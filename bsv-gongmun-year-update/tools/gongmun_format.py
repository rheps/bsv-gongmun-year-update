# -*- coding: utf-8 -*-
"""업무관리시스템 붙여넣기용 공문 글(제목/본문/붙임 목록)을 현행 공문서 작성 규칙에 맞춘다.

근거(2026-11-03 확인)
- 행정업무의 운영 및 혁신에 관한 규정(대통령령 제36333호, 2026. 5. 19. 일부개정·시행) 제7조
- 같은 규정 시행규칙(행정안전부령 제408호, 2023. 6. 28. 일부개정·시행) 제2조, 제4조
- 행정안전부 「2025 행정업무운영 편람」(2025. 12. 17. 최종, 행안부 누리집 2026. 1. 2. 게시) 49~61쪽
문구는 바꾸지 않고 기호·띄어쓰기·날짜·시간 표기와 붙임·끝 표시만 고친다.
"""
import re

R_DATE = "영 제7조제5항, 편람 49쪽(날짜: 연·월·일 글자 생략, 마침표·한 타 띄움, 0 생략)"
R_TIME = "영 제7조제5항, 편람 49쪽(시간: 24시각제, 쌍점)"
R_ITEM = "규칙 제2조제1항, 편람 51~52쪽(항목 기호 1.→가.→1)→가)→(1)→(가)→①→㉮, 기호 뒤 한 타)"
R_INDENT = "편람 52쪽(첫째 항목은 왼쪽 기본선, 둘째 항목부터 바로 위 항목에서 2타씩 오른쪽)"
R_ATT = "규칙 제4조제4항, 편람 59~60쪽(붙임 표시: 본문 다음 줄, 붙임 뒤 2타, 두 가지 이상이면 항목 구분)"
R_REL = "관련 추가: 모든 공문에 관련 항목을 둠, 뒤 항목 번호는 규칙 제2조제1항 순서대로 이어 매김"
R_COLON = "「한글 맞춤법」 부록 문장 부호, 쌍점(:)은 앞말에 붙여 쓰고 뒤는 한 칸 띄움. 18:00처럼 숫자 사이에 쓸 때는 붙여 씀"
R_END = "규칙 제4조제5항, 편람 61쪽(끝 표시: 마지막 글자에서 2타 띄우고 '끝.', 붙임이 있으면 붙임 표시문 다음, 표로 끝나면 다음 줄 왼쪽 기본선에서 2타)"

ITEM_PATTERNS = [
    (1, re.compile(r"^(\d{1,2})\.(?!\d)\s*")),
    (2, re.compile(r"^([가-하거-허])\.\s*")),
    (3, re.compile(r"^(\d{1,2})\)\s*")),
    (4, re.compile(r"^([가-하거-허])\)\s*")),
    (5, re.compile(r"^\((\d{1,2})\)\s*")),
    (6, re.compile(r"^\(([가-하거-허])\)\s*")),
    (7, re.compile(r"^([①-⑳])\s*")),
    (8, re.compile(r"^([㉮-㉻])\s*")),
]
SPECIAL = re.compile(r"^([□○■●◦∙ㆍ·\-–※▪▶◎◉☞*])\s*")


def fmt_dates(s, log, where):
    def full(m):
        y, mo, d = m.group("y"), int(m.group("m")), int(m.group("d"))
        new = f"{y}. {mo}. {d}."
        return new
    out = s
    pats = [
        re.compile(r"(?<![\d,])(?P<y>20\d{2})\s*년\s*(?P<m>\d{1,2})\s*월\s*(?P<d>\d{1,2})\s*일"),
        re.compile(r"(?<![\d,])(?P<y>20\d{2})\s*[.\-/]\s*(?P<m>\d{1,2})\s*[.\-/]\s*(?P<d>\d{1,2})(?![\d:])\.?"),
    ]
    for p in pats:
        def rep(m):
            new = full(m)
            if new != m.group(0):
                log.append((where, m.group(0), new, R_DATE))
            return new
        out = p.sub(rep, out)
    # 연도 없는 날짜(요일이 붙은 것): 10.31.(금) → 10. 31.(금), 10월 31일(금) → 10. 31.(금)
    p3 = re.compile(r"(?<![\d.,])(?P<m>\d{1,2})\s*(?:\.|월)\s*(?P<d>\d{1,2})\s*(?:\.|일)?(?=\s*\([월화수목금토일])")
    def rep3(m):
        new = f"{int(m.group('m'))}. {int(m.group('d'))}."
        if new != m.group(0):
            log.append((where, m.group(0), new, R_DATE))
        return new
    out = p3.sub(rep3, out)
    # 날짜와 요일 괄호 사이 공백 제거: '2026. 4. 3. (금)' → '2026. 4. 3.(금)'
    out2 = re.sub(r"(\d\.)\s+(\([월화수목금토일]\))", r"\1\2", out)
    if out2 != out:
        log.append((where, "날짜 뒤 요일 괄호 앞 공백", "붙여 씀", R_DATE))
    return out2


def fmt_times(s, log, where):
    p = re.compile(r"(?P<ap>오전|오후)?\s*(?<!\d)(?P<h>\d{1,2})\s*시(?![간각대절점])(?:\s*(?P<mi>\d{1,2})\s*분)?")
    def rep(m):
        h = int(m.group("h")); mi = int(m.group("mi") or 0)
        if m.group("ap") == "오후" and h < 12:
            h += 12
        if m.group("ap") == "오전" and h == 12:
            h = 0
        if h > 24 or mi > 59:
            return m.group(0)
        new = f"{h:02d}:{mi:02d}"
        lead = " " if m.group(0).startswith(" ") and not m.group("ap") else ""
        log.append((where, m.group(0).strip(), new, R_TIME))
        return lead + new
    out = p.sub(rep, s)
    # 이미 쌍점으로 쓴 시간의 한 자리 시: 9:30 → 09:30
    def rep2(m):
        new = f"{int(m.group(1)):02d}:{m.group(2)}"
        if new != m.group(0):
            log.append((where, m.group(0), new, R_TIME))
        return new
    out = re.sub(r"(?<![\d:])(\d):([0-5]\d)(?!\d)", rep2, out)
    return out


def fmt_colon(s, log, where):
    """항목 이름 뒤 쌍점: 앞 빈칸은 지우고 뒤는 한 칸. 숫자 사이(시각·비율)와 줄 끝 쌍점은 그대로."""
    def rep(m):
        new = ": "
        if m.group(0) != new:
            log.append((where, m.group(0).replace(" ", "␣"), new.replace(" ", "␣"), R_COLON))
        return new
    return re.sub(r"(?<![\d\s])\s*[:：]\s*(?=[^\s\d/])|(?<=[가-힣A-Za-z)\]])\s*[:：]\s*(?=\d)", rep, s)


# 띄어쓰기 확인(고치지 않고 표시만): 공문 관용구가 붙어 있거나 한글이 너무 길게 이어진 곳
SPACE_SUSPECT = [
    re.compile(r"[가-힣](?=바랍니다)"),                       # 주시기바랍니다
    re.compile(r"(?:하여|하고|하며|하니|하오니|으며)(?=(?:안전|교육|학생|학교|자료|제출|협조|운영|실시|추진|참고|확인))"),
    re.compile(r"[가-힣]{12,}"),
]


def spacing_check(lines):
    """붙여넣기 글에서 단어가 붙었을 수 있는 곳. 반환: 표시 목록(분류 '띄어쓰기 확인')."""
    import dateconv as dc
    out, seen = [], set()
    for i, ln in enumerate(lines, 1):
        for p in SPACE_SUSPECT:
            for m in p.finditer(ln):
                if re.fullmatch(r"[일이삼사오육칠팔구십백천만억조원정금整]+", m.group(0)):
                    continue  # 금액 한글 표기(일금…원정)는 붙여 쓰는 것이 맞음
                ctx = ln[max(0, m.start() - 10): m.end() + 10].strip()
                if (i, ctx) in seen:
                    continue
                seen.add((i, ctx))
                out.append({"분류": "띄어쓰기 확인", "위치": f"붙여넣기 글 {i}번째 줄", "원문": ctx, "설명": dc.msg(146)})
    return out


def item_of(line):
    for lvl, p in ITEM_PATTERNS:
        m = p.match(line)
        if m:
            return lvl, m
    return None, None


def format_body(lines, kinds, log):
    """lines: 본문 줄(붙임 앞까지). kinds: 'p' or 'row'. 반환: 고친 줄 목록"""
    out = []
    stack = []
    for i, (s, k) in enumerate(zip(lines, kinds)):
        where = f"본문 {i+1}번째 줄"
        if k == "row":
            out.append(s)
            continue
        orig = s
        t = s.strip()
        t = fmt_dates(t, log, where)
        t = fmt_times(t, log, where)
        t = fmt_colon(t, log, where)
        lvl, m = item_of(t)
        if lvl:
            sym = m.group(0).rstrip()
            rest = t[m.end():]
            newsym = sym + " "
            if m.group(0) != newsym:
                log.append((where, m.group(0), newsym, R_ITEM))
            while stack and stack[-1] >= lvl:
                stack.pop()
            stack.append(lvl)
            indent = "  " * (len(stack) - 1)
            t = indent + newsym + rest
        else:
            sm = SPECIAL.match(t)
            if sm and stack:
                t = "  " * len(stack) + sm.group(1) + " " + t[sm.end():]
            elif not sm:
                stack = [] if not stack else stack
        new_indent = len(t) - len(t.lstrip(" "))
        old_indent = len(orig) - len(orig.lstrip(" "))
        if lvl and new_indent != old_indent:
            log.append((where, f"들여쓰기 {old_indent}칸", f"{new_indent}칸", R_INDENT))
        out.append(t)
    return out


def strip_end(s):
    return re.sub(r"\s*끝\s*\.?\s*$", "", s)


def format_paste(title, body, att, log):
    """body: [(text, kind)], att: [text] (붙임 줄들). 반환: 글"""
    title_f = fmt_times(fmt_dates(title.strip(), log, "제목"), log, "제목")
    # 본문에 붙은 '끝' 정리
    blines = [b for b, _ in body]
    bkinds = [k for _, k in body]
    had_end = bool(blines) and re.search(r"끝\s*\.?\s*$", blines[-1] or "") is not None
    if blines:
        blines[-1] = strip_end(blines[-1]) if bkinds[-1] != "row" else blines[-1]
    # 관련 항목이 없으면 맨 앞에 '1. 관련: '을 넣고 첫째 항목 번호를 하나씩 미룬다
    inserted = False
    if not any(k == "p" and re.match(r"^\s*(?:\d{1,2}\.\s*)?관\s*련", b) for b, k in zip(blines, bkinds)):
        top = [i for i, (b, k) in enumerate(zip(blines, bkinds)) if k == "p" and re.match(r"^\s*\d{1,2}\.(?!\d)", b)]
        if top:
            for i in top:
                m = re.match(r"^(\s*)(\d{1,2})\.(?!\d)", blines[i])
                new = f"{m.group(1)}{int(m.group(2)) + 1}." + blines[i][m.end():]
                log.append((f"본문 {i+1}번째 줄", blines[i][:30], new[:30], R_REL))
                blines[i] = new
        else:
            for i, (b, k) in enumerate(zip(blines, bkinds)):
                if k == "p" and b.strip():
                    log.append((f"본문 {i+1}번째 줄", b.strip()[:30], ("2. " + b.strip())[:30], R_REL))
                    blines[i] = "2. " + b.strip()
                    break
        blines.insert(0, "1. 관련: "); bkinds.insert(0, "p")
        log.append(("본문 1번째 줄", "(관련 항목 없음)", "1. 관련: ", R_REL))
        inserted = True
    fb = format_body(blines, bkinds, log)
    if inserted:
        fb[0] = "1. 관련: "
    # 붙임
    items = []
    if att:
        first = att[0].strip()
        m = re.match(r"^붙\s*임\s*[:：]?\s*", first)
        if m and m.group(0) != "붙임" + " " * (len(m.group(0)) - 2):
            pass
        if m and re.sub(r"\s", "", m.group(0)).rstrip(":：") == "붙임" and m.group(0).replace(" ", "") != "붙임":
            log.append(("붙임", m.group(0).strip(), "붙임", R_ATT))
        first = first[m.end():] if m else first
        raw_items = [first] + [a.strip() for a in att[1:]]
        for a in raw_items:
            a = strip_end(a).strip()
            if not a:
                continue
            a = re.sub(r"^\d{1,2}\.\s*", "", a)
            items.append(fmt_times(fmt_dates(a, log, "붙임"), log, "붙임"))
    lines = list(fb)
    if items:
        if len(items) == 1:
            att_lines = ["붙임  " + items[0] + "  끝."]
        else:
            att_lines = ["붙임  1. " + items[0]] + [f"      {i}. {x}" for i, x in enumerate(items[1:], 2)]
            att_lines[-1] += "  끝."
        orig_first = att[0].strip()
        if att_lines[0] != orig_first:
            log.append(("붙임", orig_first[:60], att_lines[0][:60], R_ATT))
        lines += [""] + att_lines
        if had_end:
            log.append(("본문 끝", "본문 끝의 '끝.'", "붙임 표시문 다음으로 옮김", R_END))
    else:
        if lines and bkinds and bkinds[-1] == "row":
            lines.append("  끝.")
            log.append(("본문 끝", "(표로 끝남)", "다음 줄 왼쪽 기본선에서 2타 띄우고 '끝.'", R_END))
        elif lines:
            old = body[-1][0]
            lines[-1] = lines[-1].rstrip() + "  끝."
            if not re.search(r"\S  끝\.$", old.rstrip()):
                log.append(("본문 끝", old.rstrip()[-20:], lines[-1][-20:], R_END))
    return title_f, lines, items
