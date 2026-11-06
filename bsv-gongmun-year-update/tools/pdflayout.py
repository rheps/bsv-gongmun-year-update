# -*- coding: utf-8 -*-
"""서식 PDF(견적서·양식처럼 표·괘선·도장·로고·가로 쪽으로 짠 PDF) 판정과 고칠 날짜 목록.

판정(쪽마다 보고, 한 쪽이라도 맞으면 서식 PDF):
  G  표가 있거나(PyMuPDF find_tables) 괘선·사각형 그리기가 LINES_MIN개 이상
  I  그림(도장·로고·사진)이 있음
  W  가로 쪽(너비 > 높이)
  B  위치를 따로 잡은 글 덩어리가 BLOCKS_MIN개 이상
  서식 = G 이거나, I·W·B 가운데 두 가지 이상.
글만 있는 PDF(G 없음, 그림·가로·덩어리 가운데 하나 이하)는 예전처럼 hwpx로 다시 만든다.
서식 PDF는 다시 만들면 표 칸이 같은 너비로 바뀌고 글자가 세로로 갈라지며 도장·로고가 빠지고 쪽이 늘어나므로,
원본을 그대로 두고 바꿔야 할 날짜(쪽·위치·원래 → 새)만 목록으로 만든다.
"""
import re
import dateconv as dc

LINES_MIN = 10
BLOCKS_MIN = 25


def _L(p):
    import os
    p = os.path.abspath(p)
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


def page_signals(page):
    try:
        tabs = len(page.find_tables().tables)
    except Exception:
        tabs = 0
    lines = 0
    for d in page.get_drawings():
        for it in d.get("items", []):
            if it and it[0] in ("l", "re", "qu"):
                lines += 1
    blocks = len([b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()])
    s = {"표": tabs, "괘선": lines, "그림": len(page.get_images()), "가로": page.rect.width > page.rect.height, "글덩어리": blocks}
    g = tabs > 0 or lines >= LINES_MIN
    others = sum([s["그림"] > 0, s["가로"], blocks >= BLOCKS_MIN])
    s["서식"] = bool(g or others >= 2)
    return s


def detect(path):
    """반환: {"서식": bool, "쪽": [쪽별 신호], "기준": 설명}"""
    import pymupdf as fitz
    d = fitz.open(_L(path))
    try:
        pages = [page_signals(p) for p in d]
    finally:
        d.close()
    return {"서식": any(p["서식"] for p in pages), "쪽": pages,
            "기준": f"표 또는 괘선 {LINES_MIN}개 이상, 또는 그림·가로 쪽·글 덩어리 {BLOCKS_MIN}개 이상 가운데 두 가지 이상"}


def page_text(path):
    import pymupdf as fitz
    d = fitz.open(_L(path))
    try:
        return "\n".join(p.get_text() for p in d)
    finally:
        d.close()


def _lines(page):
    """줄마다 (글, 글자 상자 목록)."""
    out = []
    raw = page.get_text("rawdict")
    for b in raw.get("blocks", []):
        if b.get("type") != 0:
            continue
        for ln in b.get("lines", []):
            chars = [c for sp in ln.get("spans", []) for c in sp.get("chars", [])]
            if not chars:
                continue
            out.append(("".join(c["c"] for c in chars), [tuple(c["bbox"]) for c in chars]))
    return out


def planned_dates(path, base_sy, years, with_flags=True):
    """원본을 바꾸지 않고, 바꿨다면 달라질 곳을 쪽·상자와 함께 돌려준다.
    반환: (항목 목록, 바꿈 목록, 표시 목록). 항목: {쪽, 줄, 원문, 새글, 원래날짜, 새날짜, 새요일, 상자}"""
    import pymupdf as fitz
    d = fitz.open(_L(path))
    items, changes, flags = [], [], []
    try:
        for pno, page in enumerate(d, 1):
            for li, (txt, boxes) in enumerate(_lines(page), 1):
                if not txt.strip():
                    continue
                where = dc.msg(143, N=pno)
                new, ch, fl, reps = dc.convert(txt, base_sy=base_sy, years=years, where=where)
                flags += fl
                if with_flags:
                    flags += dc.find_flags(txt, where=where)
                byraw = {}
                for c in ch:
                    byraw.setdefault(c.get("원문", "").strip().lstrip(" ~∼～-"), []).append(c)
                for a, b, v in sorted(reps):
                    old = txt[a:b]
                    if old == v:
                        continue
                    k = len(old) - len(old.lstrip(" ~∼～-"))
                    a, old, v = a + k, old[k:].rstrip(), v[len(v) - len(v.lstrip(" ~∼～-")):].rstrip()
                    b = a + len(old)
                    bb = [x for x in boxes[a:b] if x[2] > x[0]]
                    box = [min(x[0] for x in bb), min(x[1] for x in bb), max(x[2] for x in bb), max(x[3] for x in bb)] if bb else None
                    c = (byraw.get(old.strip().lstrip(" ~∼～-")) or [{}])[0]
                    items.append({"쪽": pno, "줄": li, "원문": old, "새글": v, "원래날짜": c.get("원래날짜"),
                                  "새날짜": c.get("새날짜"), "새요일": c.get("새요일"), "규칙": c.get("규칙"),
                                  "상자": [round(x, 2) for x in box] if box else None,
                                  "쪽크기": [round(page.rect.width, 2), round(page.rect.height, 2)]})
                for c in ch:
                    c = dict(c); c["쪽"] = pno; c["줄"] = li
                    changes.append(c)
    finally:
        d.close()
    return items, changes, flags
