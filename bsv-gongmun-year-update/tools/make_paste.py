# -*- coding: utf-8 -*-
"""odt 공문을 글(txt)로 읽는다. odt 파일은 결과로 만들지 않는다.

- parse(): 공문 본문 odt에서 제목·본문·붙임 줄을 읽는다(업무관리시스템 붙여넣기 글 재료).
- plain_text(): 공문 본문 모양이 아닌 odt를 문단 순서대로 글로 옮긴다.

띄어쓰기 보존
- 빈칸 요소 text:s(text:c개), 탭 text:tab(탭 문자), 문단 안 줄바꿈 text:line-break를 글로 옮긴다.
- 문단 안 줄바꿈 뒤가 새 항목(1. 가. 1) …, 붙임, ※ 등)이거나 앞 줄이 문장 끝이면 줄을 바꾼다.
  그 밖의 줄바꿈은 화면 폭 때문에 나눈 줄로 보고 잇는다(낱말 사이 한 칸, 붙임표(-)로 끝난 줄은 붙여 씀).
- 자동 번호 목록(text:list)은 공문서 항목 기호(1.→가.→1)→가)→(1)→(가)→①→㉮)와 단계마다 2타 들여쓰기로 적는다.
"""
import io, re, zipfile
import xmlconv
import gongmun_format as gf
from lxml import etree

B = chr(92)


def L(p):
    import os
    p = os.path.abspath(p)
    return p if p.startswith(B + B + "?" + B) else B + B + "?" + B + p


T, TB, DR, OFF = xmlconv.TX, xmlconv.TB, xmlconv.DR, xmlconv.OFF
ST = "{urn:oasis:names:tc:opendocument:xmlns:style:1.0}"
FO = "{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}"

R_JOIN = "odt 문단 구조대로 이음. 쪽 너비 때문에 나뉜 줄은 낱말 사이를 한 칸 띄우고, 붙임표(-)로 끝난 줄은 띄우지 않음"
R_BREAK = "odt 문단 안 줄 바꿈을 그대로 둠. 다음 줄이 새 항목이나 붙임으로 시작하거나 앞 줄에서 문장이 끝남"
R_LIST = "odt 자동 목록 번호를 공문서 항목 기호(1.→가.→1)→가)→(1)→(가))로 적고 단계마다 2타씩 들여 씀"

HANGUL = "가나다라마바사아자차카타파하"
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
CIRCLED_HANGUL = "㉮㉯㉰㉱㉲㉳㉴㉵㉶㉷㉸㉹㉺㉻"


def _hangul(n):
    """1→가, 14→하, 15→거 …(공문서 항목 기호 순서)."""
    if n <= len(HANGUL):
        return HANGUL[n - 1]
    k = (n - 1) % len(HANGUL)
    # 거너더러머버서어저처커터퍼허: 같은 첫소리에 모음 ㅓ
    base = ord(HANGUL[k]) - 0xAC00
    return chr(0xAC00 + (base // 588) * 588 + 4 * 28)


def item_label(depth, n):
    """공문서 항목 기호: 깊이 1부터 1. 가. 1) 가) (1) (가) ① ㉮"""
    d = (depth - 1) % 8 + 1
    if d == 1:
        return f"{n}."
    if d == 2:
        return f"{_hangul(n)}."
    if d == 3:
        return f"{n})"
    if d == 4:
        return f"{_hangul(n)})"
    if d == 5:
        return f"({n})"
    if d == 6:
        return f"({_hangul(n)})"
    if d == 7:
        return CIRCLED[n - 1] if n <= len(CIRCLED) else f"({n})"
    return CIRCLED_HANGUL[n - 1] if n <= len(CIRCLED_HANGUL) else f"({_hangul(n)})"


def _hard_break(prev, nxt):
    """문단 안 줄바꿈을 줄바꿈으로 둘지(True) 이을지(False)."""
    if not prev.strip() or not nxt.strip():
        return True
    n = nxt.lstrip()
    if gf.item_of(n)[0]:
        return True
    if gf.SPECIAL.match(n) and not re.match(r"[-–~∼～]\s*\d", n):
        return True
    if re.match(r"붙\s*임|※|<|\[|【|「", n):
        return True
    if re.search(r"(?:[다요]\.|[함음임됨]\.?|[:：])\s*$", prev):
        return True
    return False


def odt_ptext(p, log=None, where=""):
    """odt 문단 글. 빈칸 요소(text:s, c개)는 그 수만큼 빈칸, 탭(text:tab)은 탭 문자로 옮긴다.
    문단 안 줄바꿈(text:line-break)은 _hard_break가 참이면 줄바꿈(\\n)으로 두고, 아니면 잇는다.
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
                out.append("\t")
            elif e.tag == T + "line-break":
                out.append("\n")
        out.append(xmlconv._get(e, a))
    s = "".join(out)
    if "\n" not in s:
        return s
    parts = s.split("\n")
    res = parts[0]
    for nxt in parts[1:]:
        last = res.rsplit("\n", 1)[-1]
        if _hard_break(last, nxt):
            if log is not None and last.strip() and nxt.strip():
                log.append((where or "본문", last.strip()[-12:] + "/" + nxt.strip()[:8], "줄 바꿈 유지", R_BREAK))
            res += "\n" + nxt
        elif last[-1].isspace() or nxt[0].isspace():
            res += nxt
        elif last[-1] in "-‐­":
            res = (res[:-1] if res[-1] == "­" else res) + nxt
            if log is not None:
                log.append((where or "본문", last[-12:] + "/" + nxt[:8], "붙여 씀", R_JOIN))
        elif last[-1] in "~∼～" or re.match(r"[-–~∼～]\s*\d", nxt):
            res += nxt   # 09:10 / -09:40 처럼 범위가 나뉜 줄
        else:
            if log is not None:
                log.append((where or "본문", last[-8:] + "/" + nxt[:8], last[-8:] + " " + nxt[:8], R_JOIN))
            res += " " + nxt
    return res


# ------------------------------------------------------------------ 목록 번호
class ListStyles:
    """text:list-style 이름 → {단계: ("number", num-format) | ("bullet", 글자) | ("none", "")}"""

    def __init__(self, roots):
        self.s = {}
        for root in roots:
            if root is None:
                continue
            for ls in root.iter(T + "list-style"):
                name = ls.get(ST + "name")
                lv = {}
                for c in ls:
                    if not isinstance(c.tag, str):
                        continue
                    try:
                        k = int(c.get(T + "level") or 1)
                    except ValueError:
                        k = 1
                    if c.tag == T + "list-level-style-number":
                        fmt = c.get(ST + "num-format")
                        lv[k] = ("number", fmt) if fmt else ("none", "")
                    elif c.tag == T + "list-level-style-bullet":
                        ch = c.get(T + "bullet-char") or ""
                        ok = ch and not (0xE000 <= ord(ch[0]) <= 0xF8FF) and ch.strip()
                        lv[k] = ("bullet", ch if ok else "-")
                    else:
                        lv[k] = ("bullet", "-")
                if name:
                    self.s[name] = lv

    def kind(self, style, level):
        return self.s.get(style or "", {}).get(level) or ("none", "")


def _read_styles(z):
    roots = []
    for n in ("content.xml", "styles.xml"):
        try:
            roots.append(etree.fromstring(z.read(n), etree.XMLParser(huge_tree=True)))
        except Exception:
            roots.append(None)
    return roots


class Walker:
    """odt 본문을 (종류, 글) 줄로 옮긴다. 종류: p(문단), row(표 한 줄, 칸은 탭), frame(글상자 안 문단), blank(빈 문단)."""

    def __init__(self, styles, log=None, frames="split"):
        self.styles = styles
        self.log = log
        self.frames = frames   # "split": 공문 머리·끝 글상자 구분(parse), "inline": 문서 순서대로(plain)
        self.lines = []
        self.counters = {}

    def ptext(self, p):
        return odt_ptext(p, self.log)

    def add_p(self, text, kind="p", prefix="", indent="", in_list=False):
        """in_list: 목록 항목 안 문단. 줄바꿈 뒤 손으로 쓴 하위 항목(가. 등)은 한 단계(2타) 더 들여 쓴다."""
        parts = text.split("\n")
        for i, part in enumerate(parts):
            if not part.strip():
                if kind == "p" and len(parts) == 1:
                    self.lines.append(("blank", ""))
                continue
            if i == 0 and prefix:
                body = part.lstrip()
                if gf.item_of(body)[0] or gf.SPECIAL.match(body):
                    self.lines.append((kind, indent + body))   # 이미 손으로 쓴 기호가 있으면 더하지 않음
                else:
                    self.lines.append((kind, indent + prefix + " " + body))
            elif in_list and i > 0 and (gf.item_of(part.lstrip())[0] or gf.SPECIAL.match(part.lstrip())):
                self.lines.append((kind, indent + "  " + part.lstrip()))
            elif indent:
                self.lines.append((kind, indent + part.lstrip()))
            else:
                self.lines.append((kind, part))

    def cell_text(self, cell):
        return " ".join(self.ptext(pp).replace("\n", " ").strip() for pp in cell.iter(T + "p", T + "h")).strip()

    def table(self, tb):
        for row in tb.iter(TB + "table-row"):
            if [a for a in row.iterancestors() if a.tag == TB + "table"][0] is not tb:
                continue
            cells = [self.cell_text(cell) for cell in row.findall(TB + "table-cell")]
            if any(cells):
                self.lines.append(("row", "\t".join(cells)))

    def frames_of(self, c):
        return [f for f in c.iter(DR + "frame")
                if not [a for a in f.iterancestors() if a.tag == DR + "frame"]]

    def para(self, c, prefix="", indent="", in_list=False):
        own = self.ptext(c)
        self.add_p(own, "p", prefix, indent, in_list)
        for f in self.frames_of(c):
            if self.frames == "inline":
                self.walk(f)
                continue
            alltext = "".join(f.itertext())
            is_head = "제목" in alltext and "수신" in alltext
            is_foot = any(k in alltext for k in ("협조자", "시행", "접수", "공개"))
            tables = [tb for tb in f.iter(TB + "table") if not [a for a in tb.iterancestors() if a.tag == TB + "table"]]
            if is_head or is_foot or not tables:
                for pp in f.iter(T + "p", T + "h"):
                    self.add_p(self.ptext(pp), "frame")
                continue
            for tb in tables:
                self.table(tb)

    def walk(self, e, depth=0, style=None):
        for c in e:
            if not isinstance(c.tag, str) or c.tag in xmlconv.ODT_SKIP:
                continue
            if c.tag in (T + "p", T + "h"):
                self.para(c)
            elif c.tag == TB + "table":
                self.table(c)
            elif c.tag == T + "list":
                self.list(c, depth + 1, c.get(T + "style-name") or style)
            elif c.tag in (T + "sequence-decls", T + "variable-decls", T + "user-field-decls", OFF + "forms",
                           T + "tracked-changes", OFF + "annotation"):
                continue
            else:
                self.walk(c, depth, style)

    def list(self, lst, depth, style):
        cont = lst.get(T + "continue-numbering") == "true" or lst.get(T + "continue-list")
        if not cont:
            self.counters[depth] = 0
        for k in [k for k in self.counters if k > depth]:
            del self.counters[k]
        kind, val = self.styles.kind(style, depth)
        indent = "  " * (depth - 1)
        for item in lst:
            if not isinstance(item.tag, str):
                continue
            if item.tag not in (T + "list-item", T + "list-header"):
                continue
            label = ""
            if item.tag == T + "list-item":
                sv = item.get(T + "start-value")
                if sv and sv.isdigit():
                    self.counters[depth] = int(sv) - 1
                self.counters[depth] = self.counters.get(depth, 0) + 1
                if kind == "number":
                    label = item_label(depth, self.counters[depth])
                elif kind == "bullet":
                    label = val
            for k in [k for k in self.counters if k > depth]:
                del self.counters[k]
            first = True
            for c in item:
                if not isinstance(c.tag, str):
                    continue
                if c.tag in (T + "p", T + "h"):
                    n0 = len(self.lines)
                    self.para(c, label if first else "", indent if (label or depth > 1) else "", True)
                    if label and first and self.log is not None and len(self.lines) > n0:
                        self.log.append(("목록", self.lines[n0][1].strip()[:20], indent + label, R_LIST))
                    first = False
                elif c.tag == T + "list":
                    self.list(c, depth + 1, c.get(T + "style-name") or style)
                elif c.tag == TB + "table":
                    self.table(c)
                else:
                    self.walk(c, depth, style)


def _open(odt):
    data = odt if isinstance(odt, (bytes, bytearray)) else open(L(odt), "rb").read()
    z = zipfile.ZipFile(io.BytesIO(data))
    roots = _read_styles(z)
    return roots[0], ListStyles(roots)


def parse(odt, log=None):
    root, styles = _open(odt)
    body = root.find(".//" + OFF + "text")
    w = Walker(styles, log, frames="split")
    w.walk(body)
    lines = [(k, s) for k, s in w.lines if k != "blank"]
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


def plain_text(odt, log=None):
    """공문 본문 모양이 아닌 odt: 문단·글상자·표를 문서 순서대로 글로 옮긴다. 반환: 줄 목록.
    빈 문단은 빈 줄로 남기되 빈 줄이 셋 이상 이어지면 둘로 줄인다."""
    root, styles = _open(odt)
    body = root.find(".//" + OFF + "text")
    w = Walker(styles, log, frames="inline")
    w.walk(body)
    out = []
    for k, s in w.lines:
        if k == "blank":
            if len(out) >= 2 and out[-1] == "" and out[-2] == "":
                continue
            out.append("")
        else:
            out.append(s)
    while out and out[0] == "":
        out.pop(0)
    while out and out[-1] == "":
        out.pop()
    return out
