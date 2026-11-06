# -*- coding: utf-8 -*-
"""전후 캡처 비교 HTML: 원래 파일과 바꾼 파일(윤문 판이 있으면 그 판)을 쪽 그림으로 나란히 놓고 표시한다.

py -3 -E <스킬 폴더>/tools/gongmun.py capture <결과 폴더> [--판 N] [--no-render]

- 상자는 모두 실선이고 바뀐 곳에만 그린다. 전 쪽에는 원래 글, 후 쪽에는 고친 글 위에 같은 자리로 그린다.
  빨간 상자: 날짜·연도 바꿈, 붙여넣기 글 서식 정리, 오타·맞춤법·띄어쓰기·공문서표기 윤문.
  파란 상자: 문장 다듬음(비문·어색한표현) 윤문. 색은 고친 종류만 알린다(둘 다 판 N에 적용함, 설계 결정).
- 목록: 바뀐 곳(빨강), 문장 다듬음 Yxxx: 전 → 후(파랑), 되돌림, 검사에서 막혀 적용 안 함(그림에 표시하지 않음).
- 학생 자료 파일은 그리지도 보여 주지도 않는다(개수만 적음). 텍스트 칸의 학번·이름 꼴은 가린다.
- 쪽 그림: 한글(COM, 숨김)로 hwp/hwpx, LibreOffice(headless)로 docx/odt/xlsx를 PDF로 내보내 PyMuPDF로 그림을 만든다.
  글자 위치(rawdict 글자 상자)에서 표시할 글을 찾는다. 빈칸은 빼고 비교한다. 못 찾은 곳은 「그림에서 못 찾은 곳」에 적는다.
- 출력(새 파일만, 덮어쓰지 않음): 결과 폴더의 전후캡처비교.html(그 폴더에서 처음 만드는 비교 페이지),
  그다음부터는 전후캡처비교_윤문<N>.html. --붙임 _v2 를 주면 이름 끝에 _v2를 붙이고, 표시 그림은 캡처/판<N>/표시_v2/, 기록은 mark_report_v2.json.
  그림과 기록은 <결과 폴더>/_작업기록/캡처/(원래 파일 그림은 판끼리 함께 씀, 바꾼 파일 그림은 캡처/판<N>/). 그림은 HTML 안에 넣으므로 HTML 하나만 열면 된다.
- LibreOffice가 없으면 odt·docx·xlsx·xls 쪽 그림은 건너뛰고 그 파일에 안내를 적는다.
원본·결과 파일은 읽기만 한다. Hwp.exe --version은 쓰지 않는다. 연 한글·LibreOffice는 모두 닫는다.
"""
import os, re, sys, json, base64, html, shutil, difflib, argparse, tempfile, subprocess
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proofread_lib as pl
from proofread_guard import reason_text

import office
DPI = 120
RED = (212, 0, 0)
BLUE = (0, 92, 230)
e = html.escape
WS = re.compile(r"\s+")
STUDENT = re.compile(r"\b[1-3]\d{4}\s+[가-힣]{2,4}")


def jl(p):
    with open(pl.L(p), encoding="utf-8") as f:
        return json.load(f)


T = jl(os.path.join(HERE, "캡처문구.json"))
T.update(jl(os.path.join(HERE, "윤문문구.json")))
T.update(jl(os.path.join(HERE, "배포문구.json")))


def mask(s):
    return STUDENT.sub("○○○○○ ○○○", s or "")


def nows(s):
    return WS.sub("", s or "")


def read_txt(p):
    with open(pl.L(p), "rb") as f:
        s, _, _ = pl.decode_text(f.read())
    return s.replace("\r\n", "\n")


# ------------------------------------------------------------------ 쪽 그림 만들기
def lo_pdf(src, out_pdf, work):
    tmp = tempfile.mkdtemp(dir=work, prefix="lo_")
    s = os.path.join(tmp, "in" + os.path.splitext(src)[1])
    shutil.copy2(pl.L(src), s)
    prof = "file:///" + os.path.join(work, "lo_profile").replace("\\", "/")
    subprocess.run([office.soffice(), "-env:UserInstallation=" + prof, "--headless", "--norestore",
                    "--convert-to", "pdf", "--outdir", tmp, s], check=True, timeout=240, capture_output=True)
    shutil.move(os.path.join(tmp, "in.pdf"), out_pdf)
    shutil.rmtree(tmp, ignore_errors=True)


def raster(pdf, img_dir, key):
    import pymupdf as fitz
    d = fitz.open(pdf)
    outs = []
    for i, p in enumerate(d):
        f = os.path.join(img_dir, f"{key}_p{i + 1:02d}.jpg")
        if not os.path.exists(f):
            p.get_pixmap(dpi=DPI).save(f, jpg_quality=80)
        outs.append(f)
    d.close()
    return outs


def render(jobs, cap_dir):
    """jobs: [(key, 원본 경로, pdf 넣을 폴더, 그림 폴더)]. 이미 만든 PDF·그림은 다시 만들지 않는다."""
    res, hwp_jobs, other = {}, [], []
    for key, src, pdir, idir in jobs:
        os.makedirs(pdir, exist_ok=True); os.makedirs(idir, exist_ok=True)
        out = os.path.join(pdir, key + ".pdf")
        ext = os.path.splitext(src)[1].lower()
        if os.path.exists(out):
            res[key] = {"src": src, "pdf": out}
        elif ext in (".hwp", ".hwpx"):
            hwp_jobs.append((key, src, out))
        elif ext in (".odt", ".xlsx", ".docx", ".xls"):
            other.append((key, src, out))
        elif ext == ".pdf":
            shutil.copy2(pl.L(src), out); res[key] = {"src": src, "pdf": out}
    if hwp_jobs and not office.hwp_available():
        for key, src, out in hwp_jobs:
            res[key] = {"src": src, "error": T["d.hwp_missing"]}
        hwp_jobs = []
    if hwp_jobs:
        from hwpcom import Hwp
        h = Hwp()
        try:
            for key, src, out in hwp_jobs:
                try:
                    tmp = os.path.join(cap_dir, "hwp_in" + os.path.splitext(src)[1])
                    shutil.copy2(pl.L(src), tmp)   # 긴 경로·특수 문자를 피해 짧은 사본으로 연다
                    h.open(tmp); h.save_as(out, "PDF", ""); h.close_doc()
                    os.remove(tmp)
                    res[key] = {"src": src, "pdf": out}
                except Exception as ex:
                    res[key] = {"src": src, "error": str(ex)}
        finally:
            h.quit()
    for key, src, out in other:
        if not office.soffice():
            res[key] = {"src": src, "error": T["d.lo_missing_render"]}
            continue
        try:
            lo_pdf(src, out, cap_dir); res[key] = {"src": src, "pdf": out}
        except Exception as ex:
            res[key] = {"src": src, "error": repr(ex)}
    shutil.rmtree(os.path.join(cap_dir, "lo_profile"), ignore_errors=True)
    for key, src, pdir, idir in jobs:
        v = res.get(key)
        if v and "pdf" in v and os.path.exists(v["pdf"]):
            v["images"] = raster(v["pdf"], idir, key)
    return res


# ------------------------------------------------------------------ 글자 위치 색인
class Index:
    """글자(빈칸 제외)를 차례로 늘어놓고 글자마다 (쪽, 상자, 줄 키)를 기억한다."""

    def __init__(self, chars):
        self.chars = chars
        self.s = "".join(c[3] for c in chars)
        self.used = []

    @classmethod
    def from_pdf(cls, pdf):
        import pymupdf as fitz
        d = fitz.open(pdf)
        chars, sizes = [], []
        for pno, p in enumerate(d):
            sizes.append((p.rect.width, p.rect.height))
            lid = 0
            for b in p.get_text("rawdict")["blocks"]:
                if b.get("type") != 0:
                    continue
                for ln in b["lines"]:
                    lid += 1
                    for sp in ln["spans"]:
                        for ch in sp["chars"]:
                            if not ch["c"].isspace():
                                chars.append((pno, tuple(ch["bbox"]), (pno, lid), ch["c"]))
        d.close()
        ix = cls(chars)
        ix.sizes = sizes
        return ix

    @classmethod
    def from_text(cls, text):
        chars, line = [], 0
        for i, c in enumerate(text):
            if c == "\n":
                line += 1
            elif not c.isspace():
                chars.append((0, i, line, c))
        return cls(chars)

    def free(self, a, b):
        return all(b <= x or a >= y for x, y in self.used)

    def find(self, key, ctx=None, off=None, overlap=False):
        k = nows(key)
        if not k:
            return None
        if ctx:
            c = nows(ctx)
            for m in re.finditer(re.escape(c), self.s):
                a = m.start() + (off or 0)
                if self.s[a:a + len(k)] == k and (overlap or self.free(a, a + len(k))):
                    self.used.append((a, a + len(k)))
                    return a, a + len(k)
        for m in re.finditer(re.escape(k), self.s):
            if self.free(m.start(), m.end()):
                self.used.append((m.start(), m.end()))
                return m.start(), m.end()
        if overlap:
            m = re.search(re.escape(k), self.s)
            if m:
                return m.start(), m.end()
        return None

    def rects(self, span):
        a, b = span
        out = OrderedDict()
        for pno, bb, lk, _ in self.chars[a:b]:
            r = out.get(lk)
            out[lk] = (pno, bb if r is None else (min(r[1][0], bb[0]), min(r[1][1], bb[1]), max(r[1][2], bb[2]), max(r[1][3], bb[3])))
        return list(out.values())

    def text_spans(self, span):
        a, b = span
        out = OrderedDict()
        for _, i, line, _ in self.chars[a:b]:
            s0, s1 = out.get(line, (i, i + 1))
            out[line] = (min(s0, i), max(s1, i + 1))
        return list(out.values())


# ------------------------------------------------------------------ 표시할 곳 목록
def items_of(r):
    """변환 도구가 바꾼 곳(날짜·연도·서식 정리). 모두 빨간색."""
    out = []
    years = r.get("더한해") or 1
    for c in r.get("바꿈", []):
        a, n = c.get("원문", ""), c.get("새글", "")
        # 엑셀 날짜 칸은 '2025-03-04 (일련번호 45720)'로 적혀 있다. 쪽 그림에는 날짜만 보이므로 날짜로 찾는다
        a, n = re.sub(r"\s*\(일련번호 \d+\)$", "", a), re.sub(r"\s*\(일련번호 \d+\)$", "", n)
        it = {"위치": c.get("위치", ""), "색": "red",
              "종류": "name" if c.get("위치") == "파일 이름" else ("meta" if c.get("위치") == "문서 정보" else "body")}
        if re.fullmatch(r"\d{4}", n) and "원래날짜" not in c:
            oy = str(int(n) - years)
            i = a.find(oy)
            if i < 0:
                it.update(원래=a, 새=n, 전키=a, 후키=n)
            else:
                suf = "학년도" if a[i + 4:].lstrip().startswith("학년도") else ("년" if a[i + 4:].lstrip().startswith("년") else "")
                it.update(원래=a, 새=a[:i] + n + a[i + 4:], 전키=oy + suf, 후키=n + suf, 전문맥=a, 후문맥=a[:i] + n + a[i + 4:],
                          문맥위치=len(nows(a[:i])))
        else:
            it.update(원래=a, 새=n, 전키=a.strip(), 후키=n.strip())
        out.append(it)
    for f in r.get("서식정리", []):
        a, b = f["원래"], f["고친것"]
        core = b
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        rng = [(j1, j2) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag in ("replace", "insert") and b[j1:j2].strip()]
        if rng:
            core = b[rng[0][0]:rng[-1][1]]
        out.append({"위치": f["위치"], "종류": "format", "색": "red", "원래": a, "새": b, "전키": None, "후키": core,
                    "후문맥": b if core != b else None, "문맥위치": len(nows(b[:b.find(core)])) if core != b and core in b else None})
    return out


def neighbors(text, i, j, taken, width=10):
    """표시할 글 앞뒤의 문맥(숫자·다른 윤문 항목이 나오면 끊음). (앞, 뒤)"""
    lo = i
    while lo > 0 and i - lo < width and not text[lo - 1].isdigit() and not any(s < lo <= t for s, t in taken):
        lo -= 1
    hi = j
    while hi < len(text) and hi - j < width and not text[hi].isdigit() and not any(s <= hi < t for s, t in taken):
        hi += 1
    return text[lo:i], text[j:hi]


def proof_items(rid, entries, applied_ids, paras):
    """판에 넣은 윤문 항목. 전 쪽은 원래 글, 후 쪽은 고친 글에 같은 자리로 실선 상자를 그린다.
    색: 빨강 = 오타·맞춤법·띄어쓰기·공문서표기, 파랑 = 문장 다듬음(비문·어색한표현)."""
    mine = [x for x in entries if x.get("file") == rid and x["id"] in applied_ids]
    taken = {}
    for x in mine:
        t = paras.get(x["location"], ("", ""))[1]
        k = t.find(x["before"])
        if k >= 0:
            taken.setdefault(x["location"], []).append((k, k + len(x["before"])))
    out = []
    for x in mine:
        t = paras.get(x["location"], ("", ""))[1]
        k = t.find(x["before"])
        others = [s for s in taken.get(x["location"], []) if s != (k, k + len(x["before"]))]
        left, right = neighbors(t, k, k + len(x["before"]), others) if k >= 0 else ("", "")
        loc = paras.get(x["location"], (x["location"], ""))[0]
        label = f'{x["category"]} · {loc}'
        out.append({"종류": "proof", "색": pl.colour_of(x), "위치": label, "원래": x["before"], "새": x["after"], "전키": x["before"],
                    "후키": x["after"], "전문맥": left + x["before"] + right, "후문맥": left + x["after"] + right,
                    "문맥위치": len(nows(left)), "번호": x["id"], "까닭": x.get("reason", "") if pl.colour_of(x) == "blue" else ""})
    return out


# ------------------------------------------------------------------ 그림에 그리기
def font(sz):
    from PIL import ImageFont
    for p in (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\malgunbd.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def draw_marks(img_path, page_size, marks, out_path):
    """marks: [(번호 글 또는 "", 색 이름, (x0,y0,x1,y1) PDF 좌표)]
    빨강·파랑 모두 실선 상자. 번호표는 상자 왼쪽 위에 붙인다. 선 굵기·글자 크기는 그림 해상도에 맞춘다."""
    from PIL import Image, ImageDraw
    im = Image.open(img_path).convert("RGB")
    sc = im.width / page_size[0]
    k = sc / (DPI / 72.0)
    dr = ImageDraw.Draw(im)
    F = font(round(14 * k))
    lw, pad, lh = max(1, round(3 * k)), 3 * k, round(17 * k)
    labels = []
    for m in marks:
        n, col, (x0, y0, x1, y1) = m[0], m[1], m[2]
        c = RED if col == "red" else BLUE
        bx = [x0 * sc - pad, y0 * sc - pad, x1 * sc + pad, y1 * sc + pad]
        dr.rectangle(bx, outline=c, width=lw)
        if n:
            w = dr.textlength(n, font=F) + 8 * k
            lx, ly = bx[0], bx[1] - lh + 1
            if ly < 0:
                lx, ly = max(0, bx[0] - w - 1), bx[1]
            labels.append(([lx, ly, lx + w, ly + lh], c, n))
    for (r, c, n) in labels:
        dr.rectangle(r, fill=c)
        dr.text((r[0] + 4 * k, r[1]), n, fill=(255, 255, 255), font=F)
    im.save(out_path, quality=85)


def img_uri(p):
    with open(p, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()


def page_cell(src, n, side):
    if not src:
        return f'<div class="cell empty"><span>{e(T["cap.no_page"])}</span></div>'
    alt = f'{T["detail.before"] if side == "b" else T["detail.after"]} {T["cap.page"].replace("{N}", str(n))}'
    return f'<div class="cell"><img loading="lazy" src="{img_uri(src)}" alt="{e(alt)}" tabindex="0"></div>'


def text_panel(text, label, spans):
    """spans: [(시작, 끝, 번호, 첫 조각인지, 색)] - 빨강은 mark.chg, 파랑(문장 다듬음)은 mark.sent."""
    merged = []
    for sp in sorted(spans, key=lambda t: t[:4]):
        a, b, n, first, col = sp[:5]
        if merged and a < merged[-1][1]:
            m = merged[-1]
            m[1] = max(m[1], b)
            if first and n not in m[2]:
                m[2].append(n)
        else:
            merged.append([a, b, [n] if first else [], col])
    out, pos = [], 0
    for a, b, ns, col in merged:
        out.append(e(mask(text[pos:a])))
        cls = "chg" if col == "red" else "sent"
        sup = f'<sup class="mn {cls}">{",".join(map(str, ns))}</sup>' if ns else ""
        out.append(f'<mark class="{cls}">{sup}{e(mask(text[a:b]))}</mark>')
        pos = b
    out.append(e(mask(text[pos:])))
    return f'<div class="cell textcell"><div class="tlabel">{e(label)}</div><pre class="paste">{"".join(out)}</pre></div>'


def name_html(name, items, side):
    ix = Index.from_text(name)
    spans = []
    for it in items:
        if it["종류"] != "name":
            continue
        sp = ix.find(it["전키"] if side == "b" else it["후키"], it.get("전문맥") if side == "b" else it.get("후문맥"), it.get("문맥위치"))
        if sp:
            for j, (a, b) in enumerate(ix.text_spans(sp)):
                spans.append((a, b, it["n"], j == 0))
            it.setdefault("찾음", set()).add(side)
    out, pos = [], 0
    for a, b, n, first in sorted(spans):
        out.append(e(name[pos:a]))
        out.append(f'<mark class="chg"><sup class="mn chg">{n if first else ""}</sup>{e(name[a:b])}</mark>')
        pos = b
    out.append(e(name[pos:]))
    return "".join(out)


def status_label(r):
    s = r["상태"]
    if s == "원본 유지(서식 PDF)":
        return T["status.kept_pdf"], "copy"
    if s.startswith("중복"):
        return T["status.duplicate"], "dup"
    if s == "변환 안 함":
        return T["status.not_converted"] + " · " + T["status.copied"], "copy"
    if s == "변환 완료":
        return T["status.done"], "ok"
    return s, "warn"


# ------------------------------------------------------------------ 본체
def main(argv=None):
    ap = argparse.ArgumentParser(description="전후 캡처 비교 HTML 만들기")
    ap.add_argument("result_dir", help="변환 결과 폴더(<입력>_올해버전)")
    ap.add_argument("--판", dest="ver", type=int, help="윤문 판 번호(기본: 가장 최근 판, 없으면 0)")
    ap.add_argument("--no-render", action="store_true", help="이미 만든 그림만 씀(새로 그리지 않음)")
    ap.add_argument("--붙임", dest="suffix", default="", help="새 이름 붙임(예: _v2). HTML·표시 그림·기록을 새 이름으로 만든다")
    a = ap.parse_args(argv)
    if a.suffix and not re.fullmatch(r"_[0-9A-Za-z가-힣]+", a.suffix):
        raise SystemExit("--붙임은 _v2처럼 밑줄로 시작하는 짧은 글이어야 합니다.")
    run = pl.Run(a.result_dir)
    recs = run.records()
    info = jl(os.path.join(run.work, "기록", "실행정보.json"))
    vers = jl(run.versions)["판"] if os.path.exists(pl.L(run.versions)) else []
    n = a.ver if a.ver is not None else (vers[-1]["판"] if vers else 0)
    vinfo = next((v for v in vers if v["판"] == n), None) if n else None
    if n and not vinfo:
        raise SystemExit(f"판 {n}이 적용기록에 없습니다.")
    entries = jl(run.entries)["항목"] if n and os.path.exists(pl.L(run.entries)) else []
    blocked = []
    if entries:
        ok, blocked = pl.check_all(run, entries)
        entries = ok          # 막힌 항목은 그림에 그리지 않고 「검사에서 막혀 적용 안 함」에만 적음
    applied = set(vinfo["넣은항목"]) if vinfo else set()
    reverted = set(vinfo.get("되돌린항목", [])) if vinfo else set()
    plist = jl(run.list_json) if os.path.exists(pl.L(run.list_json)) else {"파일": []}
    proof_src = {f["기록id"]: os.path.join(run.hub, f["파일"]) for f in plist["파일"]}

    import glob as _glob
    first = not _glob.glob(os.path.join(_glob.escape(run.out), "전후캡처비교*.html"))
    html_name = ("전후캡처비교" if (n == 0 or (first and not a.suffix)) else f"전후캡처비교_윤문{n}") + a.suffix + ".html"
    OUT = os.path.join(run.out, html_name)
    if os.path.exists(pl.L(OUT)):
        raise SystemExit(T["c.exists"].replace("{PATH}", OUT))
    CAP = os.path.join(run.review, "캡처")
    VDIR = os.path.join(CAP, f"판{n}")
    MARK = os.path.join(VDIR, "표시" + a.suffix)
    if a.suffix and os.path.exists(pl.L(MARK)):
        raise SystemExit(T["c.exists"].replace("{PATH}", MARK))
    os.makedirs(MARK, exist_ok=True)
    SRC = os.path.join(run.work, "원본", "압축해제")

    shown = [r for r in recs if not r.get("학생정보")]
    nstudent = len(recs) - len(shown)

    def after_file(r):
        if vinfo and r["기록id"] in vinfo["파일"]:
            return os.path.join(run.hub, vinfo["파일"][r["기록id"]])
        return r["결과"][0] if r.get("결과") else None

    jobs = []
    for r in shown:
        rid, ext = r["기록id"], r["ext"]
        if r["상태"].startswith("중복") or ext == ".ozd":
            continue
        src = os.path.join(SRC, r["zip"], r["rel"].replace("/", os.sep))
        if ext in (".hwp", ".hwpx", ".odt", ".xlsx", ".docx", ".xls", ".pdf"):
            jobs.append((rid + "_전", src, os.path.join(CAP, "전", "pdf"), os.path.join(CAP, "전", "img")))
        af = after_file(r)
        if af and os.path.splitext(af)[1].lower() in (".hwpx", ".hwp", ".xlsx", ".odt", ".docx") and r["상태"] != "원본 유지(서식 PDF)":
            jobs.append((rid + "_후", af, os.path.join(VDIR, "pdf"), os.path.join(VDIR, "img")))
    if a.no_render:
        rr = {}
        for key, src, pdir, idir in jobs:
            p = os.path.join(pdir, key + ".pdf")
            if os.path.exists(p):
                rr[key] = {"src": src, "pdf": p, "images": raster(p, idir, key)}
    else:
        rr = render(jobs, CAP)
    with open(os.path.join(VDIR, f"render_result{a.suffix}.json"), "w", encoding="utf-8") as f:
        json.dump(rr, f, ensure_ascii=False, indent=1)

    groups = OrderedDict()
    for r in shown:
        groups.setdefault(r["rel"].split("/")[0], []).append(r)
    parts, nav, report = [], [], {}
    tot_marked = tot_unplaced = tot_sent = tot_blocked = tot_rev = 0
    for gi, (g, rs) in enumerate(groups.items(), 1):
        newg = g
        for r in rs:
            if r.get("결과"):
                newg = os.path.basename(os.path.dirname(r["결과"][0])); break
        gid = f"g{gi}"
        nav.append(f'<li><a href="#{gid}">{e(newg)}</a> <span class="muted">({len(rs)})</span></li>')
        parts.append(f'<section class="gongmun" id="{gid}"><h2>{e(newg)}</h2><p class="muted orig">{e(g)}</p>')
        for r in rs:
            rid, ext = r["기록id"], r["ext"]
            oname = r["rel"].split("/")[-1]
            af = after_file(r)
            nname = os.path.basename(af) if af else ""
            kept = r["상태"] == "원본 유지(서식 PDF)"
            st, cls = status_label(r)
            items = [] if r["상태"].startswith("중복") or ext == ".ozd" else items_of(r)
            if kept:
                for x in r.get("고칠날짜", []):
                    items.append({"종류": "kept", "색": "red", "위치": T["cap.page"].replace("{N}", str(x["쪽"])), "원래": x["원문"],
                                  "새": x["새글"], "쪽": x["쪽"], "상자": x["상자"]})
            if rid in proof_src and entries:
                items += proof_items(rid, entries, applied, pl.paragraphs_of(proof_src[rid]))
            for k, it in enumerate(items, 1):
                it["n"] = k
            on = name_html(oname, items, "b")
            nn = name_html(nname, items, "a") if nname else ""
            head = (f'<div class="fhead"><span class="chip {cls}">{e(st)}</span><div class="names">'
                    f'<div><b>{e(T["detail.before"])}</b> {on}</div>' + (f'<div><b>{e(T["detail.after"])}</b> {nn}</div>' if nn else "") + "</div></div>")
            body, notes = [], []
            src_path = os.path.join(SRC, r["zip"], r["rel"].replace("/", os.sep))
            before, after = rr.get(rid + "_전", {}), rr.get(rid + "_후", {})
            bimgs, aimgs = before.get("images", []), after.get("images", [])
            if T["d.lo_missing_render"] in (before.get("error"), after.get("error")):
                notes.append(T["d.lo_missing_render"])

            def want_key(it, side):
                if it["종류"] in ("name", "meta", "kept"):
                    return None
                if side == "b" and it["종류"] == "format":
                    return None
                return it["전키"] if side == "b" else it["후키"]

            def mark_pdf(side, rinfo, imgs):
                if not imgs:
                    return []
                ix = Index.from_pdf(rinfo["pdf"])
                per = {}
                for it in items:
                    if it["종류"] == "kept":
                        if side == "b" and it.get("상자"):
                            per.setdefault(it["쪽"] - 1, []).append((str(it["n"]), "red", tuple(it["상자"])))
                            it.setdefault("찾음", set()).add("b")
                        continue
                    k = want_key(it, side)
                    if not k:
                        continue
                    sp = ix.find(k, it.get("전문맥") if side == "b" else it.get("후문맥"), it.get("문맥위치"),
                                 overlap=it["종류"] in ("format", "proof"))
                    if sp:
                        for j, (pno, bb) in enumerate(ix.rects(sp)):
                            per.setdefault(pno, []).append((str(it["n"]) if j == 0 else "", it["색"], bb))
                        it.setdefault("찾음", set()).add(side)
                outs = []
                from PIL import Image
                for pi, img in enumerate(imgs):
                    op = os.path.join(MARK, ("전_" if side == "b" else "후_") + os.path.basename(img))
                    if per.get(pi):
                        draw_marks(img, ix.sizes[pi], per[pi], op)
                    else:
                        Image.open(img).save(op, quality=85)
                    outs.append(op)
                return outs

            def mark_text(side, text):
                ix = Index.from_text(text)
                spans = []
                for it in items:
                    k = want_key(it, side)
                    if not k:
                        continue
                    sp = ix.find(k, it.get("전문맥") if side == "b" else it.get("후문맥"), it.get("문맥위치"),
                                 overlap=it["종류"] in ("format", "proof"))
                    if sp:
                        for j, (s0, s1) in enumerate(ix.text_spans(sp)):
                            spans.append((s0, s1, it["n"], j == 0, it["색"]))
                        it.setdefault("찾음", set()).add(side)
                return spans

            sides = set()
            if r["상태"].startswith("중복"):
                ref = ""
                for x in r.get("비고", []):
                    m = re.search(r":\s*(.+)$", x)
                    if m:
                        ref = m.group(1).split("/")[-1]
                body.append(f'<div class="card">{e(T["cap.dup_of"].replace("{F}", ref))}</div>')
            elif ext == ".ozd":
                body.append(f'<div class="card">{e(T["cap.cannot_render"])}<br>{e(T["copied_note"])}</div>')
            elif kept:
                bm = mark_pdf("b", before, bimgs)
                notes.append(T["cap.kept_pdf"])
                fix = "".join(f'<li><span class="num chg">{it["n"]}</span> <span class="loc">{e(it["위치"])}</span> '
                              f'<span class="old">{e(it["원래"])}</span> → <span class="new">{e(it["새"])}</span></li>'
                              for it in items if it["종류"] == "kept")
                body.append(f'<div class="cols"><div class="colh">{e(T["detail.before"])}</div><div class="colh">{e(T["cap.fix_list"])}</div></div>')
                for i, p in enumerate(bm):
                    right = (f'<div class="cell card fixcard"><h4>{e(T["cap.fix_list"])}</h4><ul>{fix}</ul></div>' if i == 0 else '<div class="cell"></div>')
                    body.append(f'<div class="pg">{e(T["cap.page"].replace("{N}", str(i + 1)))}</div><div class="row">{page_cell(p, i + 1, "b")}{right}</div>')
                sides = {"b"}
            elif ext == ".txt" or os.path.splitext(nname)[1].lower() == ".txt":
                if ext == ".txt":
                    t0 = read_txt(src_path)
                    left = text_panel(t0, T["cap.text_file"], mark_text("b", t0))
                else:
                    bm = mark_pdf("b", before, bimgs)
                    left = '<div class="cell stack">' + "".join(
                        f'<div class="pg">{e(T["cap.page"].replace("{N}", str(i + 1)))}</div>' + page_cell(p, i + 1, "b") for i, p in enumerate(bm)) + "</div>"
                t1 = read_txt(af)
                right = text_panel(t1, T["cap.text_file"] if ext == ".txt" else T["cap.paste_text"], mark_text("a", t1))
                body.append(f'<div class="cols"><div class="colh">{e(T["detail.before"])}</div><div class="colh">{e(T["detail.after"])}</div></div>')
                body.append(f'<div class="row">{left}{right}</div>')
                sides = {"b", "a"}
            else:
                bm = mark_pdf("b", before, bimgs)
                am = mark_pdf("a", after, aimgs)
                if len(bm) != len(am):
                    notes.append(T["cap.page_counts"].replace("{A}", str(len(bm))).replace("{B}", str(len(am))))
                body.append(f'<div class="cols"><div class="colh">{e(T["detail.before"])}</div><div class="colh">{e(T["detail.after"])}</div></div>')
                for i in range(max(len(bm), len(am))):
                    b = bm[i] if i < len(bm) else None
                    aa = am[i] if i < len(am) else None
                    body.append(f'<div class="pg">{e(T["cap.page"].replace("{N}", str(i + 1)))}</div>'
                                f'<div class="row">{page_cell(b, i + 1, "b")}{page_cell(aa, i + 1, "a")}</div>')
                sides = {"b", "a"}
            miss = []
            for it in items:
                want = set(sides)
                if it["종류"] == "format":
                    want &= {"a"}
                if it["종류"] == "proof" and not nows(it["새"]):
                    want &= {"b"}
                if it["종류"] == "name":
                    want = {"b", "a"} if nname else {"b"}
                lost = want - it.get("찾음", set())
                if lost or it["종류"] == "meta":
                    miss.append((it, sorted(lost or {"b", "a"}, reverse=True)))
            red = [it for it in items if it["색"] == "red" and it["종류"] != "kept"]
            blue = [it for it in items if it["색"] == "blue"]
            # 그림에 그리지 않는 윤문 항목: 되돌린 것(또는 예전 판에 넣지 않은 것), 검사에서 막힌 것
            rest = [x for x in entries if x.get("file") == rid and x["id"] not in applied] if rid in proof_src else []
            rev = [x for x in rest if x["id"] in reverted]
            other = [x for x in rest if x["id"] not in reverted]
            blk = [(x, rs_) for x, rs_ in blocked if x.get("file") == rid] if rid in proof_src else []

            def li(it):
                c = "chg" if it["색"] == "red" else "sent"
                why = f' <span class="why">{e(it["까닭"])}</span>' if it.get("까닭") else ""
                if it["색"] == "blue":
                    return (f'<li class="sli"><span class="num {c}">{it["n"]}</span> '
                            f'<b class="stag">{e(T["c.sent_item"].replace("{ID}", str(it.get("번호", ""))))}</b> '
                            f'<span class="sold">{e(mask(it["원래"]))}</span> → <span class="new">{e(mask(it["새"]))}</span> '
                            f'<span class="loc">{e(it["위치"])}</span>{why}</li>')
                return (f'<li><span class="num {c}">{it["n"]}</span> <span class="loc">{e(it["위치"])}</span> '
                        f'<span class="old">{e(mask(it["원래"]))}</span> → <span class="new">{e(mask(it["새"]))}</span>{why}</li>')

            def li_off(x, why=""):
                w = f' <span class="why">{e(why)}</span>' if why else ""
                return (f'<li><b class="otag">{e(str(x.get("id", "")))}</b> <span class="loc">{e(str(x.get("category", "")))}</span> '
                        f'<span class="sold">{e(mask(x.get("before") or ""))}</span> → <span class="onew">{e(mask(x.get("after") or ""))}</span>{w}</li>')
            if red or blue or miss or rev or other or blk:
                h = '<div class="changes">'
                if red:
                    h += f'<h4>{e(T["detail.changes"])} ({len(red)})</h4><ul>{"".join(li(it) for it in red)}</ul>'
                if blue:
                    h += f'<h4 class="sh">{e(T["c.sent_heading"])} ({len(blue)})</h4><ul>{"".join(li(it) for it in blue)}</ul>'
                if rev:
                    h += f'<div class="off rev"><h4>{e(T["c.reverted_heading"])} ({len(rev)})</h4><ul>{"".join(li_off(x) for x in rev)}</ul></div>'
                if other:
                    h += f'<div class="off"><h4>{e(T["c.not_in_version"])} ({len(other)})</h4><ul>{"".join(li_off(x) for x in other)}</ul></div>'
                if blk:
                    h += (f'<div class="off blk"><h4>{e(T["c.blocked_heading"])} ({len(blk)})</h4><ul>'
                          + "".join(li_off(x, reason_text(T, rs_)) for x, rs_ in blk) + "</ul></div>")
                if miss:
                    h += (f'<div class="unplaced"><h4>{e(T["cap.unplaced"])} ({len(miss)})</h4><ul>'
                          + "".join(f'<li><span class="num {"chg" if it["색"] == "red" else "sent"}">{it["n"]}</span> '
                                    + e(", ".join(T["detail.before"] if s == "b" else T["detail.after"] for s in ss))
                                    + f' · <span class="loc">{e(it["위치"])}</span> <span class="old">{e(mask(it["원래"]))}</span> → '
                                      f'<span class="new">{e(mask(it["새"]))}</span></li>' for it, ss in miss) + "</ul></div>")
                body.append(h + "</div>")
            elif not r["상태"].startswith("중복") and ext != ".ozd" and not kept:
                body.append(f'<div class="changes"><p class="muted">{e(T["cap.no_changes"])}</p></div>')
            nmark = sum(len(it.get("찾음", ())) for it in items)
            tot_marked += nmark
            tot_unplaced += len(miss)
            tot_sent += len(blue)
            tot_blocked += len(blk)
            tot_rev += len(rev)
            report[rid] = {"표시할곳": len(items), "표시한곳(전후합)": nmark, "문장다듬음": len(blue),
                           "되돌림": [x["id"] for x in rev], "판에없음": [x["id"] for x in other], "막힘": [x.get("id") for x, _ in blk],
                           "번호별": [{"번호": it["n"], "색": it["색"], "종류": it["종류"], "윤문id": it.get("번호"),
                                     "찾음": sorted(it.get("찾음", ()))} for it in items],
                           "못찾은곳": [{"번호": it["n"], "쪽": ss, "위치": it["위치"]} for it, ss in miss]}
            nt = "".join(f'<p class="note">{e(x)}</p>' for x in notes)
            parts.append(f'<article class="file" id="{rid}">{head}{nt}{"".join(body)}</article>')
        parts.append("</section>")

    vlabel = T["c.version0"] if n == 0 else str(n)
    legend = (f'<div class="legend" role="note"><b>{e(T["c.legend"])}</b>'
              f'<span><i class="sw red"></i>{e(T["c.legend_red"])}</span><span><i class="sw blue"></i>{e(T["c.legend_blue"])}</span></div>')
    stu = f'<p class="muted">{e(T["c.student_hidden"].replace("{N}", str(nstudent)))}</p>' if nstudent else ""
    css = CSS.replace("__B__", T["detail.before"]).replace("__A__", T["detail.after"])
    page = f"""<title>{e(T['cap.title'])}</title>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>{css}</style>
<header class="top" id="top">
<h1>{e(T['cap.title'])}</h1>
<div class="sum"><div class="kv"><span>{e(T['target_year'])}</span><b>{info['대상학년도']}</b></div>
<div class="kv"><span>{e(T['all_files'])}</span><b>{len(shown)}</b></div>
<div class="kv"><span>{e(T['c.version'])}</span><b>{e(vlabel)}</b></div>
<div class="kv"><span>{e(T['cap.marked'])}</span><b>{tot_marked}</b></div>
<div class="kv"><span>{e(T['c.sent_heading'])}</span><b>{tot_sent}</b></div>
<div class="kv"><span>{e(T['c.blocked_heading'])}</span><b>{tot_blocked}</b></div>
<div class="kv"><span>{e(T['cap.unplaced'])}</span><b>{tot_unplaced}</b></div></div>
<p>{e(T['cap.intro'])} {e(T['cap.zoom_hint'])}</p>
{legend}
<p class="marknote">{e(T['cap.mark_note'])}</p>
<p class="warn">{e(T['summary.local_only'])} {e(T['cap.contact_note'])} {e(T['cap.student_mask'])}</p>
{stu}
<nav><h3>{e(T['list.title'])}</h3><ol>{''.join(nav)}</ol></nav>
</header>
<main>{''.join(parts)}</main>
<a class="totop" href="#top">{e(T['nav.top'])}</a>
<div id="lb" class="lb" hidden><button type="button" id="lbc">{e(T['cap.close'])}</button><img id="lbi" alt=""></div>
<script>{JS}</script>
"""
    with open(pl.L(OUT), "x", encoding="utf-8", newline="\n") as f:
        f.write(page)
    with open(os.path.join(VDIR, f"mark_report{a.suffix}.json"), "w", encoding="utf-8") as f:
        json.dump({"판": n, "html": OUT, "표시한곳(전후합)": tot_marked, "못찾은곳(항목)": tot_unplaced, "문장다듬음": tot_sent, "되돌림": tot_rev, "막힘": tot_blocked,
                   "학생자료(보이지 않음)": nstudent, "파일별": report}, f, ensure_ascii=False, indent=1)
    print(OUT)
    print(f"표시 {tot_marked} · 문장 다듬음 {tot_sent} · 되돌림 {tot_rev} · 막힘 {tot_blocked} · 못 찾음 {tot_unplaced}")
    return 0


CSS = r"""
:root{--bg:#f6f7f9;--fg:#1d2330;--muted:#667085;--card:#fff;--line:#d9dee7;--accent:#2457c5;--old:#b42318;--new:#067647;--chip:#eef2ff;--warnbg:#fff6e5;--warnfg:#7a4b00;--page:#fff;--mark:#d40000;--markbg:rgba(212,0,0,.14);--prop:#005ce6;--propbg:rgba(0,92,230,.14);color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#14171d;--fg:#e6e9ef;--muted:#9aa4b2;--card:#1d222b;--line:#323a47;--accent:#8fb0ff;--old:#ff8a80;--new:#6ee7a8;--chip:#26314a;--warnbg:#3a2e14;--warnfg:#ffd68a;--mark:#ff5c5c;--markbg:rgba(255,92,92,.22);--prop:#6aa8ff;--propbg:rgba(106,168,255,.24);color-scheme:dark}}
:root[data-theme="dark"]{--bg:#14171d;--fg:#e6e9ef;--muted:#9aa4b2;--card:#1d222b;--line:#323a47;--accent:#8fb0ff;--old:#ff8a80;--new:#6ee7a8;--chip:#26314a;--warnbg:#3a2e14;--warnfg:#ffd68a;--mark:#ff5c5c;--markbg:rgba(255,92,92,.22);--prop:#6aa8ff;--propbg:rgba(106,168,255,.24);color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 "Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif;padding:0 16px}
header.top,main{max-width:1500px;margin:0 auto}
header.top{padding-block:20px 8px}
h1{font-size:1.6rem;margin:0 0 10px}
.sum{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:8px}
.kv{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 14px;display:flex;gap:10px;align-items:baseline}
.kv span{color:var(--muted)}.kv b{font-size:1.25rem}
.warn{background:var(--warnbg);color:var(--warnfg);border-radius:8px;padding:8px 12px}
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 14px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.sw{display:inline-block;width:22px;height:14px;border:3px solid var(--mark);border-radius:2px;flex:none}.sw.blue{border-color:var(--prop)}
.marknote{border-left:4px solid var(--mark);padding:4px 10px;background:var(--card);border-radius:4px}
nav{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 16px}
nav h3{margin:4px 0}nav ol{margin:4px 0;padding-left:1.4em}nav a{color:var(--accent)}
.muted{color:var(--muted)}
section.gongmun{margin-top:28px}
section.gongmun h2{font-size:1.25rem;margin:0;padding-top:8px;border-top:3px solid var(--accent);overflow-wrap:anywhere}
.orig{margin:2px 0 10px;font-size:.9rem;overflow-wrap:anywhere}
article.file{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin:14px 0}
.fhead{display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap}
.names{flex:1 1 300px;min-width:0;overflow-wrap:anywhere}
.names b{display:inline-block;min-width:1.6em;color:var(--muted)}
.chip{background:var(--chip);border-radius:999px;padding:2px 10px;font-size:.85rem;white-space:nowrap}
.chip.copy,.chip.dup{background:var(--warnbg);color:var(--warnfg)}
.note{margin:8px 0 0;color:var(--warnfg);background:var(--warnbg);border-radius:6px;padding:4px 10px;font-size:.9rem}
.cols,.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.cols{margin-top:12px}
.colh{font-weight:700;text-align:center;background:var(--chip);border-radius:6px;padding:2px}
.pg{font-size:.85rem;color:var(--muted);margin:10px 0 4px}
.cell{min-width:0}
.cell img{display:block;width:100%;height:auto;background:var(--page);border:1px solid var(--line);border-radius:4px;cursor:zoom-in}
.cell.empty{display:flex;align-items:center;justify-content:center;min-height:200px;border:2px dashed var(--line);border-radius:6px;color:var(--muted)}
.stack .pg:first-child{margin-top:0}
.textcell{border:1px solid var(--line);border-radius:6px;background:var(--bg);display:flex;flex-direction:column;min-width:0;margin-top:10px}
.tlabel{font-size:.85rem;color:var(--muted);padding:6px 10px;border-bottom:1px solid var(--line)}
pre.paste{margin:0;padding:10px 12px;font:13.5px/1.65 Consolas,"D2Coding","Malgun Gothic",monospace;white-space:pre-wrap;overflow-wrap:anywhere;tab-size:8}
.card{margin-top:12px;padding:16px;border:2px dashed var(--line);border-radius:8px;color:var(--muted);text-align:center}
.changes{margin-top:12px;border-top:1px solid var(--line);padding-top:8px;font-size:.92rem}
.changes h4{margin:6px 0 4px}.changes h4.sh{color:var(--prop)}.changes ul{margin:0;padding-left:.2em}.changes li{list-style:none;margin:2px 0;overflow-wrap:anywhere}
.loc{color:var(--muted);font-size:.85em}.old{color:var(--old);text-decoration:line-through}.new{color:var(--new);font-weight:600}.why{color:var(--muted);font-size:.85em}
mark.chg{background:var(--markbg);color:inherit;outline:2px solid var(--mark);border-radius:2px;padding:0 1px}
mark.sent{background:var(--propbg);color:inherit;outline:2px solid var(--prop);border-radius:2px;padding:0 1px}
.sold{color:var(--old);text-decoration:line-through}.stag{color:var(--prop)}.otag{color:var(--muted)}.onew{color:var(--fg)}
.off{margin-top:8px;padding:6px 10px;border:1px solid var(--line);border-radius:6px}.off h4{color:var(--muted)}.off .sold{color:var(--muted)}
.off.blk{border-color:var(--warnfg)}.off.blk h4{color:var(--warnfg)}
sup.mn,.num{display:inline-block;color:#fff;font:700 11px/1.35 Arial,sans-serif;border-radius:3px;padding:0 4px;margin-right:2px;vertical-align:baseline;background:var(--mark)}
.sent.num,sup.mn.sent{background:var(--prop)}
sup.mn{font-size:10px;position:relative;top:-.45em}
.num{min-width:1.5em;text-align:center}
.unplaced{margin-top:8px;padding:6px 10px;border:1px dashed var(--mark);border-radius:6px}
.unplaced h4{color:var(--mark)}
.fixcard{text-align:left;margin-top:0;color:var(--fg)}
.fixcard h4{margin:0 0 6px}.fixcard ul{margin:0;padding-left:.2em}.fixcard li{list-style:none;margin:4px 0;overflow-wrap:anywhere}
.totop{position:fixed;right:16px;bottom:calc(16px + env(safe-area-inset-bottom,0px));background:var(--accent);color:#fff;padding:6px 12px;border-radius:999px;text-decoration:none;font-size:.9rem}
.lb{position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:10;overflow:auto;padding:48px 16px 16px;text-align:center}
.lb img{width:auto;max-width:min(1400px,100%);background:#fff;cursor:zoom-out}
.lb button{position:fixed;top:calc(10px + env(safe-area-inset-top,0px));right:16px;font-size:1rem;padding:6px 14px;border-radius:999px;border:0;cursor:pointer}
[hidden]{display:none!important}
@media (max-width:760px){.cols{display:none}.row{grid-template-columns:1fr}
 .row>.cell{position:relative}
 .row>.cell::after{position:absolute;top:6px;left:6px;background:var(--accent);color:#fff;border-radius:4px;padding:0 6px;font-size:.8rem;font-weight:700}
 .row>.cell:first-child::after{content:"__B__"}.row>.cell:last-child::after{content:"__A__"}
 .row>.textcell .tlabel{padding-left:3em}.row>.fixcard{padding-top:16px}.row>.fixcard::after{content:none!important}}
"""

JS = r"""
(function(){var lb=document.getElementById('lb'),im=document.getElementById('lbi'),c=document.getElementById('lbc');
function open(src,alt){im.src=src;im.alt=alt||'';lb.hidden=false;c.focus();}
function close(){lb.hidden=true;im.removeAttribute('src');}
document.addEventListener('click',function(ev){var t=ev.target;if(t.matches('.cell img')){open(t.src,t.alt);}else if(t===c||t===lb||t===im){close();}});
document.addEventListener('keydown',function(ev){if(ev.key==='Escape'&&!lb.hidden)close();if(ev.key==='Enter'&&document.activeElement&&document.activeElement.matches('.cell img'))open(document.activeElement.src,document.activeElement.alt);});
})();
"""

if __name__ == "__main__":
    sys.exit(main())
