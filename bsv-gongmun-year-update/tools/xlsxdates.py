# -*- coding: utf-8 -*-
"""(v3) 엑셀(xlsx) 숫자 날짜 칸 바꾸기 - 날짜는 dateconv.configure로 정한 대상 학년도로 옮긴다.
 - openpyxl 없이 XML만 읽고 쓴다(읽지 못하던 파일도 처리).

- 날짜 서식이 걸린 숫자 칸(엑셀 일련번호): 날짜로 바꿔 규칙 적용 → 같은 서식의 일련번호로 다시 씀
- 날짜 서식이 없는 20250314 / 250314 같은 숫자: 같은 열 제목(위 5행)에 날짜 낱말이 있을 때만 바꿈, 없으면 표시만
- 수식 칸은 값이 계산되므로 바꾸지 않고 표시
"""
import io, re, zipfile, datetime as dtm
from lxml import etree
import dateconv as dc

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
X = "{%s}" % NS
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
BUILTIN_DATE = set(range(14, 23)) | set(range(27, 37)) | set(range(45, 48)) | set(range(50, 59))
HEAD_WORDS = re.compile(r"일자|날짜|일시|기간|작성일|기준일|발행일|접수일|시행일|등록일|일$|date", re.I)
HEAD_BAD = re.compile(r"생년월일|생일|출생")
EPOCH = dtm.date(1899, 12, 30)


def _is_date_code(code):
    c = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", code or "")
    return bool(re.search(r"[yYdD]", c)) or bool(re.search(r"m{1,4}", c) and re.search(r"[yYdD]", c))


def col_of(ref):
    return re.match(r"[A-Z]+", ref).group(0)


def make_hooks(data, years, log):
    z = zipfile.ZipFile(io.BytesIO(data))
    names = set(z.namelist())
    date_styles = set()
    if "xl/styles.xml" in names:
        st = etree.fromstring(z.read("xl/styles.xml"))
        custom = {int(n.get("numFmtId")): n.get("formatCode") for n in st.iter(X + "numFmt")}
        xfs = st.find(X + "cellXfs")
        if xfs is not None:
            for i, xf in enumerate(xfs.findall(X + "xf")):
                fid = int(xf.get("numFmtId", "0"))
                if fid in BUILTIN_DATE or (fid in custom and _is_date_code(custom[fid])):
                    date_styles.add(i)
    sst = []
    if "xl/sharedStrings.xml" in names:
        for si in etree.fromstring(z.read("xl/sharedStrings.xml")).findall(X + "si"):
            sst.append("".join(t.text or "" for t in si.iter(X + "t")))
    hooks = {}
    for n in names:
        if not re.match(r"^xl/worksheets/sheet\d+\.xml$", n):
            continue

        def hook(b, lg, n=n):
            root = etree.fromstring(b)
            heads = {}
            for c in root.iter(X + "c"):
                ref = c.get("r") or ""
                m = re.match(r"([A-Z]+)(\d+)", ref)
                if not m or int(m.group(2)) > 5:
                    continue
                txt = ""
                if c.get("t") == "s":
                    v = c.find(X + "v")
                    if v is not None and v.text and v.text.isdigit() and int(v.text) < len(sst):
                        txt = sst[int(v.text)]
                elif c.get("t") == "inlineStr":
                    txt = "".join(t.text or "" for t in c.iter(X + "t"))
                if txt:
                    heads[m.group(1)] = heads.get(m.group(1), "") + " " + txt
            changed = False
            prev = {}  # 행 번호 → (열 번호, 원래 날짜, 새 날짜): 바로 옆 칸의 기간 끝날 처리용

            def colnum(col):
                n_ = 0
                for ch in col:
                    n_ = n_ * 26 + ord(ch) - 64
                return n_
            for c in root.iter(X + "c"):
                t = c.get("t")
                v = c.find(X + "v")
                if v is None or v.text is None or t not in (None, "n"):
                    continue
                ref = c.get("r") or "?"
                try:
                    val = float(v.text)
                except ValueError:
                    continue
                s = int(c.get("s", "0"))
                where = f"{n.split('/')[-1]} {ref}"
                head = heads.get(col_of(ref), "")
                if c.find(X + "f") is not None:
                    if s in date_styles:
                        lg["flags"].append({"분류": "수식 속 연도", "위치": where, "원문": (c.find(X + "f").text or "")[:60],
                                            "설명": "날짜를 수식으로 계산하는 칸이라 바꾸지 않음"})
                    continue
                if s in date_styles and 1 <= val < 100000:
                    d = EPOCH + dtm.timedelta(days=int(val))
                    frac = val - int(val)
                    if not (dc.SRC_LO <= d.year <= dc.SRC_HI) or HEAD_BAD.search(head):
                        continue
                    mref = re.match(r"([A-Z]+)(\d+)", ref)
                    rown, coln = (int(mref.group(2)), colnum(mref.group(1))) if mref else (None, None)
                    pv = prev.get(rown)
                    if pv and pv[0] == coln - 1 and 0 < (d - pv[1]).days <= 31:
                        new, info, pf = dc.period_end(pv[1], pv[2], d, where, f"{pv[1].isoformat()} ~ {d.isoformat()}")
                        lg["flags"] += pf
                        if dc.school_year_of(pv[1]) != dc.school_year_of(d):
                            lg["flags"].append({"분류": "학년도 넘는 기간", "위치": where, "원문": f"{pv[1].isoformat()} ~ {d.isoformat()}",
                                                "설명": f"원문 기간이 두 학년도에 걸칩니다({pv[1].isoformat()} ~ {d.isoformat()}). 끝날은 길이를 유지해 {new.isoformat()}로 옮겼습니다."})
                    else:
                        new, info = dc.shift_date(d, years)
                    if rown is not None:
                        prev[rown] = (coln, d, new)
                    nv = (new - EPOCH).days + frac
                    v.text = str(int(nv)) if frac == 0 else repr(nv)
                    changed = True
                    lg["changes"].append({"위치": where, "원문": f"{d.isoformat()} (일련번호 {v.text if False else int(val)})",
                                          "새글": f"{new.isoformat()} (일련번호 {int(nv)})", "원래날짜": d.isoformat(),
                                          "새날짜": new.isoformat(), "새요일": dc.WD[new.weekday()], **info,
                                          "규칙": "숫자 날짜", "확신": "높음",
                                          "근거문맥": "엑셀 날짜 서식 칸" + (" · 왼쪽 칸과 기간(길이 유지)" if info.get("기간시작") else "")})
                    continue
                if val == int(val) and len(str(int(val))) in (6, 8):
                    raw = str(int(val))
                    if len(raw) == 8:
                        y, mo, da = int(raw[:4]), int(raw[4:6]), int(raw[6:])
                    else:
                        y, mo, da = 2000 + int(raw[:2]), int(raw[2:4]), int(raw[4:])
                    try:
                        d = dtm.date(y, mo, da)
                    except ValueError:
                        continue
                    if not (dc.SRC_LO <= y <= dc.SRC_HI):
                        continue
                    if HEAD_WORDS.search(head) and not HEAD_BAD.search(head):
                        new, info = dc.shift_date(d, years)
                        nr = f"{new.year}{new.month:02d}{new.day:02d}" if len(raw) == 8 else f"{new.year % 100:02d}{new.month:02d}{new.day:02d}"
                        v.text = nr
                        changed = True
                        lg["changes"].append({"위치": where, "원문": raw, "새글": nr, "원래날짜": d.isoformat(), "새날짜": new.isoformat(),
                                              "새요일": dc.WD[new.weekday()], **info, "규칙": "숫자 날짜",
                                              "확신": "높음" if len(raw) == 8 else "보통", "근거문맥": "열 제목: " + head.strip()[:30]})
                    else:
                        lg["flags"].append({"분류": "날짜일 수 있는 숫자", "위치": where, "원문": raw,
                                            "설명": f"날짜({d.isoformat()})일 수 있으나 열 제목에 날짜 표시가 없어 그대로 둠"})
            if not changed:
                return b
            return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        hooks[n] = hook
    # 시트 이름 속 연도는 표시만
    if "xl/workbook.xml" in names:
        for sh in etree.fromstring(z.read("xl/workbook.xml")).iter(X + "sheet"):
            if re.search(r"(?<!\d)20\d{2}(?!\d)|\d{2}학년도", sh.get("name") or ""):
                log["flags"].append({"분류": "시트 이름 연도", "위치": "시트 이름", "원문": sh.get("name"),
                                     "설명": "시트 이름은 수식 참조 때문에 바꾸지 않음"})
    return hooks
