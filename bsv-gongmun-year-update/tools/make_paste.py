# -*- coding: utf-8 -*-
"""변환한 odt 공문에서 제목·본문·붙임 줄을 읽는다(업무관리시스템 붙여넣기 글 재료)."""
import io, re, zipfile
import xmlconv
from lxml import etree

B = chr(92)


def L(p):
    import os
    p = os.path.abspath(p)
    return p if p.startswith(B + B + "?" + B) else B + B + "?" + B + p


T, TB, DR, OFF = xmlconv.TX, xmlconv.TB, xmlconv.DR, xmlconv.OFF


R_JOIN = "odt 문단 구조대로 이음. 줄이 바뀐 곳은 낱말 사이를 한 칸 띄우고, 붙임표(-)로 끝난 줄은 띄우지 않음"


def odt_ptext(p, log=None, where=""):
    """odt 문단 글. 빈칸 요소(text:s, c개), 탭은 빈칸으로, 문단 안 줄바꿈(text:line-break)은
    단어 사이면 한 칸으로 잇는다. 붙임표(-)로 끝난 줄과 이미 빈칸이 있는 곳은 빈칸을 더하지 않는다.
    (xmlconv.segments는 날짜 바꾸기용이라 빈칸 요소를 글로 세지 않으므로 여기서 따로 채운다.)"""
    out = []
    for e, a in xmlconv.segments(p, "odt"):
        if a == "text" and isinstance(e.tag, str):
            if e.tag == T + "s":
                try:
                    n = int(e.get(T + "c") or 1)
                except ValueError:
                    n = 1
                out.append(" " * max(n, 1))
            elif e.tag == T + "tab":
                out.append(" ")
            elif e.tag == T + "line-break":
                out.append("\n")
        out.append(xmlconv._get(e, a))
    s = "".join(out)
    if "\n" not in s:
        return s
    parts = s.split("\n")
    res = parts[0]
    for nxt in parts[1:]:
        if not res or not nxt or res[-1].isspace() or nxt[0].isspace():
            res += nxt
        elif res[-1] in "-‐­":
            res = (res[:-1] if res[-1] == "­" else res) + nxt
            if log is not None:
                log.append((where or "본문", res[-12:] + "/" + nxt[:8], "붙여 씀", R_JOIN))
        else:
            if log is not None:
                log.append((where or "본문", res[-8:] + "/" + nxt[:8], res[-8:] + " " + nxt[:8], R_JOIN))
            res += " " + nxt
    return res


def parse(odt, log=None):
    data = odt if isinstance(odt, (bytes, bytearray)) else open(L(odt), "rb").read()
    z = zipfile.ZipFile(io.BytesIO(data))
    root = etree.fromstring(z.read("content.xml"))
    body = root.find(".//" + OFF + "text")
    lines = []

    def ptext(p):
        return odt_ptext(p, log)

    def walk(e):
        for c in e:
            if c.tag in (T + "p", T + "h"):
                own = ptext(c)
                if own.strip():
                    lines.append(("p", own))
                frames = [f for f in c.iter(DR + "frame")
                          if not any(a.tag == DR + "frame" for a in f.iterancestors() if a is not c and c in a.iterancestors() or False)
                          and not [a for a in f.iterancestors() if a.tag == DR + "frame"]]
                for f in frames:
                    alltext = "".join(f.itertext())
                    is_head = "제목" in alltext and "수신" in alltext
                    is_foot = any(k in alltext for k in ("협조자", "시행", "접수", "공개"))
                    tables = [tb for tb in f.iter(TB + "table")
                              if not [a for a in tb.iterancestors() if a.tag == TB + "table"]]
                    if is_head or is_foot or not tables:
                        for pp in f.iter(T + "p", T + "h"):
                            lines.append(("frame", ptext(pp)))
                        continue
                    for tb in tables:
                        for row in tb.iter(TB + "table-row"):
                            cells = [" ".join(ptext(pp).strip() for pp in cell.iter(T + "p")).strip()
                                     for cell in row.findall(TB + "table-cell")]
                            if any(cells):
                                lines.append(("row", "\t".join(cells)))
            elif c.tag == TB + "table":
                for row in c.iter(TB + "table-row"):
                    cells = [" ".join(ptext(pp) for pp in cell.iter(T + "p")).strip() for cell in row.findall(TB + "table-cell")]
                    lines.append(("row", "\t".join(cells)))
            elif c.tag in (T + "list", T + "list-item", T + "section"):
                walk(c)
    walk(body)
    allf = [s.strip() for k, s in lines if s.strip()]
    title = ""
    for i, s in enumerate(allf):
        if s == "제목" and i + 1 < len(allf):
            title = allf[i + 1]; break
    main = [(s, k) for k, s in lines if k != "frame" and s.strip()]
    if title and title in [s.strip() for s, _ in main]:
        idx = [s.strip() for s, _ in main].index(title)
        main = main[idx + 1:]
    body, att, inatt = [], [], False
    for s, k in main:
        if k == "p" and re.match(r"^\s*붙\s*임", s):
            inatt = True
        if inatt:
            att.append(s)
        else:
            body.append((s, k))
        if re.search(r"끝\s*\.\s*$", s):
            break
    return title, body, att
