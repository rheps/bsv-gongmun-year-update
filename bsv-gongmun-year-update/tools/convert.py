# -*- coding: utf-8 -*-
"""공문 연도 변환 - 하나로 실행하는 명령(배포판).

지난 학년도(또는 더 앞선 해)의 공문과 첨부를 대상 학년도 버전으로 바꾼다.

사용:
  py -3 -E <스킬 폴더>/tools/gongmun.py convert --input <zip·폴더·파일 ...>
      [--target-school-year N] [--allow-unverified-holidays] [--student-data] [--no-verify] [--output 폴더]

- 대상 학년도: 지정이 없으면 실행일이 속한 학년도(3~12월 → 그해, 1~2월 → 전해).
- 공휴일 목록(holidays/<연도>.json)이 없거나 확인되지 않았으면 아무것도 만들지 않고 멈춘다.
- 결과는 첫 입력 옆의 새 폴더 <입력 이름>_올해버전(있으면 _올해버전2, 3 ...)에 쓴다.
  그 안에 바꾼 파일, 검토표.xlsx, 학생자료_변환안함/(학생 자료로 보이는 파일을 그대로 복사), _작업기록/(원본 사본·기록)을 둔다.
- 원본(입력)은 읽기만 한다. 기존 파일을 덮어쓰지 않는다. 문서 내용을 밖으로 보내지 않는다.
"""
import os, sys, re, io, json, shutil, zipfile, hashlib, struct, zlib, argparse, collections
import datetime as dtm

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import dateconv as dc

OUT_SUFFIX = "_올해버전"
RECORDS = "_작업기록"
STUDENT_DIR = "학생자료_변환안함"
B = chr(92)
CONVERTIBLE = (".hwpx", ".docx", ".xlsx", ".odt", ".xls", ".hwp", ".pdf", ".txt", ".md", ".csv")
STUDENT_PATH_WORDS = ["명단", "명렬", "배치", "좌석", "대장", "통지서", "변론서", "의견서", "사안", "등재", "건강상태",
                      "지원 신청", "지원 정산", "징계", "출석부", "가정방문", "숙려", "환불자", "녹취", "참가명단", "등록부", "봉사 지도",
                      "학생생활교육위원회", "생활교육위원회", "선도위원회"]


def MSG():
    """화면 문구(문구.txt)."""
    lab = {}
    with open(os.path.join(HERE, "문구.txt"), encoding="utf-8") as fh:
        text = fh.read()
    for line in text.splitlines():
        m = re.match(r"(\d+)\.\s*(.*)", line.strip())
        if m:
            lab[int(m.group(1))] = m.group(2)
    return lab


def _jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def L(p):
    p = os.path.abspath(p)
    return p if p.startswith(B + B + "?" + B) else B + B + "?" + B + p


def sha(p):
    h = hashlib.sha256()
    with open(L(p), "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel_to(root, p):
    return os.path.relpath(os.path.abspath(p), root).replace(B, "/")


def T():
    """배포판에서 더한 화면 문구(배포문구.json)."""
    return _jload(os.path.join(HERE, "배포문구.json"))


# ------------------------------------------------------------------ 접수
def safe_extract(zpath, dest):
    """zip 풀기: UTF-8 표시가 없는 이름은 cp949로 살리고, 밖으로 나가는 경로·링크는 건너뛴다."""
    os.makedirs(L(dest), exist_ok=False)
    files, skipped = [], []
    destr = os.path.realpath(dest)
    with zipfile.ZipFile(L(zpath)) as zf:
        for i in zf.infolist():
            name = i.filename
            if not (i.flag_bits & 0x800):
                try:
                    name = name.encode("cp437").decode("cp949")
                except Exception:
                    pass
            name = name.replace(B, "/")
            parts = [p.rstrip(" .") for p in name.split("/") if p not in ("", ".")]
            if any(p == ".." for p in parts) or (parts and ":" in parts[0]) or name.startswith("/"):
                skipped.append(name); continue
            if not parts:
                continue
            target = os.path.join(dest, *parts)
            if not os.path.realpath(target).startswith(destr):
                skipped.append(name); continue
            if i.is_dir():
                os.makedirs(L(target), exist_ok=True); continue
            if (i.external_attr >> 16) & 0o170000 == 0o120000:
                skipped.append(name + " (symlink)"); continue
            os.makedirs(L(os.path.dirname(target)), exist_ok=True)
            with zf.open(i) as src, open(L(target), "wb") as f:
                shutil.copyfileobj(src, f)
            files.append("/".join(parts))
    return files, skipped


def intake(inputs, task):
    """입력마다 원본 사본을 작업 폴더에 둔다. 반환: [{n, 종류, 원래위치, 사본, sha256, 풀린곳, 파일수, 건너뜀}]"""
    out = []
    src_root = os.path.join(task, "원본")
    os.makedirs(os.path.join(src_root, "압축해제"), exist_ok=True)
    for n, p in enumerate(inputs, 1):
        p = os.path.abspath(p)
        nn = f"{n:02d}"
        ext_dir = os.path.join(src_root, "압축해제", nn)
        rec = {"n": nn, "원래위치": p, "이름": os.path.basename(p.rstrip(B + "/")), "건너뜀": []}
        if os.path.isdir(p):
            rec["종류"] = "폴더"
            shutil.copytree(L(p), L(ext_dir))
            rec["사본"] = ext_dir; rec["sha256"] = None
        elif p.lower().endswith(".zip"):
            rec["종류"] = "zip"
            digest = sha(p)
            dst = os.path.join(src_root, f"{nn}_{os.path.basename(p)}")
            shutil.copy2(L(p), L(dst))
            if sha(dst) != digest:
                raise RuntimeError("원본 사본 확인값 불일치: " + dst)
            rec["사본"] = dst; rec["sha256"] = digest
            _, rec["건너뜀"] = safe_extract(dst, ext_dir)
        else:
            rec["종류"] = "파일"
            digest = sha(p)
            os.makedirs(L(ext_dir), exist_ok=False)
            dst = os.path.join(ext_dir, os.path.basename(p))
            shutil.copy2(L(p), L(dst))
            if sha(dst) != digest:
                raise RuntimeError("원본 사본 확인값 불일치: " + dst)
            rec["사본"] = dst; rec["sha256"] = digest
        rec["풀린곳"] = ext_dir
        out.append(rec)
    return out


# ------------------------------------------------------------------ 분류(학생 자료·PDF 종류·공문 본문)
def _xmltext(b):
    import html
    s = b.decode("utf-8", "replace")
    s = re.sub(r"<(text:p|text:h|hp:p|w:p|text:line-break|hp:lineBreak|w:br|table:table-row|text:tab)[ />]", "\n<", s)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s)


def _hwp_text(p):
    import olefile
    o = olefile.OleFileIO(L(p))
    try:
        hdr = o.openstream("FileHeader").read()
        flags = struct.unpack("<I", hdr[36:40])[0]
        if flags & 2:
            return ""
        secs = sorted([s for s in o.listdir() if s[0] == "BodyText" and s[1].startswith("Section")], key=lambda s: int(s[1][7:]))
        out = []
        for s in secs:
            data = o.openstream(s).read()
            if flags & 1:
                data = zlib.decompress(data, -15)
            i = 0
            while i + 4 <= len(data):
                h = struct.unpack("<I", data[i:i + 4])[0]; i += 4
                tag, size = h & 0x3ff, (h >> 20) & 0xfff
                if size == 0xfff:
                    size = struct.unpack("<I", data[i:i + 4])[0]; i += 4
                rec = data[i:i + size]; i += size
                if tag == 67:
                    t, j = [], 0
                    while j + 2 <= len(rec):
                        c = struct.unpack("<H", rec[j:j + 2])[0]
                        if c in (1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23, 4, 5, 6, 7, 8, 9, 19, 20):
                            j += 16; continue
                        if c in (10, 13):
                            t.append("\n")
                        elif c >= 32:
                            t.append(chr(c))
                        j += 2
                    out.append("".join(t))
        return "\n".join(out)
    finally:
        o.close()


def quick_text(p, ext):
    """분류용 글자(실패하면 빈 글)."""
    try:
        if ext in (".odt",):
            return _xmltext(zipfile.ZipFile(L(p)).read("content.xml"))
        if ext == ".hwpx":
            zf = zipfile.ZipFile(L(p))
            return "\n".join(_xmltext(zf.read(n)) for n in sorted(zf.namelist()) if re.match(r"Contents/section\d+\.xml", n))
        if ext == ".docx":
            return _xmltext(zipfile.ZipFile(L(p)).read("word/document.xml"))
        if ext == ".xlsx":
            zf = zipfile.ZipFile(L(p))
            return "\n".join(_xmltext(zf.read(n)) for n in zf.namelist() if n == "xl/sharedStrings.xml" or re.match(r"xl/worksheets/sheet\d+\.xml", n))
        if ext == ".hwp":
            return _hwp_text(p)
        if ext == ".pdf":
            import pymupdf as fitz
            d = fitz.open(L(p))
            t = "\n".join(pg.get_text() for pg in d)
            d.close()
            return t
        if ext in (".txt", ".md", ".csv"):
            b = open(L(p), "rb").read()
            for e in ("utf-8-sig", "cp949", "utf-16"):
                try:
                    return b.decode(e)
                except Exception:
                    pass
    except Exception:
        return ""
    return ""


# 본문 학생 식별 신호: 학번(학년 1자리 + 반 01~20 + 번호 01~50) 옆 이름, 학년·반·번 옆 이름, 명단 머리글.
# 날짜(25.10.15.)·금액(12,000·12000원)·전화(010-1234-5678)·문서번호(제10101호)·우편번호는 앞뒤 글자로 걸러낸다.
_SID = r"[1-3](?:0[1-9]|1\d|20)(?:0[1-9]|[1-4]\d|50)"
_SID_RE = re.compile(r"(?<![\d.,\-:/~₩$#제])(?<!우\))(?<!우편번호)(?<!우편번호 )(" + _SID + r")(?![\d.,\-:/%~])")
_NAME = r"[가-힣]{2,4}(?![가-힣])"
_SEP = r"[ \t,|:()\[\]·]{0,3}"
# 이름 자리에 와도 이름이 아닌 낱말(머리글·단위·지역)
_NOT_NAME = {"학생", "학년", "학급", "학번", "번호", "이름", "성명", "명단", "담임", "남자", "여자", "기준", "이상", "이하",
             "예산", "합계", "금액", "단가", "총계", "소계", "만원", "천원", "비고", "학교", "교사", "교실", "번지", "년도",
             "학년도", "회차", "인원", "명이", "명은", "명을", "원이", "원은", "원을", "원정", "년에", "년의", "호실", "번째",
             "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남",
             "참가", "참석", "불참", "지참", "미참", "결석", "지각", "조퇴", "출석", "해당", "없음", "완료", "미정", "신청",
             "제출", "예정", "대상", "확인", "예시",
             "경북", "경남", "제주", "경기도", "강원도", "서울시", "부산시", "대구시", "인천시", "광주시", "대전시", "울산시"}
# 숫자 바로 뒤에 붙은 글자가 이 글자로 시작하면 단위로 본다(10101원, 20240년)
_UNIT_HEAD = set("년원명개건회호번일월쪽권초층억만천백차분시점등위세학리동")
# 숫자·'번' 바로 뒤에 붙은 조사(10101까지, 3번에게)
_PARTICLE_HEAD = set("까부에으은는의과와을를도만째")


def _named(tok):
    return (tok not in _NOT_NAME and not any(tok.startswith(w) for w in ("학년", "학생", "번호", "까지", "부터"))
            and not re.search(r"(?:니다|습니|합니|었다|했다|한다|된다|이다)$", tok))


def student_content(text):
    """본문에서 학생 식별 신호를 센다. 반환: {학번이름, 학년반번이름, 명단머리글, 학번수}"""
    pairs = 0
    for m in re.finditer(_SID_RE.pattern + "(" + _SEP + ")(" + _NAME + ")", text):
        sep, tok = m.group(2), m.group(3)
        if sep == "" and (tok[0] in _UNIT_HEAD or tok[0] in _PARTICLE_HEAD):
            continue
        if _named(tok):
            pairs += 1
    # 이름이 앞에 오는 꼴(홍길동(10101), 홍길동 10101): 이름 앞은 글의 처음·빈칸·문장부호, 학번 뒤는 한글이 아님
    for m in re.finditer(r"(?<![가-힣])([가-힣]{2,4})" + _SEP + _SID_RE.pattern + r"(?![가-힣])", text):
        if _named(m.group(1)):
            pairs += 1
    gcn = 0
    for m in re.finditer(r"(?:[1-3]\s*학년\s*)?\d{1,2}\s*반\s*\d{1,2}\s*번(" + _SEP + ")(" + _NAME + ")", text):
        sep, tok = m.group(1), m.group(2)
        if sep == "" and tok[0] in _PARTICLE_HEAD:
            continue
        if _named(tok):
            gcn += 1
    header = len(re.findall(r"학\s?번|번호\s*[\t |,]*\s*(?:이름|성명)(?![가-힣])", text))
    ids = len(_SID_RE.findall(text))
    return {"학번이름": pairs, "학년반번이름": gcn, "명단머리글": header, "학번수": ids}


def student_signals(path, text):
    sc = len(re.findall(r"\d\s*반\s*\d{1,2}\s*번|학번", text))
    rrn = len(re.findall(r"(?<!\d)\d{6}\s*-\s*[1-4]\d{6}(?!\d)", text))
    phone = len(re.findall(r"(?<![\d.,])01[016789]-?\d{3,4}-?\d{4}(?![\d.,])", text))  # 긴 숫자 속 부분은 세지 않음
    words = [k for k in STUDENT_PATH_WORDS if k in path]
    c = student_content(text)
    content_hit = bool(c["학번이름"] or c["학년반번이름"] or (c["명단머리글"] and c["학번수"] >= 2))
    return {"반번": sc, "주민번호": rrn, "휴대폰": phone, "이름낱말": words, "본문": c,
            "학생정보": bool(sc >= 3 or rrn or phone >= 2 or words or content_hit)}


def pdf_kind(p):
    try:
        import pymupdf as fitz
        d = fitz.open(L(p))
        n = max(len(d), 1)
        chars = sum(len(re.sub(r"\s", "", pg.get_text())) for pg in d)
        d.close()
        return "글자" if chars >= 50 * n else "스캔"
    except Exception:
        return "스캔"


def plan(intakes, all_student):
    items, seen = [], {}
    for rec in intakes:
        base = rec["풀린곳"]
        for dp, dn, fn in os.walk(L(base)):
            dn.sort(); fn.sort()
            for f in fn:
                full = os.path.join(dp, f)
                rel = os.path.relpath(full, L(base)).replace(B, "/")
                items.append({"zip": rec["n"], "rel": rel, "abs": full, "입력이름": rec.get("이름", "")})
    seq = collections.Counter()
    for it in items:
        it["sha256"] = sha(it["abs"])
        it["ext"] = os.path.splitext(it["rel"])[1].lower()
        seq[it["zip"]] += 1
        it["기록id"] = f"파일-{it['zip']}-{seq[it['zip']]:04d}"
        text = quick_text(it["abs"], it["ext"]) if it["ext"] in CONVERTIBLE else ""
        # 낱말은 zip·폴더 이름까지 본다(예: '학생생활교육위원회' zip 안의 파일은 모두 학생 자료)
        sig = student_signals(it.get("입력이름", "") + "/" + it["rel"], text)
        it["학생신호"] = {k: v for k, v in sig.items() if k != "학생정보"}
        it["학생정보"] = bool(all_student or sig["학생정보"])
        it["pdf종류"] = pdf_kind(it["abs"]) if it["ext"] == ".pdf" else None
        it["공문본문"] = it["ext"] == ".odt" and bool(re.search(r"(?m)^\s*제목\s*$", text)) and bool(re.search(r"(?m)^\s*시행\s*$", text))
        if it["sha256"] in seen:
            it["중복원본"] = seen[it["sha256"]]
        else:
            seen[it["sha256"]] = it["zip"] + "/" + it["rel"]
    keys = {(it["zip"], os.path.splitext(it["rel"])[0]) for it in items if it["ext"] == ".hwp"}
    for it in items:
        if it["ext"] == ".docx" and (it["zip"], os.path.splitext(it["rel"])[0]) in keys:
            it["hwp파생"] = os.path.splitext(it["rel"])[0] + ".hwp"
    return items


# ------------------------------------------------------------------ 기록
def dump(obj, path):
    os.makedirs(L(os.path.dirname(path)), exist_ok=True)
    if os.path.exists(L(path)):
        raise RuntimeError("이미 있는 파일 - 덮어쓰지 않음: " + path)
    with open(L(path), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)


def default_output(first_input):
    """첫 입력 옆 <이름>_올해버전. 이미 있으면 _올해버전2, 3 ..."""
    p = os.path.abspath(first_input).rstrip(B + "/")
    name = os.path.basename(p)
    if not os.path.isdir(p):
        name = os.path.splitext(name)[0]
    base = os.path.join(os.path.dirname(p), name + OUT_SUFFIX)
    out, k = base, 2
    while os.path.exists(L(out)):
        out = f"{base}{k}"; k += 1
    return out


def scan_exts(inputs):
    """한글이 필요한지 미리 보려고 입력 안 파일 확장자를 모은다(zip은 목록만 읽음)."""
    exts = set()
    for p in inputs:
        if os.path.isdir(p):
            for _, _, fn in os.walk(L(p)):
                exts |= {os.path.splitext(f)[1].lower() for f in fn}
        elif p.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(L(p)) as zf:
                    exts |= {os.path.splitext(n)[1].lower() for n in zf.namelist()}
            except Exception:
                pass
        else:
            exts.add(os.path.splitext(p)[1].lower())
    return exts


def default_rules():
    """사용자 표시 규칙 파일(있으면): 사용자 폴더/.bsv-gongmun-year-update/표시규칙.json"""
    return os.path.join(os.path.expanduser("~"), ".bsv-gongmun-year-update", "표시규칙.json")


def main(argv=None):
    ap = argparse.ArgumentParser(description="지난 공문·첨부를 대상 학년도 버전으로 바꾼다")
    ap.add_argument("--input", nargs="+", required=True, help="zip, 폴더 또는 파일(여러 개 가능)")
    ap.add_argument("--output", help="결과 폴더(없는 폴더여야 함). 기본: 첫 입력 옆 <이름>_올해버전")
    ap.add_argument("--target-school-year", type=int)
    ap.add_argument("--run-date", help="YYYY-MM-DD (시험용, 기본 오늘)")
    ap.add_argument("--allow-unverified-holidays", action="store_true")
    ap.add_argument("--student-data", action="store_true", help="입력 전체를 학생 자료로 다룸(바꾸지 않고 그대로 복사)")
    ap.add_argument("--no-verify", action="store_true", help="한글·LibreOffice로 여는 확인을 건너뜀")
    ap.add_argument("--holiday-dir", default=os.path.join(HERE, "holidays"))
    ap.add_argument("--flag-rules", help="학교별 표시 규칙 파일(기본: 사용자 폴더/.bsv-gongmun-year-update/표시규칙.json, 있으면)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    M = MSG()
    TT = T()
    import office

    inputs = []
    for p in a.input:
        if not os.path.exists(p):
            print(M[129].replace("{PATH}", os.path.abspath(p)), flush=True)
            return 3
        inputs.append(os.path.abspath(p))

    run_date = dtm.date.fromisoformat(a.run_date) if a.run_date else dtm.date.today()
    tsy = dc.resolve_target_sy(run_date, a.target_school_year)
    try:
        hol_warn = dc.configure(tsy, holiday_dir=a.holiday_dir, allow_unverified=a.allow_unverified_holidays)
    except dc.HolidayDataError as e:
        print(M[111].replace("{MESSAGE}", str(e)), flush=True)
        return 2
    # 한글: hwp·PDF를 바꾸거나 hwpx를 열어 확인하려면 꼭 있어야 한다
    exts = scan_exts(inputs)
    need_hwp = bool(exts & {".hwp", ".pdf"}) or (not a.no_verify and ".hwpx" in exts)
    if need_hwp and not a.student_data and not office.hwp_available():
        print(TT["d.hwp_missing"], flush=True)
        return 4
    rules_path = a.flag_rules or default_rules()
    rules_used = None
    if os.path.exists(rules_path):
        dc.add_flag_terms(_jload(rules_path).get("분류별낱말", {}))
        rules_used = rules_path
    else:
        dc.add_flag_terms({})

    out = os.path.abspath(a.output) if a.output else default_output(inputs[0])
    if os.path.exists(L(out)):
        print(TT["d.out_exists"].replace("{PATH}", out), flush=True)
        return 5
    for p in inputs:  # 결과 폴더를 입력 폴더 안에 만들지 않는다(다시 실행하면 결과가 입력에 섞임)
        if os.path.isdir(p) and (out + os.sep).startswith(os.path.join(p, "")):
            print(TT["d.out_exists"].replace("{PATH}", out), flush=True)
            return 5

    import pipeline, verify, build_review
    now = dtm.datetime.now(dtm.timezone(dtm.timedelta(hours=9)))
    rid = now.strftime("%Y%m%d-%H%M%S-%f")
    task = os.path.join(out, RECORDS)
    out_student = os.path.join(out, STUDENT_DIR)
    tmp = os.path.join(task, "임시")
    os.makedirs(L(task))
    os.makedirs(L(tmp))
    print(M[131].replace("{PATH}", out), flush=True)

    intakes = intake(inputs, task)
    items = plan(intakes, a.student_data)
    group_dir = {}
    for rec in intakes:
        stem = os.path.splitext(rec["이름"])[0] if rec["종류"] != "폴더" else rec["이름"]
        if len(intakes) == 1:
            group_dir[rec["n"]] = ""   # 입력이 하나면 결과 폴더 바로 아래에 둔다
        else:
            group_dir[rec["n"]] = f"{rec['n']}_{pipeline.conv_name(stem, tsy - 1, 1)[0]}"
    dump({"실행ID": rid, "입력": [{k: v for k, v in r.items()} for r in intakes],
          "files": [{k: v for k, v in it.items() if k != "abs"} for it in items]}, os.path.join(task, "기록", "파일목록.json"))

    pipeline.init(tsy, out, out_student, tmp, group_dir)
    try:
        results = pipeline.run(items, progress=not a.quiet)
        vrows = verify.run(results, tmp, use_office=not a.no_verify)
    finally:
        shutil.rmtree(L(tmp), ignore_errors=True)

    info = {"실행ID": rid, "대상학년도": tsy,
            "정한방법": ("직접 지정(--target-school-year)" if a.target_school_year else f"실행일 {run_date.isoformat()}이 속한 학년도"),
            "대상기간": f"{tsy}-03-01 ~ {(dtm.date(tsy + 1, 3, 1) - dtm.timedelta(days=1)).isoformat()}",
            "실행일": run_date.isoformat(), "공휴일자료": dc.HOLIDAY_INFO, "공휴일경고": hol_warn,
            "미확인공휴일허용": a.allow_unverified_holidays, "원래연도범위": [dc.SRC_LO, dc.SRC_HI],
            "표시규칙파일": rules_used, "열기확인": not a.no_verify,
            "한글": office.hwp_available(), "LibreOffice": bool(office.soffice()), "외부전송": "없음"}
    dump(results, os.path.join(task, "기록", "결과기록.json"))
    dump(vrows, os.path.join(task, "기록", "검증기록.json"))
    dump(info, os.path.join(task, "기록", "실행정보.json"))

    normal = [r for r in results if not r.get("학생정보")]
    student = [r for r in results if r.get("학생정보")]
    review = build_review.build(normal, vrows, info, os.path.join(out, "검토표.xlsx"), out,
                                student_count=len(student), holiday_dir=a.holiday_dir)
    status = dict(collections.Counter(r["상태"] for r in results))
    vsum = verify.summary(vrows)
    copied = [r["zip"] + "/" + r["rel"] for r in normal if r.get("그대로복사")]
    kept_pdf = [{"파일": r["zip"] + "/" + r["rel"], "고칠날짜": [{k: x.get(k) for k in ("쪽", "원문", "새글", "원래날짜", "새날짜", "새요일")}
                                                         for x in r.get("고칠날짜", [])]}
                for r in normal if r.get("상태") == "원본 유지(서식 PDF)"]
    dump({"상태별": status, "학생자료파일": len(student), "그대로복사(학생자료 제외)": copied,
          "검토표": review, "열기확인": vsum, "원본유지서식PDF": kept_pdf}, os.path.join(task, "기록", "변환요약.json"))

    # 화면 요약
    print(M[134].replace("{N}", str(len(results))), flush=True)
    for st, k in build_review.STAT.items():
        if status.get(st):
            print(f"  {build_review.stat_label(st, M)}: {status[st]}", flush=True)
    if kept_pdf:
        print(M[144], flush=True)
        for kp in kept_pdf:
            print("  " + kp["파일"], flush=True)
            for x in kp["고칠날짜"]:
                print("    " + M[143].replace("{N}", str(x["쪽"])) + f": {x['원문'].strip()} → {x['새글'].strip()}", flush=True)
    print(M[131].replace("{PATH}", out), flush=True)
    print(M[133].replace("{PATH}", os.path.join(out, "검토표.xlsx")), flush=True)
    if student:
        print(TT["d.student_console"].replace("{N}", str(len(student))).replace("{PATH}", out_student), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
