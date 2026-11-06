# -*- coding: utf-8 -*-
"""지난 공문·첨부 → 대상 학년도 버전 변환 엔진(v3 파이프라인을 함수로 정리한 것).

convert.py가 init()으로 경로·대상 학년도를 정하고 run(items)을 부른다.
원본은 읽기만 한다. 결과는 결과 폴더 아래 새 파일로만 쓴다(같은 이름이 있으면 멈춤).
"""
import os, re, io, json, shutil, zipfile, time, subprocess, traceback, collections

import dateconv as dc
import xmlconv

TSY = None
SRC_DEFAULT = None
OUT = None            # 일반 결과 폴더
OUT_STUDENT = None    # 학생 자료로 보이는 파일을 그대로 복사할 폴더(결과 폴더 안 학생자료_변환안함)
WORK = None
TMP = None
GROUP_DIR = {}        # 묶음 번호 → 결과 첫 폴더 이름
import office


def _T(k):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "배포문구.json"), encoding="utf-8") as f:
        return json.load(f)[k]


def init(tsy, out, out_student, tmp, group_dir):
    global TSY, SRC_DEFAULT, OUT, OUT_STUDENT, WORK, TMP, GROUP_DIR
    TSY = int(tsy)
    SRC_DEFAULT = TSY - 1  # 학년도 근거가 없을 때 원래 문서의 학년도(지난 학년도)
    OUT, OUT_STUDENT, TMP = os.path.abspath(out), os.path.abspath(out_student), os.path.abspath(tmp)
    WORK = os.path.join(TMP, "w")
    os.makedirs(WORK, exist_ok=True)
    GROUP_DIR = dict(group_dir)


def L(p):  # 긴 경로
    p = os.path.abspath(p)
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


def conv_name(name, base_sy, years):
    new, ch, fl, _ = dc.convert(name, base_sy=base_sy, years=years, where="파일 이름")
    return new, ch, fl


def date_school_years(text):
    t = re.sub(r"[가-힣A-Za-z][가-힣A-Za-z0-9·]*-\d{2,6}\s*\([^()]{0,40}\)", " ", (text or "")[:8000])
    out = []
    for y, m in re.findall(r"(?<![\d,])(20\d{2})\s*[.년]\s*(\d{1,2})\s*[.월]\s*\d{1,2}", t):
        y, m = int(y), int(m)
        if 1 <= m <= 12 and dc.SRC_LO <= y <= dc.SRC_HI:
            out.append(y if m >= 3 else y - 1)
    return out


def working_sy(sy, text):
    """연도만 쓴 표기를 옮길 기준(작업 학년도). 문서 학년도 표기가 대상 학년도 이상이면(다음 해 준비 문서)
    본문 날짜의 학년도, 날짜가 없으면 지난 학년도를 작업 학년도로 본다."""
    if sy < TSY:
        return sy
    ds = date_school_years(text)
    return collections.Counter(ds).most_common(1)[0][0] if ds else SRC_DEFAULT


def detect_sy(path, text):
    """본문을 먼저 본다: 'YYYY학년도', 'YYYY년', 완전한 날짜의 학년도. 본문에 없을 때만 파일 이름·폴더."""
    D = SRC_DEFAULT
    fname = path.split("/")[-1]
    fy = [int(y) for y in re.findall(r"(20\d{2})\s*학년도", fname)]
    if fy and fy[0] != D and dc.SRC_LO <= fy[0] <= dc.SRC_HI:
        return fy[0], True  # 파일 이름에 다른 학년도가 적혀 있으면 그것을 따름
    t = (text or "")[:8000]
    t = re.sub(r"[가-힣A-Za-z][가-힣A-Za-z0-9·]*-\d{2,6}\s*\([^()]{0,40}\)", " ", t)  # 관련 문서 날짜는 빼고 셈
    ys = [int(y) for y in re.findall(r"(20\d{2})\s*학년도", t)]
    ys += [int(y) for y in re.findall(r"(?<![\d,.\-])(20\d{2})\s*년(?!도)", t)]
    for y, m in re.findall(r"(?<![\d,])(20\d{2})\s*[.년]\s*(\d{1,2})\s*[.월]\s*\d{1,2}", t):
        y, m = int(y), int(m)
        if 1 <= m <= 12:
            ys.append(y if m >= 3 else y - 1)
    ys = [y for y in ys if dc.SRC_LO <= y <= dc.SRC_HI]
    if ys:
        c = collections.Counter(ys)
        top, n = c.most_common(1)[0]
        # 다른 학년도로 보려면 본문 근거가 2개 이상이고 지난 학년도 근거의 2배 이상이어야 함
        # 지난 학년도 근거가 하나도 없고 다른 한 학년도만 보이면 그 학년도로 본다
        d_any = len(re.findall(r"(?<!\d)" + str(D) + r"(?!\d)", t + " " + fname))
        if top != D and ((n < 2 and (c.get(D, 0) > 0 or d_any > 0 or len(c) > 1)) or n < 2 * c.get(D, 0)):
            return D, False
        if top != D:
            return top, True
        return D, False
    ys = [int(y) for y in re.findall(r"(20\d{2})\s*학년도", path.split("/")[-1])] or \
         [int(y) for y in re.findall(r"(20\d{2})\s*학년도", path)]
    ys = [y for y in ys if dc.SRC_LO <= y <= dc.SRC_HI]
    if not ys:
        return D, False
    c = collections.Counter(ys).most_common()
    top = c[0][0]
    if D in dict(c) and dict(c)[D] >= c[0][1]:
        top = D
    return top, top != D


NO_CONVERT = {
    ".jpg": "그림 파일(글자 바꿀 수 없음)", ".jpeg": "그림 파일", ".png": "그림 파일(글자 바꿀 수 없음)",
    ".gif": "그림 파일", ".bmp": "그림 파일", ".tif": "그림 파일", ".tiff": "그림 파일",
    ".ozd": "에듀파인 지출품의서(ozd) - 읽고 고칠 도구 없음", ".cell": "한셀(cell) 파일 - 규칙상 바꾸지 않음",
    ".exe": "프로그램 파일 - 실행·변경 금지", ".msi": "프로그램 파일 - 실행·변경 금지", ".lnk": "바로가기 파일",
    ".zip": "압축 파일(서식모음집) - 규칙상 풀지 않음", ".mp3": "소리 파일", ".mp4": "동영상 파일",
}


def out_path(it, new_ext=None, suffix=""):
    parts = it["rel"].split("/")
    sy = it.get("base_sy", SRC_DEFAULT)
    newparts = [conv_name(p, SRC_DEFAULT, TSY - SRC_DEFAULT)[0] for p in parts[:-1]]  # 폴더 구조는 지난 학년도 작업 묶음
    stem, ext = os.path.splitext(parts[-1])
    stem = conv_name(stem, sy, TSY - sy)[0] + suffix
    root = OUT_STUDENT if it.get("학생정보") else OUT
    return os.path.join(root, GROUP_DIR.get(it["zip"], it["zip"]), *newparts, stem + (new_ext or ext))


def write_out(path, data):
    os.makedirs(L(os.path.dirname(path)), exist_ok=True)
    if os.path.exists(L(path)):
        raise RuntimeError("이미 있는 파일 - 덮어쓰지 않음: " + path)
    with open(L(path), "wb") as f:
        f.write(data)


# ------------------------------------------------------------------ 한글 단계
class HwpStage:
    def __init__(self):
        self.h = None
        self.count = 0

    def get(self):
        if self.h is None or self.count >= 60 or getattr(self.h, "killed", False):
            if self.h:
                self.h.quit()
            import hwpcom
            self.h = hwpcom.Hwp()
            self.count = 0
        self.count += 1
        return self.h

    def to_hwpx(self, src, key, fmt=""):
        """한글이 도중에 꺼지면(RPC 서버 없음 등) 새 한글을 띄워 한 번 더 해 본다."""
        try:
            return self._to_hwpx(src, key, fmt)
        except Exception:
            self.quit()
            self.h = None
            return self._to_hwpx(src, key, fmt)

    def _to_hwpx(self, src, key, fmt=""):
        ext = os.path.splitext(src)[1].lower()
        tin = os.path.join(WORK, f"{key}{ext}")
        tout = os.path.join(WORK, f"{key}.hwpx")
        if os.path.abspath(src) != os.path.abspath(tin):
            shutil.copyfile(L(src), tin)
        h = self.get()
        ok = h.open(tin, fmt)
        if not ok:
            raise RuntimeError("한글에서 열기 실패")
        pages = h.pages()
        ok = h.save_as(tout, "HWPX")
        h.close_doc()
        if not ok or not os.path.exists(tout):
            raise RuntimeError("hwpx 저장 실패")
        return open(tout, "rb").read(), pages

    def quit(self):
        if self.h:
            self.h.quit(); self.h = None


def tessdata():
    return office.tessdata()


def ocr_pdf(path):
    import pymupdf as fitz
    td = tessdata()
    if not td:
        return None
    d = fitz.open(L(path))
    pages = []
    for p in d:
        tp = p.get_textpage_ocr(language="kor+eng", dpi=300, full=True, tessdata=td)
        pages.append(p.get_text(textpage=tp))
    return pages


def run(items, progress=True):
    """items: convert.py가 만든 파일 목록. 반환: 결과 기록 목록."""
    import pdf2html, pdflayout, xlsxdates, make_paste, gongmun_format as gf
    os.makedirs(L(OUT), exist_ok=True)
    stage = HwpStage()
    results = []
    t0 = time.time()
    try:
        for k, it in enumerate(items):
            key = f"{it['zip']}_{k:04d}"
            r = {k2: it.get(k2) for k2 in ("zip", "rel", "sha256", "ext", "기록id", "학생정보", "pdf종류", "공문본문")}
            r["대상학년도"] = TSY
            r.update({"상태": None, "결과": [], "바꿈": [], "표시": [], "오류": [], "비고": []})
            results.append(r)
            ext = it["ext"]
            try:
                if it.get("중복원본"):
                    r["상태"] = "중복(같은 파일)"; r["비고"].append("같은 파일을 한 번만 변환: " + it["중복원본"]); continue
                if it.get("hwp파생"):
                    r["상태"] = "중복(hwp 일괄 변환본)"; r["비고"].append("같은 이름 hwp를 변환함: " + it["hwp파생"]); continue
                if it.get("학생정보"):
                    # 학생 자료로 보이는 파일은 바꾸지 않고 이름도 그대로 학생자료_변환안함/에 복사한다
                    op = os.path.join(OUT_STUDENT, GROUP_DIR.get(it["zip"], it["zip"]), *it["rel"].split("/"))
                    write_out(op, open(L(it["abs"]), "rb").read()); r["결과"].append(op)
                    r["상태"] = "학생 자료(변환 안 함)"; r["그대로복사"] = True
                    r["비고"].append(_T("d.student_note"))
                    continue
                if ext == ".xls" and not office.soffice():
                    op = out_path(it); write_out(op, open(L(it["abs"]), "rb").read()); r["결과"].append(op)
                    r["상태"] = "변환 안 함"; r["그대로복사"] = True
                    r["비고"].append(_T("d.lo_missing_xls"))
                    continue
                if ext in NO_CONVERT or ext not in (".hwpx", ".docx", ".xlsx", ".odt", ".xls", ".hwp", ".pdf", ".txt", ".md", ".csv"):
                    # 바꿀 수 없는 파일은 그대로 복사하고 목록에 남긴다
                    op = out_path(it); write_out(op, open(L(it["abs"]), "rb").read()); r["결과"].append(op)
                    r["상태"] = "변환 안 함"
                    r["비고"].append(NO_CONVERT.get(ext, f"규칙에 없는 형식({ext})"))
                    r["비고"].append("원본 파일을 그대로 복사했습니다.")
                    r["그대로복사"] = True
                    continue
                raw = open(L(it["abs"]), "rb").read()
                # 1) 준비: 고칠 zip 문서(doc, mode) 또는 글
                doc, mode, text, note, status, suffix, newext = None, None, None, [], "변환 완료", "", None
                keep_pdf = False
                if ext in (".hwpx", ".docx", ".xlsx", ".odt"):
                    doc, mode = raw, ext[1:]
                elif ext == ".xls":
                    tdir = os.path.join(WORK, key + "_xls"); os.makedirs(tdir, exist_ok=True)
                    tin = os.path.join(tdir, "in.xls"); shutil.copyfile(L(it["abs"]), tin)
                    prof = "file:///" + os.path.join(TMP, "lo_profile").replace("\\", "/")
                    subprocess.run([office.soffice(), f"-env:UserInstallation={prof}",
                                    "--headless", "--convert-to", "xlsx", "--outdir", tdir, tin], timeout=180, capture_output=True)
                    doc, mode, newext = open(os.path.join(tdir, "in.xlsx"), "rb").read(), "xlsx", ".xlsx"
                    note.append("xls → xlsx(LibreOffice로 형식만 바꾼 뒤 수정)")
                elif ext == ".hwp":
                    doc, pages = stage.to_hwpx(it["abs"], key); mode, newext = "hwpx", ".hwpx"
                    r["원본쪽수"] = pages; note.append("hwp → hwpx")
                elif ext == ".pdf" and it["pdf종류"] == "글자" and pdflayout.detect(it["abs"])["서식"]:
                    # 서식 PDF: 다시 만들지 않고 원본을 그대로 둔 뒤 고칠 날짜만 목록으로 남긴다
                    lay = pdflayout.detect(it["abs"])
                    r["서식PDF판정"] = lay
                    keep_pdf = True
                    text = None
                elif ext == ".pdf" and it["pdf종류"] == "글자":
                    hs, pages = pdf2html.pdf_to_html(L(it["abs"]))
                    hp = os.path.join(WORK, key + ".html"); open(hp, "w", encoding="utf-8").write(hs)
                    doc, _ = stage.to_hwpx(hp, key, "HTML"); mode, newext, suffix = "hwpx", ".hwpx", " (PDF에서 변환)"
                    r["원본쪽수"] = pages
                    note.append("글자 PDF → 글·표를 뽑아 hwpx로 다시 만듦(한글 PDF 변환기는 안내 창이 자동으로 닫히지 않아 쓰지 않음). 글꼴·위치·쪽 나눔은 원본과 다름")
                elif ext == ".pdf":
                    pages = ocr_pdf(it["abs"])
                    if pages is None:
                        op = out_path(it); write_out(op, raw); r["결과"].append(op); r["그대로복사"] = True
                        r["상태"] = "OCR 필요"; r["비고"].append(_T("d.ocr_missing")); continue
                    txt = "".join(pages)
                    if len(re.sub(r"\s", "", txt)) < 20:
                        op = out_path(it); write_out(op, raw); r["결과"].append(op); r["그대로복사"] = True
                        r["상태"] = "OCR 필요"; r["비고"].append("OCR로 글자를 거의 읽지 못함(손글씨·흐린 스캔)")
                        r["비고"].append("원본 파일을 그대로 복사했습니다."); continue
                    import html as _h
                    tpath = os.path.join(WORK, key + "_ocr.html")
                    hb_ = []
                    for pi, pg in enumerate(pages):
                        if pi:
                            hb_.append('<p style="page-break-before:always"></p>')
                        hb_ += ["<p>" + _h.escape(l) + "</p>" for l in pg.splitlines() if l.strip()]
                    open(tpath, "w", encoding="utf-8").write('<html><head><meta charset="utf-8"></head><body>' + "\n".join(hb_) + "</body></html>")
                    doc, _ = stage.to_hwpx(tpath, key + "_ocr", "HTML"); mode, newext, suffix = "hwpx", ".hwpx", " (OCR 변환)"
                    r["원본쪽수"] = len(pages); status = "일부"
                    note.append("스캔 PDF → 한컴 OCR 글자 자료(tessdata)로 글자만 읽어 hwpx로 만듦. 서식·표·서명 없음, 띄어쓰기·오인식 대조 필요")
                    r["표시"].append({"분류": "OCR 확인 필요", "위치": "문서 전체", "원문": it["rel"][-80:],
                                      "설명": "스캔 PDF를 OCR로 읽어 만든 hwpx입니다. 원본과 비교해 확인하세요."})
                else:
                    text = raw
                # 2) 문서 학년도와 더할 해
                if keep_pdf:
                    pre = pdflayout.page_text(it["abs"])
                else:
                    pre = xmlconv.plain_text(doc, mode) if doc is not None else raw[:20000].decode("utf-8", "ignore")
                sy0, other = detect_sy(it["rel"], pre)
                sy = working_sy(sy0, pre)
                years = TSY - sy
                it["base_sy"] = sy
                r["문서학년도표기"], r["기준학년도"], r["더한해"] = sy0, sy, years
                if other:
                    r["표시"].append({"분류": "원래 다른 연도 문서", "위치": "문서 전체", "원문": it["rel"][-80:],
                                      "설명": f"{sy0}학년도 문서로 보입니다. 날짜는 {TSY}학년도 안으로 옮겼고, 연도만 쓴 표기는 {years:+d}년 옮겼습니다."})
                if sy != sy0:
                    r["표시"].append({"분류": "문서 학년도와 날짜 학년도 다름", "위치": "문서 전체", "원문": it["rel"][-80:],
                                      "설명": f"{sy0}학년도를 준비하는 문서로 보이며, 본문 날짜는 {sy}학년도입니다. 연도만 쓴 표기는 {sy}학년도를 기준으로 {years:+d}년 옮겼습니다(예: {sy0}학년도 → {sy0 + years}학년도). 확인하세요."})
                _, nch, nfl = conv_name(os.path.splitext(it["rel"].split("/")[-1])[0], sy, years)
                for f in nfl:
                    if f["분류"] in ("다른 연도 표기", "다른 학년도 날짜", "학년도 넘는 기간", "여러 해 기간", "날짜 순서 바뀜"):
                        f["위치"] = "파일 이름"
                        r["표시"].append(f)
                for c in nch:
                    c["위치"] = "파일 이름"
                r["바꿈"] += nch
                # 파일·폴더 이름에 일(日)만 쓴 날짜 등이 남아 있으면 이름은 그대로 두고 표시한다
                for part in it["rel"].split("/"):
                    for ref in dc.name_day_refs(os.path.splitext(part)[0] if part == it["rel"].split("/")[-1] else part):
                        r["표시"].append({"분류": dc.CAT_ORDER, "위치": "파일 이름", "원문": part[-80:],
                                          "설명": dc.msg(141, D=ref)})
                r["비고"] += note
                log = None
                # 3) 바꾸기
                if keep_pdf:
                    op = out_path(it); write_out(op, raw); r["결과"].append(op); r["그대로복사"] = True
                    items_, ch_, fl_ = pdflayout.planned_dates(it["abs"], sy, years)
                    r["고칠날짜"] = items_
                    r["상태"] = "원본 유지(서식 PDF)"
                    r["비고"].append(dc.msg(142))
                    for x in items_:
                        r["표시"].append({"분류": "원본 유지(서식 PDF)", "위치": dc.msg(143, N=x["쪽"]), "원문": x["원문"],
                                          "설명": f"{x['원문'].strip()} → {x['새글'].strip()}"
                                                  + (f" ({x['새날짜']}, {x['새요일']})" if x.get("새날짜") else "")})
                    r["표시"] += fl_
                    r["표시"] += dc.order_check(ch_, skip_where=())
                    continue
                if doc is not None:
                    hooks, lg = None, xmlconv.new_log()
                    if mode == "xlsx":
                        hooks = xlsxdates.make_hooks(doc, years, lg) or None
                    newb, log = xmlconv.convert_zipdoc(doc, mode, sy, extra=hooks, years=years)
                    log["flags"] += lg["flags"]
                    pics = [n for n in zipfile.ZipFile(io.BytesIO(doc)).namelist() if re.match(r"(Pictures|BinData|word/media|xl/media)/", n)]
                    if pics:
                        r["표시"].append({"분류": "그림 포함(로고 등)", "위치": "문서 전체", "원문": f"그림 {len(pics)}개",
                                          "설명": "이전 학교 로고·사진일 수 있음. 그림은 바꾸지 않음"})
                    title = None
                    if mode == "odt":
                        jlog = []
                        title, pbody, patt = make_paste.parse(newb, jlog)
                    if title:
                        flog = list(jlog)
                        t2, lines2, items2 = gf.format_paste(title, pbody, patt, flog)
                        r["표시"] += gf.spacing_check(lines2)
                        text_out = "\r\n".join(["[제목]", t2, "", "[본문]"] + lines2 + ["", "[붙임 목록]"] + (items2 or ["(없음)"])) + "\r\n"
                        tp = out_path(it, ".txt", "_업무관리시스템_붙여넣기"); write_out(tp, text_out.encode("utf-8-sig"))
                        r["결과"].append(tp)
                        r["서식정리"] = [{"위치": w, "원래": a, "고친것": b, "근거": c} for w, a, b, c in flog]
                        r["odt공문본문"] = True
                        r["공문본문"] = True
                        r["비고"].append("odt 공문 본문 → 업무관리시스템 붙여넣기 글만 만듦(odt는 만들지 않음)")
                    else:
                        op = out_path(it, newext, suffix); write_out(op, newb); r["결과"].append(op)
                    r["상태"] = status
                else:
                    lg = xmlconv.new_log()
                    nb = xmlconv.text_member(text, lg, sy, "본문", years)
                    s_ = text.decode("utf-8-sig", "ignore") if not text.startswith(b"\xff\xfe") else text.decode("utf-16")
                    for i2, line in enumerate(s_.splitlines()):
                        lg["flags"] += dc.find_flags(line, where=f"{i2+1}번째 줄")
                    log = lg
                    op = out_path(it); write_out(op, nb if nb is not None else text); r["결과"].append(op)
                    r["상태"] = "변환 완료"
                if log is not None:
                    r["바꿈"] += log["changes"]
                    r["표시"] += log["flags"]
                    r["오류"] += log["errors"]
                    if log["errors"]:
                        r["상태"] = "일부"
                    if not log["changes"] and not nch:
                        r["비고"].append("바꿀 날짜·연도 없음")
                # 4) 한 문서 안 날짜 순서가 바꾼 뒤에도 그대로인지
                r["표시"] += dc.order_check(r["바꿈"])
            except Exception as e:
                r["상태"] = "오류"; r["오류"].append(f"{type(e).__name__}: {e}")
                r["오류"].append(traceback.format_exc()[-600:])
            if progress:
                print(f"{k + 1}/{len(items)} {time.time()-t0:.0f}s {r['상태']} {it['ext']}", flush=True)
    finally:
        stage.quit()
    return results
