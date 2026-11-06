# -*- coding: utf-8 -*-
"""윤문(교정) 단계 공용 함수: 읽을 글 뽑기, 검사(guard), 적용.

윤문 판단은 에이전트가 한다(SKILL.md). 이 파일은 그 앞뒤의 기계 작업만 한다.
- 본문 뽑기: 변환한 파일에서 문단(hwpx/docx/odt) 또는 줄(txt)을 위치 id와 함께 뽑는다.
- 검사: 윤문.json 항목이 숫자·날짜·금액·이름·고유명사·「」·따옴표 안 글·OOOO 자리·뜻을 가진 낱말을
  바꾸지 않는지 본다. 규칙은 아래 check_entry 설명과 SKILL.md에 있다.
- 적용: 통과한 항목을 모두 변환본에 넣은 새 파일(<이름>_윤문<N><확장자>)을 만든다(되돌린 항목만 뺌). 원래 변환본은 그대로 둔다.

화면·검토표 문구는 이 폴더의 윤문문구.json에서 읽는다.
"""
import io, os, re, json, zipfile, copy, collections, datetime as dt
from lxml import etree

import xmlconv

HERE = os.path.dirname(os.path.abspath(__file__))
RECORDS = "_작업기록"

KINDS = ("확정", "제안")
CAT_CONFIRM = ("오타", "맞춤법", "띄어쓰기", "공문서표기")
CAT_PROPOSE = ("비문", "어색한표현")
CATEGORIES = CAT_CONFIRM + CAT_PROPOSE
# 설계 결정: 검사를 통과한 항목은 구분(확정·제안)과 관계없이 모두 적용한다.
# 구분은 검사 규칙만 가른다(제안 = 문장 다듬기 규칙). 색은 고친 종류만 알린다.


def colour_of(e):
    """빨강 = 날짜·오타·맞춤법·띄어쓰기·공문서표기, 파랑 = 문장 다듬음(비문·어색한표현)."""
    return "blue" if e.get("category") in CAT_PROPOSE else "red"

# 윤문할 XML 부분(머리말·본문). xlsx는 숫자·표 위주라 윤문하지 않는다.
PROOF_PARTS = {
    "hwpx": re.compile(r"^Contents/section\d+\.xml$"),
    "docx": re.compile(r"^word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$"),
    "odt": re.compile(r"^(content|styles)\.xml$"),
}
TEXT_EXT = (".txt", ".md")
HANGUL = re.compile(r"[가-힣]")


def L(p):
    p = os.path.abspath(p)
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


def labels():
    with open(os.path.join(HERE, "윤문문구.json"), encoding="utf-8") as f:
        return json.load(f)


def jload(p):
    with open(L(p), encoding="utf-8") as f:
        return json.load(f)


def jdump(obj, p, overwrite=False):
    if os.path.exists(L(p)) and not overwrite:
        raise RuntimeError("이미 있음 - 덮어쓰지 않음: " + p)
    os.makedirs(L(os.path.dirname(p)), exist_ok=True)
    with open(L(p), "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


class Run:
    """결과 폴더(<입력>_올해버전) 경로 모음. 기록은 그 안 _작업기록/에 있다."""

    def __init__(self, result_dir):
        self.out = os.path.abspath(result_dir)
        self.hub = self.out                      # 기록 속 파일 경로의 기준
        self.id = os.path.basename(self.out.rstrip("/" + chr(92)))
        self.work = os.path.join(self.out, RECORDS)
        self.rec_path = os.path.join(self.work, "기록", "결과기록.json")
        if not os.path.isfile(L(self.rec_path)):
            with open(os.path.join(HERE, "배포문구.json"), encoding="utf-8") as f:
                raise SystemExit(json.load(f)["d.not_result"].replace("{PATH}", self.out))
        self.dir = os.path.join(self.work, "윤문")
        self.list_json = os.path.join(self.dir, "본문목록.json")
        self.list_txt = os.path.join(self.dir, "본문목록.txt")
        self.entries = os.path.join(self.dir, "윤문.json")
        self.check_json = os.path.join(self.dir, "윤문_검사.json")
        self.versions = os.path.join(self.dir, "적용기록.json")
        self.review = self.work                  # 캡처 그림과 표시 기록(_작업기록/캡처/)

    def records(self):
        return jload(self.rec_path)


# ------------------------------------------------------------------ 글 읽기·쓰기
def decode_text(data):
    """(글, 인코딩, BOM 여부). 글은 원래 줄바꿈(\r\n)을 그대로 둔다."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16"), "utf-16", True
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8"), "utf-8", True
    try:
        return data.decode("utf-8"), "utf-8", False
    except UnicodeDecodeError:
        return data.decode("cp949"), "cp949", False


def encode_text(s, enc, bom):
    if enc == "utf-16":
        return s.encode("utf-16")
    b = s.encode(enc)
    return (b"\xef\xbb\xbf" + b) if (bom and enc == "utf-8") else b


def text_lines(s):
    """[(줄 번호, 시작 위치, 줄 글(줄바꿈 뺌))]"""
    out, pos = [], 0
    for i, ln in enumerate(s.splitlines(keepends=True), 1):
        body = ln.rstrip("\r\n")
        out.append((i, pos, body))
        pos += len(ln)
    return out


def zip_paragraphs(data, mode):
    """[(위치 id, 사람이 읽는 위치, 글)] - 위치 id는 '<XML 부분>#<빈 문단을 뺀 순번>'."""
    out = []
    z = zipfile.ZipFile(io.BytesIO(data))
    for name in z.namelist():
        if not PROOF_PARTS[mode].match(name):
            continue
        root = etree.fromstring(z.read(name), etree.XMLParser(remove_blank_text=False, huge_tree=True))
        n = 0
        for p in root.iter(*xmlconv.MODES[mode]["P"]):
            segs = xmlconv.segments(p, mode)
            txt = "".join(xmlconv._get(e, a) for e, a in segs)
            if not txt.strip():
                continue
            n += 1
            out.append((f"{name}#{n}", f"{xmlconv.where_of(p, mode, name)} {n}번째 문단", txt))
    return out


def file_mode(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in TEXT_EXT:
        return "txt"
    if ext in (".hwpx", ".docx", ".odt"):
        return ext[1:]
    return None


def paragraphs_of(path):
    """파일 → {위치 id: (사람이 읽는 위치, 글)}"""
    with open(L(path), "rb") as f:
        data = f.read()
    mode = file_mode(path)
    if mode == "txt":
        s, _, _ = decode_text(data)
        return {f"줄 {i}": (f"{i}번째 줄", body) for i, _, body in text_lines(s) if body.strip()}
    if mode:
        return {loc: (w, t) for loc, w, t in zip_paragraphs(data, mode)}
    return {}


# ------------------------------------------------------------------ 어떤 파일을 읽을지
def skip_reason(r):
    """윤문하지 않을 파일이면 문구 키, 읽을 파일이면 None."""
    if r.get("학생정보"):
        return "s.student"
    st = r.get("상태") or ""
    if st.startswith("중복"):
        return "s.dup"
    if st not in ("변환 완료", "일부"):
        return "s.status"
    outs = r.get("결과") or []
    if any("(OCR 변환)" in os.path.basename(o) for o in outs) or any(f.get("분류") == "OCR 확인 필요" for f in r.get("표시", [])):
        return "s.ocr"
    if not outs:
        return "s.noresult"
    if all(os.path.splitext(o)[1].lower() in (".xlsx", ".xls", ".csv") for o in outs):
        return "s.sheet"
    if not any(file_mode(o) for o in outs):
        return "s.noresult"
    return None


def proof_target(r):
    for o in r.get("결과") or []:
        if file_mode(o):
            return o
    return None


PROTECT_CATS = {"사람 이름 가능", "이전 학교 정보", "교육지원청·관계 기관", "표어", "주소·우편번호", "전화·팩스",
                "홈페이지·메일", "문서번호·시행번호", "금액", "업체 이름", "관련 문서·법령 날짜", "관련 안 법령 인용", "회차"}
PARTICLE_END = re.compile(r"(으로|에서|에게|께서|이|가|은|는|을|를|의|에|도|와|과|로)$")


def protected_terms(r):
    """변환 도구가 「확인할 곳」으로 적은 이름·기관·금액·문서번호 등. 윤문에서 바꾸면 안 된다."""
    out = set()
    for f in r.get("표시", []):
        if f.get("분류") not in PROTECT_CATS:
            continue
        for m in re.finditer(r"「([^」]+)」", f.get("설명", "")):
            t = re.sub(r"\s+", "", m.group(1))
            if len(t) > 2:
                t = PARTICLE_END.sub("", t) or t
            if len(t) >= 2:
                out.add(t)
    return sorted(out)


# ------------------------------------------------------------------ 검사(guard)
_KIWI = None
KIWI_MISSING = False   # kiwipiepy를 쓸 수 없으면 True(낱말 검사는 조사를 떼어 세는 단순한 규칙으로 함)


def _kiwi():
    global _KIWI, KIWI_MISSING
    if _KIWI is None and not KIWI_MISSING:
        try:
            from kiwipiepy import Kiwi
            _KIWI = Kiwi()
        except Exception:
            KIWI_MISSING = True
    return _KIWI


def nouns(s):
    """뜻을 가진 낱말(명사·고유명사·어근·외국어·한자) 모음. kiwipiepy가 없으면 낱말에서 조사를 떼어 셈."""
    k = _kiwi()
    if k is not None:
        return collections.Counter(t.form for t in k.tokenize(s) if t.tag in ("NNG", "NNP", "XR", "SH", "SL"))
    # kiwipiepy가 없을 때의 단순한 규칙: 조사를 떼고, '-하다·-되다'처럼 붙은 꼴은 그 앞 어근만 센다.
    # 형태소 분석보다 거칠어서 통과해야 할 문장 다듬기를 더 자주 막을 수 있다(위험한 쪽으로는 느슨해지지 않음).
    c = collections.Counter()
    for w in re.findall(r"[가-힣]+", s):
        if w in FALLBACK_SKIP:
            continue
        while len(w) > 2 and PARTICLE_END.search(w):   # 조사가 겹친 꼴(지도를 → 지도 → 지)도 같은 어근으로 맞춤
            w = PARTICLE_END.sub("", w)
        m = re.search(r"(?<=..)(하|해|되|돼|시키)", w)
        if m:
            w = w[:m.start()]
        if len(w) >= 2 and w not in FALLBACK_SKIP:
            c[w] += 1
    return c


FALLBACK_SKIP = {"주시기", "주십시오", "바랍니다", "있습니다", "합니다", "됩니다", "있도록", "같이", "위하여", "대하여", "따라", "통하여", "있는", "있고"}


def proper_nouns(s):
    k = _kiwi()
    if k is not None:
        return collections.Counter(t.form for t in k.tokenize(s) if t.tag == "NNP")
    return collections.Counter()


# 문장을 다듬을 때 빠지거나 생겨도 뜻이 바뀌지 않는 형식 명사
REMOVABLE = {"것", "수", "등", "경우", "관련", "해당", "바", "때문", "데", "중", "측면", "부분", "사항", "부분", "통해",
             "대하", "위하", "진행", "실시", "적극"}
WS = re.compile(r"\s+")
PUNCT = re.compile(r"[\s.,:;·‧ㆍ~\-–—()\[\]<>/!?'\"‘’“”…]")
QUOTES = re.compile(r"「[^」]*」|『[^』]*』|“[^”]*”|‘[^’]*’|\"[^\"]*\"|'[^']*'")
PLACE = re.compile(r"[OＯ○◯]{2,}")
NEG = {"안않": re.compile(r"[안않]"), "못": re.compile(r"못"), "없": re.compile(r"없"), "아니": re.compile(r"아니"),
       "금지": re.compile(r"금지"), "불가": re.compile(r"불가")}


def nows(s):
    return WS.sub("", s or "")


def lev(a, b):
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def other_chars(s):
    """한글·빈칸·문장부호를 뺀 나머지(숫자, 영문, @ 등) - 어떤 윤문에서도 바뀌면 안 된다."""
    return [c for c in s if not (HANGUL.match(c) or PUNCT.match(c))]


def notation_core(s):
    """공문서표기 비교용: 숫자 뒤 년·월·일·시·분과 빈칸·문장부호를 뺀 글
    (2026년 3월 5일 → 2026. 3. 5., 12시 40분 → 12:40). '1시간'의 '시'는 빼지 않는다."""
    s = re.sub(r"(\d)\s*(년|월|일|시(?!간)|분)", r"\1", s)
    return PUNCT.sub("", s)


def check_entry(e, para, protect):
    """한 항목 검사. 반환: [(문구 키, 덧붙일 말)] - 비어 있으면 통과.

    모든 항목: before가 그 위치 글에 꼭 한 번 있어야 하고, 숫자·영문·기호 차례, 「」·따옴표 안 글,
    OOOO 자리, 변환 도구가 적은 보호어(이름·기관·금액·문서번호), 부정 표현(안·않·못·없·아니·금지·불가) 수가 같아야 한다.
    확정: 띄어쓰기는 빈칸만, 공문서표기는 빈칸·문장부호·숫자 뒤 년월일시분만 바꿀 수 있다.
          오타·맞춤법은 빈칸을 뺀 글의 편집 거리가 2 이하(그리고 길이의 4분의 1 이하)이고 고유명사가 같아야 한다.
    제안(비문·어색한표현): 뜻을 가진 낱말(명사·고유명사·어근)이 새로 생기거나, 늘거나, 모두 없어지면 안 된다
          (문단 전체로 세고, 것·수·등 같은 형식 명사는 뺌). 겹쳐 쓴 낱말을 하나로 줄이는 것(계획을 ~ 계획하여 → ~를 ~ 계획하여)은 된다.
    """
    bad = []
    kind, cat = e.get("kind"), e.get("category")
    b, a = e.get("before") or "", e.get("after") if e.get("after") is not None else ""
    if kind not in KINDS:
        bad.append(("g.kind", ""))
    if cat not in CATEGORIES:
        bad.append(("g.category", ""))
    if kind == "확정" and cat in CAT_PROPOSE:
        bad.append(("g.sentence_confirmed", ""))
    if para is None:
        return bad + [("g.no_location", "")]
    if not b:
        return bad + [("g.not_found", "")]
    cnt = para.count(b)
    if cnt == 0:
        return bad + [("g.not_found", "")]
    if cnt > 1:
        bad.append(("g.many", ""))
    if a == b:
        bad.append(("g.same", ""))
    if other_chars(b) != other_chars(a):
        bad.append(("g.digits", ""))
    if QUOTES.findall(b) != QUOTES.findall(a) or (b.count("「") != a.count("「")):
        bad.append(("g.quote", ""))
    if PLACE.findall(b) != PLACE.findall(a) or re.findall(r"OO\.\s*OO\.", b) != re.findall(r"OO\.\s*OO\.", a):
        bad.append(("g.placeholder", ""))
    nb, na = nows(b), nows(a)
    lost = [t for t in protect if nb.count(t) != na.count(t)]
    if lost:
        bad.append(("g.protected", ", ".join(lost)))
    if any(len(rx.findall(nb)) != len(rx.findall(na)) for rx in NEG.values()):
        bad.append(("g.negation", ""))
    if cat == "띄어쓰기":
        if nb != na:
            bad.append(("g.spacing_only", ""))
    elif cat == "공문서표기":
        if notation_core(b) != notation_core(a):
            bad.append(("g.notation_only", ""))
    elif cat in ("오타", "맞춤법"):
        d = lev(nb, na)
        if d > 2 or d > max(1, len(nb) // 4):
            bad.append(("g.edit_far", ""))
        pb, pa = proper_nouns(b), proper_nouns(a)
        if pb != pa:
            bad.append(("g.protected", ", ".join(sorted(set((pb - pa) + (pa - pb))))))
    elif cat in CAT_PROPOSE:
        x, y = nouns(para), nouns(para.replace(b, a, 1))   # 문단 전체로 셈: 겹친 낱말을 줄여도 문단에 남아 있으면 됨
        for k in REMOVABLE:
            x.pop(k, None); y.pop(k, None)
        diff = sorted((set(x) ^ set(y)) | {k for k in y if y[k] > x.get(k, 0)})
        if diff:
            bad.append(("g.nouns", ", ".join(diff)))
        if na and not (0.5 <= len(na) / max(1, len(nb)) <= 1.6):
            bad.append(("g.length", ""))
    return bad


def check_all(run, entries, plist=None):
    """반환: (통과 항목 목록, 막힌 항목 목록[(항목, [(키, 말)])])"""
    plist = plist if plist is not None else jload(run.list_json)
    files = {f["기록id"]: f for f in plist["파일"]}
    recs = {r["기록id"]: r for r in run.records()}
    paras_cache, ok, bad, seen_ids, spans = {}, [], [], set(), collections.defaultdict(list)
    for e in entries:
        reasons = []
        eid = e.get("id")
        if not eid or eid in seen_ids:
            reasons.append(("g.id_dup", str(eid)))
        seen_ids.add(eid)
        f = files.get(e.get("file"))
        if f is None:
            bad.append((e, reasons + [("g.no_file", "")]))
            continue
        if f["기록id"] not in paras_cache:
            paras_cache[f["기록id"]] = paragraphs_of(os.path.join(run.hub, f["파일"]))
        pr = paras_cache[f["기록id"]].get(e.get("location"))
        reasons += check_entry(e, pr[1] if pr else None, protected_terms(recs.get(f["기록id"], {})))
        if not reasons:
            i = pr[1].find(e["before"])
            sp = (i, i + len(e["before"]))
            key = (f["기록id"], e["location"])
            if any(not (sp[1] <= s or sp[0] >= t) for s, t in spans[key]):
                reasons.append(("g.overlap", ""))
            else:
                spans[key].append(sp)
        (bad.append((e, reasons)) if reasons else ok.append(e))
    return ok, bad


# ------------------------------------------------------------------ 적용
def replace_in_text(s, changes):
    """changes: {위치 id: [(before, after)]} - 줄 단위로 바꾼 새 글."""
    lines = text_lines(s)
    reps = []
    for i, start, body in lines:
        for b, a in changes.get(f"줄 {i}", []):
            k = body.find(b)
            if k < 0:
                raise RuntimeError(f"줄 {i}: 바꿀 글을 찾지 못함")
            reps.append((start + k, start + k + len(b), a))
    for a0, b0, new in sorted(reps, key=lambda r: -r[0]):
        s = s[:a0] + new + s[b0:]
    return s


def replace_in_zip(data, mode, changes):
    zin = zipfile.ZipFile(io.BytesIO(data))
    outb = io.BytesIO()
    zout = zipfile.ZipFile(outb, "w")
    done = 0
    for info in zin.infolist():
        raw = zin.read(info.filename)
        new = None
        if PROOF_PARTS[mode].match(info.filename) and any(k.startswith(info.filename + "#") for k in changes):
            root = etree.fromstring(raw, etree.XMLParser(remove_blank_text=False, huge_tree=True))
            n = 0
            for p in root.iter(*xmlconv.MODES[mode]["P"]):
                segs = xmlconv.segments(p, mode)
                txt = "".join(xmlconv._get(el, at) for el, at in segs)
                if not txt.strip():
                    continue
                n += 1
                ch = changes.get(f"{info.filename}#{n}")
                if not ch:
                    continue
                reps, want = [], txt
                for b, a in ch:
                    k = txt.find(b)
                    if k < 0:
                        raise RuntimeError(f"{info.filename}#{n}: 바꿀 글을 찾지 못함")
                    reps.append((k, k + len(b), a))
                for a0, b0, nw in sorted(reps, key=lambda r: -r[0]):
                    want = want[:a0] + nw + want[b0:]
                xmlconv.apply_reps(segs, reps)
                got = "".join(xmlconv._get(el, at) for el, at in segs)
                if got != want:
                    raise RuntimeError(f"{info.filename}#{n}: 글 다시 맞추기 불일치")
                done += len(ch)
            di = root.getroottree().docinfo
            new = etree.tostring(root, xml_declaration=True, encoding=di.encoding or "UTF-8", standalone=di.standalone)
        zout.writestr(copy.copy(info), new if new is not None else raw, compress_type=info.compress_type)
    zout.close()
    if done != sum(len(v) for v in changes.values()):
        raise RuntimeError("적용하지 못한 항목이 있음")
    return outb.getvalue()


def apply_to_file(src, changes):
    """원래 변환본 src에 changes를 넣은 새 내용(bytes)."""
    with open(L(src), "rb") as f:
        data = f.read()
    mode = file_mode(src)
    if mode == "txt":
        s, enc, bom = decode_text(data)
        return encode_text(replace_in_text(s, changes), enc, bom)
    return replace_in_zip(data, mode, changes)


def version_path(src, n):
    stem, ext = os.path.splitext(src)
    return f"{stem}_윤문{n}{ext}"


def today():
    return dt.date.today().isoformat()
