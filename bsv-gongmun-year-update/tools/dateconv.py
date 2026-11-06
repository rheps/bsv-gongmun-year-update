# -*- coding: utf-8 -*-
"""지난 문서의 날짜 표기를 '대상 학년도'로 옮기는 엔진 (v3).

규칙(1년씩 더하지 않고 대상 학년도 안으로 옮긴다)
- 날짜는 몇 해 전 것이든 대상 학년도(대상년 3월 1일 ~ 다음 해 2월 말일) 안으로 옮긴다.
  3~12월 → 대상년, 1~2월 → 대상년 + 1. 달은 그대로.
- 그 달 안에서 같은 '몇째 주 무슨 요일' 위치를 유지한다
  (n = (일-1)//7 + 1, 그 달에 n번째 요일이 없으면 마지막 요일).
- 옮긴 날이 공휴일·대체공휴일·주말이면 가장 가까운 평일(같은 달 우선 → 거리 → 같은 주 → 앞날).
- 고정 날짜(3/1, 2/28 등)는 월·일 유지.
- 기간(~)은 시작일을 위 규칙으로 옮기고 끝날은 원래 길이를 유지한다.
- 관련 문서 날짜는 '대상년. OO. OO.', 문서번호는 OOOO.
- 연도만 쓴 표기(N학년도, N년)는 문서의 작업 학년도가 대상 학년도가 되도록 같은 만큼 옮긴다.
  (작업 학년도와 다른 연도는 같은 만큼 옮기고 표시한다.)

대상 학년도와 공휴일 자료는 configure()로 정한다. 연도를 코드에 박아 두지 않는다.
공휴일 자료: 이 파일 옆 holidays/<연도>.json
"""
import os, re, json
import datetime as dt

WD = "월화수목금토일"
HERE = os.path.dirname(os.path.abspath(__file__))
HOLIDAY_DIR = os.path.join(HERE, "holidays")

# configure()가 채운다
TSY = None            # 대상 학년도
SRC_LO = SRC_HI = None  # 날짜로 인정할 원래 연도 범위
HOLIDAYS = {}         # "YYYY-MM-DD" → 이름 (불러온 모든 연도)
HOLIDAY_INFO = {}     # 연도 → {"파일", "모두확인됨", "미확인": [...]}
HOLIDAY_SOURCE = ""
COVERED_YEARS = set()
WARNINGS = []


class HolidayDataError(Exception):
    """공휴일 자료가 없거나 확인되지 않아 변환을 멈춰야 할 때."""


def school_year_of(d):
    return d.year if d.month >= 3 else d.year - 1


def resolve_target_sy(run_date=None, override=None):
    """대상 학년도: 직접 지정(override)이 있으면 그것, 없으면 실행일이 속한 학년도."""
    if override is not None:
        return int(override)
    d = run_date or dt.date.today()
    return school_year_of(d)


def load_holidays(year, holiday_dir=None):
    p = os.path.join(holiday_dir or HOLIDAY_DIR, f"{year}.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def configure(target_sy, holiday_dir=None, allow_unverified=False, src_years_back=3):
    """대상 학년도와 공휴일 자료를 정한다. 반환: 경고 목록.

    대상 학년도에 들어가는 두 달력 연도(대상년, 대상년+1) 공휴일 자료가 없으면 멈춘다.
    대상 학년도 기간 안에 확인되지 않은 공휴일이 있으면, allow_unverified가 아닐 때 멈춘다.
    """
    global TSY, SRC_LO, SRC_HI, HOLIDAYS, HOLIDAY_INFO, HOLIDAY_SOURCE, COVERED_YEARS, WARNINGS
    hd = holiday_dir or HOLIDAY_DIR
    target_sy = int(target_sy)
    need = [target_sy, target_sy + 1]
    lo, hi = dt.date(target_sy, 3, 1).isoformat(), (dt.date(target_sy + 1, 3, 1) - dt.timedelta(days=1)).isoformat()
    hol, info, warn, src_notes = {}, {}, [], []
    missing, unverified = [], []
    for y in need:
        d = load_holidays(y, hd)
        if d is None:
            missing.append(y)
            continue
        bad = [h for h in d["holidays"] if not h.get("verified") and lo <= h["date"] <= hi]
        info[y] = {"파일": os.path.join(hd, f"{y}.json"), "모두확인됨": bool(d.get("모두확인됨")),
                   "미확인": [f"{h['date']} {h['name']}" for h in bad]}
        if bad:
            unverified.append((y, bad))
        for h in d["holidays"]:
            hol[h["date"]] = h["name"]
        if d.get("근거"):
            src_notes.append(f"{y}: {d['근거']}")
    if missing:
        ys = ", ".join(f"{y}년" for y in missing)
        files = ", ".join(os.path.join(hd, f"{y}.json") for y in missing)
        raise HolidayDataError(
            f"{target_sy}학년도로 옮기려면 {ys} 공휴일 목록이 필요합니다. 다음 파일을 추가하고 다시 실행하세요: {files}")
    if unverified:
        lines = [f"{y}년: " + ", ".join(f"{h['date']} {h['name']}" for h in bad) for y, bad in unverified]
        msg = ("공휴일 목록에 확인되지 않은 날이 있습니다. 공식 근거를 확인해 verified를 true로 바꾼 뒤 다시 실행하세요. "
               "확인 전에 결과를 미리 보려면 --allow-unverified-holidays를 붙이세요. " + " / ".join(lines))
        if not allow_unverified:
            raise HolidayDataError(msg)
        warn += [f"확인되지 않은 공휴일: {l}" for l in lines]
    # 원래 날짜 비교용(지난 연도) 자료는 있으면 읽는다(없어도 됨)
    for y in range(target_sy - src_years_back - 1, target_sy):
        d = load_holidays(y, hd)
        if d:
            for h in d["holidays"]:
                hol.setdefault(h["date"], h["name"])
    # 기간 끝날이 대상년+2로 넘어가는 경우를 위해 있으면 읽는다
    d = load_holidays(target_sy + 2, hd)
    if d:
        for h in d["holidays"]:
            hol.setdefault(h["date"], h["name"])
        need.append(target_sy + 2)
    TSY = target_sy
    SRC_LO, SRC_HI = target_sy - src_years_back, target_sy + 1
    HOLIDAYS = hol
    HOLIDAY_INFO = info
    HOLIDAY_SOURCE = " | ".join(src_notes)
    COVERED_YEARS = set(need)
    WARNINGS = warn
    _compile()
    return warn


def _need():
    if TSY is None:
        raise RuntimeError("dateconv.configure(대상 학년도)를 먼저 불러야 합니다")


def target_year(month):
    _need()
    return TSY if month >= 3 else TSY + 1


def is_holiday(d):
    return d.isoformat() in HOLIDAYS


def is_offday(d):
    return d.weekday() >= 5 or is_holiday(d)


def nth_weekday(year, month, weekday, n):
    first = dt.date(year, month, 1)
    off = (weekday - first.weekday()) % 7
    day = 1 + off + 7 * (n - 1)
    try:
        return dt.date(year, month, day), False
    except ValueError:
        pass
    last = dt.date(year + (month == 12), month % 12 + 1, 1) - dt.timedelta(days=1)
    back = (last.weekday() - weekday) % 7
    return last - dt.timedelta(days=back), True


def nearest_workday(d):
    """가장 가까운 평일. 같은 달 안의 날을 먼저 보고, 거리가 같으면 같은 주, 그다음 앞날."""
    if not is_offday(d):
        return d
    cands = [d + dt.timedelta(days=k) for k in range(-10, 11) if k and not is_offday(d + dt.timedelta(days=k))]
    if not cands:
        return d

    def key(c):
        return (c.month != d.month, abs((c - d).days), c.isocalendar()[:2] != d.isocalendar()[:2], c)
    return min(cands, key=key)


# 날짜 자체에 뜻이 있는 고정 날짜(학년도 시작·끝, 해 시작·끝): 같은 월·일을 유지
FIXED_MD = {(3, 1), (2, 28), (2, 29), (1, 1), (12, 31), (8, 31), (9, 1)}


def shift_date(src, years=None, deadline=False, ty=None):
    """src(date) → (대상 학년도 안의 새 날짜, info). years는 v2 호환용으로 받기만 하고 쓰지 않는다.
    ty: 옮길 달력 연도를 직접 정할 때(학년도에 걸친 기간의 시작일). 없으면 달에 따라 대상년/대상년+1."""
    ty = target_year(src.month) if ty is None else ty
    if (src.month, src.day) in FIXED_MD:
        day = src.day
        while True:
            try:
                new = dt.date(ty, src.month, day); break
            except ValueError:
                day -= 1
        return new, {"고정날짜": True, "주차": None, "요일": WD[src.weekday()], "마지막주로": False, "위치날짜": new.isoformat()}
    n = (src.day - 1) // 7 + 1
    wd = src.weekday()
    pos, used_last = nth_weekday(ty, src.month, wd, n)
    info = {"주차": n, "요일": WD[wd], "마지막주로": used_last, "위치날짜": pos.isoformat()}
    new = nearest_workday(pos)
    if new != pos:
        why = HOLIDAYS.get(pos.isoformat()) or ("토요일" if pos.weekday() == 5 else "일요일")
        info["이동"] = f"{pos.isoformat()}({WD[pos.weekday()]}) {why} → {new.isoformat()}({WD[new.weekday()]})"
    if src.weekday() >= 5:
        info["원래주말"] = True
    if new.year not in COVERED_YEARS:
        info["공휴일확인불가"] = True
    return new, info


# ---------------------------------------------------------------- patterns
def _alt(lo, hi):
    return "(?:" + "|".join(str(y) for y in range(lo, hi + 1)) + ")"


def _yyalt(lo, hi):
    return "(?:" + "|".join(f"{y % 100:02d}" for y in range(lo, hi + 1)) + ")"


WDP = r"(?:\s*\(\s*(?P<w1>[월화수목금토일])(?:요일)?\s*\)|\s*(?P<w2>[월화수목금토일])요일)"
P_NOYEAR = [
    re.compile(r"(?<![\d년])(?P<m>\d{1,2})\s*월\s*(?P<d>\d{1,2})\s*일" + WDP + "?"),
    re.compile(r"(?<![\d.,])(?P<m>\d{1,2})\.\s?(?P<d>\d{1,2})(?![\d:])(?P<t>\.)?" + WDP),
    re.compile(r"(?<![\d.,])(?P<m>\d{1,2})\.\s?(?P<d>\d{1,2})\.(?=\s*[~∼～\-]\s*\d{1,2}\.\s?\d{1,2}\.)"),
    re.compile(r"(?:(?<=[~∼～\-])|(?<=[~∼～\-]\s))(?P<m>\d{1,2})\.\s?(?P<d>\d{1,2})\.(?![\d:])" + WDP + "?"),
    re.compile(r"(?<![\d/])(?P<m>\d{1,2})/(?P<d>\d{1,2})(?![\d/])" + WDP),
]
P_DAYTAIL = re.compile(r"\s*[~∼～]\s*(?P<d>\d{1,2})(?:(?P<u>일)|(?P<t>\.))?" + WDP + r"?(?![\d:.])")
P_CONNECT = re.compile(r"^\s*[~∼～]\s*$|^\s*-\s*$")
P_YM = [
    re.compile(r"(?<![\d,])(?P<y>20\d{2})\s*년\s*(?P<m>\d{1,2})\s*월(?!\s*\d{1,2}\s*일)"),
    re.compile(r"(?<![\d,])(?P<y>20\d{2})\s*\.\s*(?P<m>\d{1,2})(?:\s*\.)?(?!\s*\d)(?![\d])"),
]
P_PROTECT = [
    re.compile(r"[가-힣A-Za-z][가-힣A-Za-z0-9·]*-\d{2,6}(?!\d|\s*(?:학년도|년))(?:\s*,\s*\d{2,6}(?!\d|\s*\.))*(?:\s*\([^()\n]{0,60}\))?"),
    re.compile(r"제\s*[\d\-]+\s*호\s*[,(<\[]?\s*20\d{2}\s*[.\-]\s*\d{1,2}\s*[.\-]\s*\d{1,2}\.?[)>\]]?"),
    re.compile(r"20\d{2}\s*\.\s*\d{1,2}\s*\.\s*\d{1,2}\.?\s*(?:일부개정|전부개정|신설|개정|시행|제정|공포)"),
    re.compile(r"(?:법률|법|시행령|시행규칙|규칙|조례|훈령|예규|고시|지침|규정)\s*(?:제\s*[\d\-]+\s*호)?\s*[(<\[]\s*20\d{2}[^)>\]\n]{0,24}[)>\]]"),
]
P_PROTECT_LINE = re.compile(r"^\s*(?:\d{1,2}\.\s*)?관\s*련\s*[:：]?")
P_BARE_MD = re.compile(r"(?<![\d.,])(?P<m>\d{1,2})\.\s?(?P<d>\d{1,2})\.(?![\d])")
CTX_BEFORE = re.compile(r"(일시|일자|날짜|기간|기한|까지|부터|시행|마감|제출|예정|접수|[~∼～(])\s*[:：]?\s*$")
CTX_AFTER = re.compile(r"^\s*(까지|부터|[~∼～(]|중(?![가-힣])|경(?![가-힣])|자(?![가-힣]))")
NUM_CTX = re.compile(r"(일자|날짜|일시|기간|작성일|기준일|발행일|접수일|시행일|등록일|생산일|date)\s*[:：]?\s*[^\d\n]{0,4}$", re.I)
NUM_BAD_AFTER = re.compile(r"^\s*(원|명|개|번|호|건|점|%|-)")
P_DOCNUM = re.compile(r"(?P<head>[가-힣A-Za-z][가-힣A-Za-z0-9·]*-)(?P<num>\d{2,6})(?!\d|\s*(?:학년도|년))(?P<more>(?:\s*,\s*\d{2,6}(?!\d|\s*\.))*)")
P_DOCREF = re.compile(r"[가-힣A-Za-z][가-힣A-Za-z0-9·]*-\d{2,6}(?:\s*,\s*\d{2,6}(?!\d|\s*\.))*\s*\(\s*(?:20\d{2}|\d{2}\s*\.)[^()\n]{0,60}\)"
                      r"|[가-힣A-Za-z][가-힣A-Za-z0-9·]*-\d{2,6}\s*,\s*20\d{2}\s*\.\s*\d{1,2}\s*\.\s*\d{1,2}\.?")
P_LAW = P_PROTECT[1:]
# 연도 범위에 따라 configure()에서 만든다
P_FULL = P_YRANGE = P_YEAR2 = P_NUM8 = P_NUM6 = P_YEAR3 = P_YEAR = P_YY_SCHOOLYEAR = P_OLDYEAR = None


def _compile():
    global P_FULL, P_YRANGE, P_YEAR2, P_NUM8, P_NUM6, P_YEAR3, P_YEAR, P_YY_SCHOOLYEAR, P_OLDYEAR
    lo, hi = SRC_LO, SRC_HI
    YA, YYA = _alt(lo, hi), _yyalt(lo, hi)
    YOLD = _alt(lo, TSY)  # 연도만 쓴 표기로 옮길 원래 연도(대상년까지)
    P_FULL = [
        re.compile(r"(?<![\d,])(?P<y>20\d{2})\s*(?P<s>[.\-/])\s*(?P<m>\d{1,2})\s*(?P=s)\s*(?P<d>\d{1,2})(?![\d:])(?P<t>\s*\.)?" + WDP + "?"),
        re.compile(r"(?<![\d,])(?P<y>20\d{2})\s*년\s*(?P<m>\d{1,2})\s*월\s*(?P<d>\d{1,2})\s*일" + WDP + "?"),
        re.compile(r"(?<![\d,.])(?P<yy>" + YYA + r")\.\s?(?P<m>\d{1,2})\.\s?(?P<d>\d{1,2})(?![\d:])(?P<t>\.)?" + WDP + "?"),
    ]
    P_YRANGE = re.compile(r"(?<![\d,.])(?P<a>" + YA + r")\s*(?P<c>[-~∼～])\s*(?P<b>20\d{2})(?![\d,.])")
    P_YEAR2 = re.compile(r"(?<=\d\.)(?P<y>" + YOLD + r")(?=\s*(?:년|학년도))")
    P_NUM8 = re.compile(r"(?<![\d\-.,/])(?P<y>" + YA + r")(?P<m>0[1-9]|1[0-2])(?P<d>0[1-9]|[12]\d|3[01])(?!\d)")
    P_NUM6 = re.compile(r"(?<![\d\-.,/])(?P<yy>" + YYA + r")(?P<m>0[1-9]|1[0-2])(?P<d>0[1-9]|[12]\d|3[01])(?!\d)")
    P_YEAR3 = re.compile(r"(?<=-)(?P<y>" + YOLD + r")(?=\s*(?:학년도|년))")
    P_YEAR = re.compile(r"(?<![\d,.\-])(?P<y>20\d{2})(?![\d,])")
    P_YY_SCHOOLYEAR = re.compile(r"(?<![\d,.])'?(?P<yy>" + _yyalt(lo, TSY) + r")(?=학년도)")
    P_OLDYEAR = re.compile(r"(?<!\d)(?P<y>" + _alt(lo, TSY - 1) + r")(?!\d)")


def _valid(y, m, d):
    try:
        return dt.date(y, m, d)
    except ValueError:
        return None


class Match:
    __slots__ = ("start", "end", "kind", "gs", "date", "wmark", "m")

    def __init__(self, m, kind, date):
        self.m = m
        self.start, self.end = m.start(), m.end()
        self.kind = kind
        self.date = date
        self.wmark = m.group("w1") or m.group("w2") if "w1" in m.re.groupindex else None


def _render(m, new):
    s = m.group(0)
    base = m.start()
    reps = []
    gi = m.re.groupindex
    if "y" in gi and m.group("y"):
        reps.append((m.span("y"), str(new.year)))
    if "yy" in gi and m.group("yy"):
        reps.append((m.span("yy"), f"{new.year % 100:02d}"))
    if "m" in gi and m.group("m"):
        g = m.group("m")
        reps.append((m.span("m"), f"{new.month:0{len(g)}d}" if g.startswith("0") else str(new.month)))
    if "d" in gi and m.group("d"):
        g = m.group("d")
        reps.append((m.span("d"), f"{new.day:0{len(g)}d}" if g.startswith("0") else str(new.day)))
    for wg in ("w1", "w2"):
        if wg in gi and m.group(wg):
            reps.append((m.span(wg), WD[new.weekday()]))
    out = s
    for (a, b), v in sorted(reps, key=lambda x: -x[0][0]):
        out = out[: a - base] + v + out[b - base:]
    return out


def _year_only(seg, years, base_sy, where, free, taken, reps, changes, flags, offset0=0, in_relate=False):
    """연도만 쓴 표기(N학년도, 'NN학년도, .N년, -N학년도, 맨 연도 N): 작업 학년도 → 대상 학년도가 되도록 같은 만큼."""
    tag = "관련 줄 연도" if in_relate else "연도 → 대상 학년도"

    def note_other(y, raw):
        if y != base_sy:
            flags.append({"분류": "다른 연도 표기", "위치": where, "원문": raw,
                          "설명": f"{y} → {y + years}(문서 작업 학년도 {base_sy}와 다른 연도도 같은 만큼 옮김)"})
    for m in P_YY_SCHOOLYEAR.finditer(seg):
        if not free(m.start(), m.end()):
            continue
        y = 2000 + int(m.group("yy"))
        taken.append(m.span("yy"))
        new = f"{(y + years) % 100:02d}"
        reps.append((m.start("yy") + offset0, m.end("yy") + offset0, new))
        changes.append({"위치": where, "원문": m.group(0) + "학년도", "새글": new + "학년도", "규칙": tag})
        note_other(y, m.group(0) + "학년도")
    for pat in (P_YEAR2, P_YEAR3):
        for m in pat.finditer(seg):
            if not free(m.start(), m.end()):
                continue
            taken.append((m.start(), m.end()))
            y = int(m.group("y"))
            reps.append((m.start() + offset0, m.end() + offset0, str(y + years)))
            ctx = seg[max(0, m.start() - 6): m.end() + 5]
            changes.append({"위치": where, "원문": ctx, "새글": str(y + years), "규칙": tag})
            note_other(y, ctx.strip())
    for m in P_YEAR.finditer(seg):
        if not free(m.start(), m.end()):
            continue
        y = int(m.group("y"))
        ctx = seg[max(0, m.start() - 12): m.end() + 12]
        if SRC_LO <= y <= TSY:
            taken.append((m.start(), m.end()))
            reps.append((m.start() + offset0, m.end() + offset0, str(y + years)))
            changes.append({"위치": where, "원문": ctx.strip(), "새글": str(y + years), "규칙": tag})
            note_other(y, ctx.strip())
        elif not in_relate:
            flags.append({"분류": "바꾸지 않은 연도", "위치": where, "원문": ctx.strip(), "설명": f"{y}는 그대로 둠"})


def relate_transform(seg, years, where="", base_sy=None):
    """관련 문서 표시: 문서번호 숫자는 OOOO, 날짜는 '대상년. OO. OO.'. 법령 인용 날짜는 그대로. 연도만 쓴 표기는 대상 학년도로."""
    _need()
    base_sy = TSY - 1 if base_sy is None else base_sy
    years = TSY - base_sy if years is None else years
    changes, flags = [], []
    law = []
    for p in P_LAW:
        for m in p.finditer(seg):
            law.append((m.start(), m.end()))
            flags.append({"분류": "관련 안 법령 인용", "위치": where, "원문": m.group(0)[:80],
                          "설명": "관련 줄 안의 법령 인용 - 날짜를 그대로 둠"})
    reps = []
    taken = list(law)

    def free(a, b):
        return all(b <= x or a >= y for x, y in taken)
    for pat in P_FULL:
        for m in pat.finditer(seg):
            if not free(m.start(), m.end()):
                continue
            y = 2000 + int(m.group("yy")) if "yy" in pat.groupindex else int(m.group("y"))
            if not _valid(y, int(m.group("m")), int(m.group("d"))):
                continue
            new = f"{TSY if 'y' in pat.groupindex else TSY % 100:02d}. OO. OO."
            reps.append((m.start(), m.end(), new)); taken.append((m.start(), m.end()))
            changes.append({"위치": where, "원문": m.group(0), "새글": new, "규칙": "관련 문서(번호 OOOO·월일 OO)",
                            "원래날짜": f"{y}-{int(m.group('m')):02d}-{int(m.group('d')):02d}"})
    nblank = 0
    for m in P_DOCNUM.finditer(seg):
        if not free(m.start(), m.end()):
            continue
        more = re.sub(r"\d{2,6}", "OOOO", m.group("more"))
        new = m.group("head") + "OOOO" + more
        nblank += 1 + len(re.findall(r"\d{2,6}", m.group("more")))
        reps.append((m.start(), m.end(), new)); taken.append((m.start(), m.end()))
        changes.append({"위치": where, "원문": m.group(0), "새글": new, "규칙": "관련 문서(번호 OOOO·월일 OO)"})
    # 관련 줄의 제목 속 연도만 쓴 표기(예: 2025학년도 제2차 추경)
    _year_only(seg, years, base_sy, where, free, taken, reps, changes, flags, in_relate=True)
    out, pos = [], 0
    for a, b, v in sorted(reps):
        out.append(seg[pos:a]); out.append(v); pos = b
    out.append(seg[pos:])
    return "".join(out), changes, flags, nblank


def overlap_days(a, b):
    """[a, b] 기간이 대상 학년도와 겹치는 날 수."""
    lo, hi = dt.date(TSY, 3, 1), dt.date(TSY + 1, 3, 1) - dt.timedelta(days=1)
    return max(0, (min(b, hi) - max(a, lo)).days + 1)


def period_end(s0, n0, src, where, raw):
    """기간 끝날: 원래 길이를 유지한다. 끝날이 고정 날짜(2/28 등)면 월·일을 유지한다.
    옮긴 끝날이 대상 학년도를 벗어나면(원래는 한 학년도 안이었는데) 표시한다. 반환: (새 날짜, info, 표시 목록)"""
    fl = []
    new = n0 + (src - s0)
    info = {"규칙": "기간 끝날(길이 유지)", "기간시작": s0.isoformat()}
    if (src.month, src.day) in FIXED_MD and src >= s0:
        fixed, _ = shift_date(src)
        if fixed >= n0 and (fixed - n0).days <= (src - s0).days + 14:
            if fixed != new:
                fl.append({"분류": "기간 길이 바뀜", "위치": where, "원문": raw,
                           "설명": f"끝날 {src.month}/{src.day}을 고정 날짜로 보고 월·일을 유지했습니다({fixed.isoformat()}). "
                                   f"길이를 유지했다면 {new.isoformat()}입니다. 확인하세요."})
            new = fixed
            info = {"규칙": "고정 날짜(월·일 유지)", "기간시작": s0.isoformat(), "고정날짜": True}
    if school_year_of(s0) == school_year_of(src) and school_year_of(new) != school_year_of(n0):
        fl.append({"분류": "학년도 넘는 기간", "위치": where, "원문": raw,
                   "설명": f"원문 기간은 한 학년도 안이었지만, 길이를 유지해 옮긴 끝날({new.isoformat()})이 {TSY}학년도를 벗어납니다. 확인하세요."})
    if new.year not in COVERED_YEARS:
        info["공휴일확인불가"] = True
    return new, info, fl


def protected_spans(text):
    out = []
    for p in P_PROTECT:
        for m in p.finditer(text):
            if re.search(r"20\d{2}|\d{1,2}\s*\.\s*\d{1,2}\.", m.group(0)):
                out.append((m.start(), m.end()))
    return out


_MSG = {}


def msg(n, **kw):
    """화면 문구(문구.txt) 번호 n. {키}를 kw로 채운다."""
    if not _MSG:
        with open(os.path.join(HERE, "문구.txt"), encoding="utf-8") as fh:
            for line in fh.read().splitlines():
                m = re.match(r"(\d+)\.\s*(.*)", line.strip())
                if m:
                    _MSG[int(m.group(1))] = m.group(2)
    s = _MSG[n]
    for k, v in kw.items():
        s = s.replace("{" + k + "}", str(v))
    return s


# 일(日)만 쓴 날짜: '16일쯤', '15일에', '20일까지'. '1일형', '3일간', '1박2일'처럼 날짜가 아닌 것은 뺀다.
P_DAYREF = re.compile(r"(?<![\w.~∼～/\-])(?P<d>\d{1,2})\s*일(?=(?:쯤|경|께|까지|부터|이후|이전|전후|전|후|에는|에도|에|날|자|로)?(?![가-힣]))")
DAYREF_NOT = re.compile(r"^\s*(동안|이내|이상|이하|미만|정도|가량|째|만에|간)")
DAYREF_WINDOW = 150   # 앞 날짜와 이만큼(글자) 안에 있어야 딸린 날짜로 본다
DAYREF_MAXGAP = 14    # 앞 날짜와 원래 이만큼(일) 안이어야 같은 날수로 옮긴다
CAT_ORDER = "날짜 순서 확인"


def _day_refs(text, found, newdates, where, free, taken, reps, changes, flags, shift=True):
    moved = [(i, found[i]) for i in sorted(newdates)]
    for m in P_DAYREF.finditer(text):
        if not free(m.start(), m.end()) or DAYREF_NOT.match(text[m.end():m.end() + 4]):
            continue
        if re.search(r"(매월|매달|매주)\s*$", text[max(0, m.start() - 4):m.start()]):
            continue
        d = int(m.group("d"))
        if not 1 <= d <= 31:
            continue
        raw = m.group(0)
        prev = [(i, mt) for i, mt in moved if mt.end <= m.start() and m.start() - mt.end <= DAYREF_WINDOW]
        near = prev or [(i, mt) for i, mt in moved if mt.start >= m.end() and mt.start - m.end() <= DAYREF_WINDOW]
        if not near:
            continue
        ok = None
        if prev and shift:
            i, mt = prev[-1]
            a0, a1 = mt.date, newdates[i]
            implied = _valid(a0.year, a0.month, d)
            if implied and abs((implied - a0).days) <= DAYREF_MAXGAP:
                new = a1 + (implied - a0)
                if new.month == a1.month:
                    ok = (implied, new, mt, a0, a1)
        taken.append((m.start(), m.end()))
        if not ok:
            mt = near[-1][1] if prev else near[0][1]
            flags.append({"분류": CAT_ORDER, "위치": where, "원문": text[max(0, m.start() - 20):m.end() + 6].strip(),
                          "설명": msg(140, D=raw.strip())})
            continue
        implied, new, mt, a0, a1 = ok
        g = m.group("d")
        rendered = raw[:m.start("d") - m.start()] + (f"{new.day:0{len(g)}d}" if g.startswith("0") else str(new.day)) + raw[m.end("d") - m.start():]
        reps.append((m.start(), m.end(), rendered))
        changes.append({"위치": where, "원문": raw, "새글": rendered, "원래날짜": implied.isoformat(), "새날짜": new.isoformat(),
                        "새요일": WD[new.weekday()], "규칙": "딸린 날짜(같은 날수)", "기준날짜": a0.isoformat(),
                        "설명": msg(139, A=mt.m.group(0).strip(), A0=a0.isoformat(), A1=a1.isoformat())})
        if is_offday(new) and not is_offday(implied):
            flags.append({"분류": "기간에 휴일 포함", "위치": where, "원문": raw, "설명": "옮긴 기간 안에 공휴일·주말: " + new.isoformat()})


def name_day_refs(name):
    """파일·폴더 이름에 남은 일(日)만 쓴 날짜·연도 없는 날짜(이름은 바꾸지 않고 표시만 한다)."""
    out = []
    for m in P_DAYREF.finditer(name):
        if not DAYREF_NOT.match(name[m.end():m.end() + 4]):
            out.append(m.group(0).strip())
    for m in re.finditer(r"(?<![\d.])\d{1,2}\s*월\s*\d{1,2}\s*일", name):
        out.append(m.group(0))
    return out


def order_check(changes, skip_where=("파일 이름",)):
    """한 문서 안에서 바꾸기 전 날짜 순서가 바꾼 뒤에도 그대로인지 본다. 반환: 표시 목록.
    원래 날짜 순으로 줄 세운 뒤, 이웃한 두 날짜의 새 날짜가 뒤집혔으면 표시한다(같은 글 안 짝은 convert가 이미 봄)."""
    pts = {}
    for c in changes:
        if not c.get("원래날짜") or not c.get("새날짜") or c.get("위치") in skip_where:
            continue
        pts.setdefault(c["원래날짜"], c)
    seq = sorted(pts.items())
    flags = []
    for (a0, ca), (b0, cb) in zip(seq, seq[1:]):
        if ca["새날짜"] > cb["새날짜"] and (ca.get("위치"), ca.get("줄")) != (cb.get("위치"), cb.get("줄")):
            flags.append({"분류": "날짜 순서 바뀜", "위치": f"{ca.get('위치', '')} / {cb.get('위치', '')}",
                          "원문": f"{ca.get('원문', '')} … {cb.get('원문', '')}"[:80],
                          "설명": f"원래 {a0} → {b0} 순서였지만 옮긴 뒤 {ca['새날짜']} → {cb['새날짜']}로 뒤집혔습니다. 확인하세요."})
    return flags


def convert(text, base_sy=None, years=None, where="", date_context=False, shift_day_refs=True):
    """text 안의 날짜·연도 표기를 대상 학년도로 옮긴다.

    base_sy: 이 문서의 작업 학년도(기본: 대상 학년도 - 1).
    years: 연도만 쓴 표기를 옮길 해 수(기본: 대상 학년도 - base_sy). 날짜는 이 값과 상관없이 대상 학년도로 간다.
    반환: (새 글, 바꿈 목록, 표시 목록, 치환 목록[(start,end,new)])
    """
    _need()
    base_sy = TSY - 1 if base_sy is None else base_sy
    years = TSY - base_sy if years is None else years
    taken = []
    flags = []
    if P_PROTECT_LINE.match(text):
        new_t, ch, fl, nb = relate_transform(text, years, where, base_sy)
        for c in ch:
            c["번호비움"] = nb
        flags.append({"분류": "관련 문서·법령 날짜", "위치": where, "원문": text[:80],
                      "설명": f"관련 줄: 문서번호 {nb}개를 OOOO로, 날짜를 {TSY}. OO. OO.로 바꿨습니다. 실제 문서번호와 날짜를 넣으세요."})
        reps = [(0, len(text), new_t)] if new_t != text else []
        return new_t, ch, fl + flags, reps
    prot = []
    pre_reps, pre_changes = [], []
    for m in P_DOCREF.finditer(text):
        new_t, ch, fl, nb = relate_transform(m.group(0), years, where, base_sy)
        for c in ch:
            c["번호비움"] = nb
        pre_reps.append((m.start(), m.end(), new_t)); pre_changes += ch; flags += fl
        prot.append((m.start(), m.end()))
        flags.append({"분류": "관련 문서·법령 날짜", "위치": where, "원문": m.group(0)[:80],
                      "설명": f"관련 문서 표시: 번호를 OOOO로, 날짜를 {TSY}. OO. OO.로 바꿨습니다. 실제 값을 넣으세요."})
    for a, b in protected_spans(text):
        if any(not (b <= x or a >= y) for x, y in prot):
            continue
        prot.append((a, b))
        if re.search(r"20\d{2}|\d{1,2}\s*\.\s*\d{1,2}\.", text[a:b]):
            flags.append({"분류": "관련 문서·법령 날짜", "위치": where, "원문": text[a:b][:80],
                          "설명": "문서번호·법령 인용이라 그대로 둠"})
    for a, b in prot:
        taken.append((a, b))

    def free(a, b):
        return all(b <= s or a >= e for s, e in taken)

    found = []
    for pat in P_FULL:
        for m in pat.finditer(text):
            if not free(m.start(), m.end()):
                continue
            y = 2000 + int(m.group("yy")) if "yy" in pat.groupindex else int(m.group("y"))
            d = _valid(y, int(m.group("m")), int(m.group("d")))
            if not d or not (SRC_LO <= y <= SRC_HI):
                continue
            found.append(Match(m, "full", d))
            taken.append((m.start(), m.end()))
    for pat in P_NOYEAR:
        for m in pat.finditer(text):
            if not free(m.start(), m.end()):
                continue
            mo, da = int(m.group("m")), int(m.group("d"))
            if not (1 <= mo <= 12 and 1 <= da <= 31):
                continue
            found.append(Match(m, "noyear", None))
            taken.append((m.start(), m.end()))
    for m in P_BARE_MD.finditer(text):
        if not free(m.start(), m.end()):
            continue
        mo, da = int(m.group("m")), int(m.group("d"))
        if not (1 <= mo <= 12 and 1 <= da <= 31) or not text[:m.start()].strip():
            continue
        before, after = text[max(0, m.start() - 12):m.start()], text[m.end():m.end() + 6]
        if CTX_BEFORE.search(before) or CTX_AFTER.match(after):
            found.append(Match(m, "noyear", None))
            taken.append((m.start(), m.end()))
        elif re.search(r"\d\.\s*$", before) is None:
            flags.append({"분류": "날짜일 수 있는 숫자", "위치": where, "원문": text[max(0, m.start() - 12):m.end() + 6].strip(),
                          "설명": "날짜 문맥이 분명하지 않아 그대로 둠"})
    found.sort(key=lambda x: x.start)

    last_full = None
    for mt in found:
        if mt.kind == "full":
            last_full = mt.date
            continue
        mo, da = int(mt.m.group("m")), int(mt.m.group("d"))
        sy = school_year_of(last_full) if last_full else base_sy
        y = sy if mo >= 3 else sy + 1
        cand = _valid(y, mo, da)
        note = "연도 추정(학년도 기준)"
        if mt.wmark and cand and WD[cand.weekday()] != mt.wmark:
            for alt in (y - 1, y + 1):
                c2 = _valid(alt, mo, da)
                if c2 and WD[c2.weekday()] == mt.wmark:
                    cand, note = c2, f"연도 추정(요일 표기로 {alt}년 판단)"
                    break
        if not cand:
            mt.date = None
            continue
        mt.date = cand
        mt.kind = "noyear:" + note

    # 기간 연결
    pairs = {}
    extra = []
    for i, mt in enumerate(found):
        if mt.date is None:
            continue
        nxt = found[i + 1] if i + 1 < len(found) else None
        if nxt and nxt.date and P_CONNECT.match(text[mt.end:nxt.start]):
            pairs[i + 1] = i
            continue
        tm = P_DAYTAIL.match(text, mt.end)
        if tm and (tm.group("u") or tm.group("t") or tm.group("w1") or tm.group("w2")) and free(tm.start(), tm.end()):
            da = int(tm.group("d"))
            base = mt.date
            end = _valid(base.year, base.month, da)
            if end and end < base:
                end = _valid(base.year + (base.month == 12), base.month % 12 + 1, da)
            if end and 0 <= (end - base).days <= 31:
                extra.append((i, tm, end))
                taken.append((tm.start(), tm.end()))
        # 끝날이 범위 밖 연도(예: ~ 2029. 2. 28.)인 여러 해 기간
        mm = re.match(r"\s*[~∼～\-]\s*(20\d{2})\s*[.년]", text[mt.end:mt.end + 12])
        if mm and not (SRC_LO <= int(mm.group(1)) <= SRC_HI):
            flags.append({"분류": "여러 해 기간", "위치": where, "원문": text[mt.start:mt.end + 16].strip(),
                          "설명": f"기간 끝 연도({mm.group(1)})가 옮길 범위 밖이라 끝날은 그대로 두고 시작일만 대상 학년도로 옮겼습니다. 기간을 확인하세요."})

    # 학년도에 걸친 기간(예: 1. 1. ~ 12. 31., 2. 23. ~ 3. 6.): 대상 학년도와 가장 많이 겹치도록 시작일의 연도를 고른다
    cross_ty = {}
    spans = [(j, i, found[i].date) for i, j in pairs.items()] + [(i, None, end) for i, tm, end in extra]
    for j, _, end in spans:
        s0 = found[j].date
        if s0 is None or end is None or school_year_of(s0) == school_year_of(end) or end < s0:
            continue
        cands = []
        for ty in (TSY, TSY + 1):
            ns, _ = shift_date(s0, ty=ty)
            ov = overlap_days(ns, ns + (end - s0))
            cands.append((-ov, ty != target_year(s0.month), ty))
        cross_ty[j] = min(cands)[2]

    changes, reps = list(pre_changes), list(pre_reps)
    newdates = {}
    for i, mt in enumerate(found):
        if mt.date is None:
            continue
        src = mt.date
        raw = mt.m.group(0)
        if i in pairs and newdates.get(pairs[i]) is not None:
            j = pairs[i]
            s0, n0 = found[j].date, newdates[j]
            new, info, pf = period_end(s0, n0, src, where, text[found[j].start:mt.end])
            flags += pf
            span = (src - s0).days
            if span < 0:
                flags.append({"분류": "날짜 순서 바뀜", "위치": where, "원문": text[found[j].start:mt.end],
                              "설명": "원문 기간의 끝날이 시작일보다 앞섭니다. 길이를 그대로 두고 옮겼으니 확인하세요."})
            elif span > 366:
                flags.append({"분류": "여러 해 기간", "위치": where, "원문": text[found[j].start:mt.end],
                              "설명": f"{span}일짜리 기간입니다. 시작일을 대상 학년도로 옮기고 길이를 유지했습니다. 여러 해 계획이면 확인하세요."})
            if school_year_of(s0) != school_year_of(src):
                flags.append({"분류": "학년도 넘는 기간", "위치": where, "원문": text[found[j].start:mt.end],
                              "설명": f"원문 기간이 두 학년도에 걸칩니다({s0.isoformat()} ~ {src.isoformat()}). 끝날은 길이를 유지해 {new.isoformat()}로 옮겼습니다."})
            if new.year not in COVERED_YEARS:
                info["공휴일확인불가"] = True
            bad = [new - dt.timedelta(days=k) for k in range(max(span, 0) + 1)
                   if is_offday(new - dt.timedelta(days=k)) and not is_offday(src - dt.timedelta(days=k))]
            if bad:
                flags.append({"분류": "기간에 휴일 포함", "위치": where, "원문": text[found[j].start:mt.end],
                              "설명": "옮긴 기간 안에 공휴일·주말: " + ", ".join(b.isoformat() for b in sorted(bad))})
        else:
            new, info = shift_date(src, ty=cross_ty.get(i))
            info["규칙"] = "같은 주차·요일"
            if i in cross_ty:
                info["학년도걸친기간시작"] = True
        newdates[i] = new
        if mt.wmark and WD[src.weekday()] != mt.wmark:
            flags.append({"분류": "원문 요일 오류", "위치": where, "원문": raw,
                          "설명": f"{src.isoformat()}은 실제 {WD[src.weekday()]}요일인데 원문은 ({mt.wmark}). 실제 요일 기준으로 옮김"})
            info["원문요일오류"] = mt.wmark
        if mt.kind.startswith("noyear"):
            flags.append({"분류": "연도 없는 날짜", "위치": where, "원문": raw,
                          "설명": mt.kind.split(":", 1)[1] + f" → {src.isoformat()}로 보고 옮김"})
        if info.get("고정날짜"):
            info["규칙"] = "고정 날짜(월·일 유지)"
            flags.append({"분류": "고정 날짜", "위치": where, "원문": raw,
                          "설명": f"학년도·해의 시작·끝 같은 고정 날짜로 보고 월·일을 그대로 둠 → {new.isoformat()}({WD[new.weekday()]})"})
        if info.get("원래주말"):
            flags.append({"분류": "원래 주말 날짜", "위치": where, "원문": raw,
                          "설명": f"{src.isoformat()}({WD[src.weekday()]}) 주말 행사·기한일 수 있음. 평일로 옮김"})
        if info.get("공휴일확인불가"):
            flags.append({"분류": "공휴일 확인 불가", "위치": where, "원문": raw,
                          "설명": f"{new.isoformat()} 공휴일 목록 범위 밖"})
        if school_year_of(src) != base_sy and not info.get("기간시작") and not info.get("학년도걸친기간시작"):
            info["다른학년도"] = school_year_of(src)
            flags.append({"분류": "다른 학년도 날짜", "위치": where, "원문": raw,
                          "설명": f"{src.isoformat()}는 {school_year_of(src)}학년도 날짜입니다(문서 작업 학년도 {base_sy}). "
                                  f"규칙대로 {TSY}학년도 {new.isoformat()}로 옮겼습니다. 지난 일을 가리키면 확인하세요."})
        rendered = _render(mt.m, new)
        reps.append((mt.start, mt.end, rendered))
        changes.append({"위치": where, "원문": raw, "새글": rendered, "원래날짜": src.isoformat(),
                        "새날짜": new.isoformat(), "새요일": WD[new.weekday()], **info})
    for i, tm, end in extra:
        s0 = found[i].date
        if i not in newdates:
            continue
        n0 = newdates[i]
        new, einfo, pf = period_end(s0, n0, end, where, text[found[i].start:tm.end()])
        flags += pf
        s = tm.group(0)
        b = tm.start()
        r = []
        g = tm.group("d")
        r.append((tm.span("d"), str(new.day) if not g.startswith("0") else f"{new.day:02d}"))
        for wg in ("w1", "w2"):
            if tm.group(wg):
                r.append((tm.span(wg), WD[new.weekday()]))
                if WD[end.weekday()] != tm.group(wg):
                    flags.append({"분류": "원문 요일 오류", "위치": where, "원문": s.strip(),
                                  "설명": f"{end.isoformat()}은 실제 {WD[end.weekday()]}요일인데 원문은 ({tm.group(wg)})"})
        for (a, c), v in sorted(r, key=lambda x: -x[0][0]):
            s = s[: a - b] + v + s[c - b:]
        if new.month != n0.month and new.month != end.month:
            flags.append({"분류": "기간 달 바뀜", "위치": where, "원문": tm.group(0).strip(), "설명": "끝날이 다른 달로 넘어감, 확인 필요"})
        reps.append((tm.start(), tm.end(), s))
        bad = [n0 + dt.timedelta(days=k) for k in range((end - s0).days + 1) if is_offday(n0 + dt.timedelta(days=k)) and not is_offday(s0 + dt.timedelta(days=k))]
        if bad:
            flags.append({"분류": "기간에 휴일 포함", "위치": where, "원문": text[found[i].start:tm.end()],
                          "설명": "옮긴 기간 안에 공휴일·주말: " + ", ".join(x.isoformat() for x in bad)})
        changes.append({"위치": where, "원문": tm.group(0).strip(), "새글": s.strip(), "원래날짜": end.isoformat(),
                        "새날짜": new.isoformat(), "새요일": WD[new.weekday()], **einfo})

    # 일(日)만 쓴 딸린 날짜(예: '10월 15일 회의 이후 16일쯤 품의'): 앞 날짜와 같은 날수만큼 옮겨 순서를 지킨다
    _day_refs(text, found, newdates, where, free, taken, reps, changes, flags, shift=shift_day_refs)

    # 같은 글 안에서 원래 순서가 뒤집힌 날짜(학년도 경계를 넘는 나열 등)
    seq = [(found[i].date, newdates[i], found[i]) for i in sorted(newdates)]
    for (a0, a1, ma), (b0, b1, mb) in zip(seq, seq[1:]):
        if (b0 - a0).days > 0 and (b1 - a1).days < -7:
            flags.append({"분류": "날짜 순서 바뀜", "위치": where, "원문": text[ma.start:mb.end][:80],
                          "설명": f"원래 {a0.isoformat()} → {b0.isoformat()} 순서였지만 옮긴 뒤 {a1.isoformat()} → {b1.isoformat()}로 뒤집혔습니다. 확인하세요."})

    # 연-월: 달에 따라 대상년 또는 대상년+1
    for pat in P_YM:
        for m in pat.finditer(text):
            if not free(m.start(), m.end()):
                continue
            y, mo = int(m.group("y")), int(m.group("m"))
            if not (SRC_LO <= y <= SRC_HI) or not (1 <= mo <= 12):
                continue
            taken.append((m.start(), m.end()))
            ny = target_year(mo)
            new = m.group(0).replace(m.group("y"), str(ny), 1)
            reps.append((m.start(), m.end(), new))
            changes.append({"위치": where, "원문": m.group(0), "새글": new, "규칙": "연-월(대상 학년도)"})
            ssy = y if mo >= 3 else y - 1
            if ssy != base_sy:
                flags.append({"분류": "다른 학년도 날짜", "위치": where, "원문": m.group(0),
                              "설명": f"{y}년 {mo}월은 {ssy}학년도입니다(문서 작업 학년도 {base_sy}). 규칙대로 {ny}년 {mo}월로 옮겼습니다. 지난 일을 가리키면 확인하세요."})
    for m in P_YRANGE.finditer(text):
        if not free(m.start(), m.end()):
            continue
        a, b = int(m.group("a")), int(m.group("b"))
        if not (a < b <= a + 10):
            continue
        taken.append((m.start(), m.end()))
        new = text[m.start():m.start("a")] + str(a + years) + text[m.end("a"):m.start("b")] + str(b + years)
        reps.append((m.start(), m.end(), new))
        changes.append({"위치": where, "원문": m.group(0), "새글": new, "규칙": "연도 기간(같은 만큼)"})
        flags.append({"분류": "여러 해 기간", "위치": where, "원문": m.group(0),
                      "설명": f"연도 기간 {a}~{b}를 같은 만큼({years:+d}) 옮겨 {a + years}~{b + years}로 바꿨습니다. 여러 해 계획이면 확인하세요."})
    _year_only(text, years, base_sy, where, free, taken, reps, changes, flags)
    for m in re.finditer(r"(?<=-)(" + _alt(SRC_LO, TSY) + r")(?!\d)", text):
        if free(m.start(), m.end()):
            flags.append({"분류": "연도 같은 숫자", "위치": where, "원문": text[max(0, m.start() - 12): m.end() + 6].strip(),
                          "설명": "문서번호·전화번호일 수 있어 그대로 둠"})

    for pat, kind in ((P_NUM8, 8), (P_NUM6, 6)):
        for m in pat.finditer(text):
            if not free(m.start(), m.end()):
                continue
            y = int(m.group("y")) if kind == 8 else 2000 + int(m.group("yy"))
            d = _valid(y, int(m.group("m")), int(m.group("d")))
            if not d:
                continue
            ctx = NUM_CTX.search(text[max(0, m.start() - 16):m.start()])
            after_bad = NUM_BAD_AFTER.match(text[m.end():m.end() + 3])
            raw = m.group(0)
            if (ctx or date_context) and not after_bad:
                new, info = shift_date(d)
                rendered = f"{new.year}{new.month:02d}{new.day:02d}" if kind == 8 else f"{new.year % 100:02d}{new.month:02d}{new.day:02d}"
                taken.append((m.start(), m.end()))
                reps.append((m.start(), m.end(), rendered))
                changes.append({"위치": where, "원문": raw, "새글": rendered, "원래날짜": d.isoformat(), "새날짜": new.isoformat(),
                                "새요일": WD[new.weekday()], **info, "규칙": "숫자 날짜",
                                "확신": "높음" if (kind == 8 or date_context) else "보통",
                                "근거문맥": (ctx.group(0).strip() if ctx else "열 제목")})
            else:
                flags.append({"분류": "날짜일 수 있는 숫자", "위치": where, "원문": text[max(0, m.start() - 12):m.end() + 6].strip(),
                              "설명": f"{raw}는 날짜({d.isoformat()})일 수 있으나 문맥이 분명하지 않아 그대로 둠"})

    reps.sort(key=lambda r: r[0])
    for m in P_OLDYEAR.finditer(text):
        if any(a <= m.start() < b for a, b, _ in reps) or any(a <= m.start() < b for a, b in prot):
            continue
        if text[max(0, m.start() - 1):m.start()] == "-":
            continue
        flags.append({"분류": "바꾸지 않은 연도 숫자", "위치": where, "원문": text[max(0, m.start() - 12): m.end() + 10].strip(),
                      "설명": "날짜·연도 규칙에 맞지 않아 그대로 둠. 확인 필요"})
    out, pos = [], 0
    for a, b, v in reps:
        out.append(text[pos:a]); out.append(v); pos = b
    out.append(text[pos:])
    return "".join(out), changes, flags, reps


# ---------------------------------------------------------------- 표시(자동 변경 안 함)
# 학교·지역 고유 낱말(이전 학교 이름, 표어 등)은 코드에 두지 않는다.
# 학교별 표시 규칙 파일(사용자 폴더/.bsv-gongmun-year-update/표시규칙.json)을 add_flag_terms()로 더한다.
FLAG_RULES = [
    ("이전 학교 정보", re.compile(r"[가-힣]{1,12}(?:초등|중|고등|여자중|여자고등)?학교")),
    ("교육지원청·관계 기관", re.compile(r"[가-힣]*교육지원청|[가-힣]*교육청|[가-힣]*경찰서|[가-힣]*소방서|[가-힣]*시청|[가-힣]*구청|[가-힣]*수련원|[가-힣]*청소년수련관|[가-힣]*보건소|[가-힣]*주민센터|[가-힣]*행정복지센터")),
    ("주소·우편번호", re.compile(r"[가-힣]+(?:로|길)\s?\d+(?:-\d+)?(?:번길)?|(?<!\d)\d{5}(?!\d)(?=.*[가-힣])|우편번호")),
    ("전화·팩스", re.compile(r"(?<!\d)0\d{1,2}[-)\s]\d{3,4}-\d{4}(?!\d)|(?:전화|팩스|FAX|Tel)\s*[:.]?", re.I)),
    ("홈페이지·메일", re.compile(r"https?://\S+|www\.\S+|\S+\.(?:kr|com|net|org)\b|\S+@\S+", re.I)),
    ("회차", re.compile(r"제\s*\d+\s*(?:회|차)|\d+\s*차(?![가-힣])|\(\d+차\)|\d+회(?=\s|$|[^\d가-힣])")),
    ("문서번호·시행번호", re.compile(r"[가-힣A-Za-z]+(?:과|부|교|청|원|팀|실)?-\d{3,6}(?!\d)|시행\s*[가-힣]*-\d+|접수\s*[가-힣]*-\d+")),
    ("금액", re.compile(r"\d{1,3}(?:,\d{3})+\s*(?:원|천원)|\d+\s*(?:천|만)?원(?![가-힣]{0,1}[칙장리])|일금\S+")),
    ("중학교 기준·학교급", re.compile(r"중학교|중학생|\(중\)|중\s?학\s?교")),
    ("업체 이름", re.compile(r"㈜|\(주\)|주식회사|[가-힣]*관광|[가-힣]*고속|[가-힣]*여행사|[가-힣]*손해보험|[가-힣]*공제회|[가-힣]*화재")),
    ("결재란", re.compile(r"결\s*재|기안자|검토자|결재권자|협조자|전결|대결|담당자\s|교\s*장|교\s*감")),
    ("사람 이름 가능", re.compile(r"(?:(?<=[\s,(])|^)(?:[가-힣]{2,4}\s*,\s*){2,}[가-힣]{2,4}|(?:담임|교사|부장|담당|선생님?|실무사|주무관|행정실장|위원장|간사)\s*[:：]?\s*[가-힣]{2,4}(?=[\s,)]|$)")),
]


_BASE_FLAG_RULES = list(FLAG_RULES)


def add_flag_terms(terms):
    """표시 규칙 더하기. terms: {분류: [낱말 또는 're:정규식', ...]}. 같은 분류가 있으면 그 앞에 넣는다.
    다시 부르면 기본 규칙에서 새로 만든다."""
    global FLAG_RULES
    rules = list(_BASE_FLAG_RULES)
    for cat, words in (terms or {}).items():
        if cat.startswith("_") or not isinstance(words, list):
            continue
        alts = [w[3:] if w.startswith("re:") else re.escape(w) for w in words if isinstance(w, str) and w.strip()]
        if not alts:
            continue
        pat = re.compile("|".join(alts), re.I)
        idx = next((i for i, (c, _) in enumerate(rules) if c == cat), 0)
        rules.insert(idx, (cat, pat))
    FLAG_RULES = rules
    return FLAG_RULES


def find_flags(text, where=""):
    out = []
    taken = {}  # 분류 → 이미 올린 글자 범위. 같은 분류의 두 규칙이 같은 곳을 겹쳐 잡으면 한 번만 올린다
    for cat, pat in FLAG_RULES:
        for m in pat.finditer(text):
            s = m.group(0).strip()
            if not s:
                continue
            spans = taken.setdefault(cat, [])
            if any(m.start() < e and m.end() > b for b, e in spans):
                continue
            spans.append((m.start(), m.end()))
            ctx = text[max(0, m.start() - 15): m.end() + 15].replace("\n", " ").strip()
            out.append({"분류": cat, "위치": where, "원문": ctx, "설명": f"「{s}」 자동 변경 안 함"})
    return out


def check_weekdays(text):
    """바꾼 뒤 글에서 날짜-요일이 맞지 않는 곳(연도 있는 날짜만)."""
    bad = []
    for pat in P_FULL:
        for m in pat.finditer(text):
            w = m.group("w1") or m.group("w2")
            if not w:
                continue
            y = 2000 + int(m.group("yy")) if "yy" in pat.groupindex else int(m.group("y"))
            d = _valid(y, int(m.group("m")), int(m.group("d")))
            if d and WD[d.weekday()] != w:
                bad.append(m.group(0))
    return bad
