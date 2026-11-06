# -*- coding: utf-8 -*-
# v3 복사본: 기본 연도값을 없앰(대상 학년도는 dateconv.configure로 정함)
"""zip+XML 문서(hwpx/docx/xlsx/odt)의 글자만 바꾸는 도구.

문단 단위로 글을 이어 붙여 날짜 엔진에 넣고, 바뀐 부분을 원래 글자 노드에
다시 나누어 넣는다(여러 run에 나뉜 글 처리). 구조·서식 요소는 건드리지 않는다.
"""
import io, re, zipfile, copy
from lxml import etree
import dateconv as dc

HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
X = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
TX = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
TB = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
DR = "{urn:oasis:names:tc:opendocument:xmlns:drawing:1.0}"
OFF = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"

MODES = {
    "hwpx": dict(P={HP + "p"}, T={HP + "t"}, TABLE={HP + "tbl"}, HEAD={HP + "header", HP + "footer"}),
    "docx": dict(P={W + "p"}, T={W + "t"}, TABLE={W + "tbl"}, HEAD=set()),
    "xlsx": dict(P={X + "si", X + "is"}, T={X + "t"}, TABLE=set(), HEAD=set()),
    "odt": dict(P={TX + "p", TX + "h"}, T=None, TABLE={TB + "table"}, HEAD={"{urn:oasis:names:tc:opendocument:xmlns:style:1.0}header",
                                                                   "{urn:oasis:names:tc:opendocument:xmlns:style:1.0}footer"}),
}
ODT_SKIP = {OFF + "annotation", TX + "note-citation"}


def segments(p, mode):
    cfg = MODES[mode]
    P, T = cfg["P"], cfg["T"]
    segs = []
    if mode == "odt":
        segs.append((p, "text"))

    def rec(e):
        for c in e:
            if not isinstance(c.tag, str):
                if mode == "odt":
                    segs.append((c, "tail"))
                continue
            if c.tag in P:
                if mode == "odt":
                    segs.append((c, "tail"))
                continue
            if mode == "odt":
                if c.tag in ODT_SKIP or c.tag == DR + "frame":
                    # frame 안의 문단은 따로 처리됨
                    segs.append((c, "tail"))
                    continue
                segs.append((c, "text")); rec(c); segs.append((c, "tail"))
            else:
                if c.tag in T:
                    segs.append((c, "text"))
                    for cc in c:
                        segs.append((cc, "tail"))
                else:
                    rec(c)
    rec(p)
    return segs


def _get(e, a):
    v = e.text if a == "text" else e.tail
    return v or ""


def _set(e, a, v):
    if a == "text":
        e.text = v
    else:
        e.tail = v


def apply_reps(segs, reps):
    offs, pos = [], 0
    for e, a in segs:
        s = _get(e, a)
        offs.append((pos, pos + len(s)))
        pos += len(s)
    for a0, b0, new in sorted(reps, key=lambda r: -r[0]):
        # 시작 조각
        si = None
        for i, (s, e) in enumerate(offs):
            if s <= a0 < e:
                si = i; break
        if si is None:
            continue
        first = True
        for i in range(si, len(segs)):
            s, e = offs[i]
            if s >= b0 and not first:
                break
            el, at = segs[i]
            txt = _get(el, at)
            lo = max(a0, s) - s
            hi = min(b0, e) - s
            if first:
                txt = txt[:lo] + new + txt[hi:]
                first = False
            else:
                txt = txt[:lo] + txt[hi:]
            _set(el, at, txt)
            if e >= b0:
                break


def where_of(p, mode, part):
    cfg = MODES[mode]
    anc = set(a.tag for a in p.iterancestors())
    if anc & cfg["HEAD"] or re.search(r"header|footer|styles", part):
        return "머리말·꼬리말"
    if anc & cfg["TABLE"]:
        return "표"
    return "본문"


def process_xml(data, mode, part, log, base_sy, with_flags=True, years=None):
    parser = etree.XMLParser(remove_blank_text=False, huge_tree=True)
    root = etree.fromstring(data, parser)
    tree = root.getroottree()
    changed = False
    n = 0
    for p in list(root.iter(*MODES[mode]["P"])):
        segs = segments(p, mode)
        txt = "".join(_get(e, a) for e, a in segs)
        if not txt.strip():
            continue
        n += 1
        w = f"{where_of(p, mode, part)} {n}번째 문단"
        new, ch, fl, reps = dc.convert(txt, base_sy=base_sy, years=years, where=w)
        log["changes"] += ch
        log["flags"] += fl
        if with_flags:
            log["flags"] += dc.find_flags(txt, where=w)
        log["texts_old"].append(txt)
        log["texts_new"].append(new)
        if reps and new != txt:
            apply_reps(segs, reps)
            chk = "".join(_get(e, a) for e, a in segs)
            if chk != new:
                log["errors"].append(f"{w}: 글 다시 맞추기 불일치")
            changed = True
    if not changed:
        return None
    di = tree.docinfo
    out = etree.tostring(root, xml_declaration=True, encoding=di.encoding or "UTF-8",
                         standalone=di.standalone)
    return out


def text_member(data, log, base_sy, where, years=None):
    # v3: UTF-16은 BOM이 있을 때만(BOM 없는 cp949 글을 UTF-16으로 잘못 읽지 않게)
    encs = ("utf-16",) if data[:2] in (bytes([0xFF, 0xFE]), bytes([0xFE, 0xFF])) else ("utf-8-sig", "cp949")
    for enc in encs:
        try:
            s = data.decode(enc); break
        except Exception:
            continue
    else:
        return None
    new, ch, fl, reps = dc.convert(s, base_sy=base_sy, years=years, where=where)
    log["changes"] += ch
    log["flags"] += fl
    if enc == "utf-8-sig" and not data.startswith(bytes([0xEF, 0xBB, 0xBF])):
        enc = "utf-8"  # v3: 원래 BOM이 없으면 BOM을 붙이지 않음
    return new.encode(enc) if new != s else None


XML_PARTS = {
    "hwpx": re.compile(r"^Contents/section\d+\.xml$|^Contents/content\.hpf$"),
    "docx": re.compile(r"^word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$|^docProps/core\.xml$"),
    "xlsx": re.compile(r"^xl/sharedStrings\.xml$|^xl/worksheets/sheet\d+\.xml$"),
    "odt": re.compile(r"^(content|styles|meta)\.xml$"),
}


def new_log():
    return {"changes": [], "flags": [], "errors": [], "texts_old": [], "texts_new": []}


def convert_zipdoc(src_bytes, mode, base_sy=None, extra=None, years=None):
    """반환: (new bytes, log)"""
    log = new_log()
    zin = zipfile.ZipFile(io.BytesIO(src_bytes))
    outb = io.BytesIO()
    zout = zipfile.ZipFile(outb, "w")
    for info in zin.infolist():
        data = zin.read(info.filename)
        new = None
        name = info.filename
        if XML_PARTS[mode].match(name):
            if mode in ("docx",) and name.startswith("docProps"):
                new = text_member_xml_simple(data, log, base_sy, years)
            elif mode == "hwpx" and name.endswith("content.hpf"):
                new = text_member_xml_simple(data, log, base_sy, years)
            elif mode == "odt" and name == "meta.xml":
                new = text_member_xml_simple(data, log, base_sy, years)
            else:
                new = process_xml(data, mode, name, log, base_sy, years=years)
        elif mode == "hwpx" and name == "Preview/PrvText.txt":
            new = text_member(data, new_log(), base_sy, "미리보기", years)
        if extra and name in extra:
            new = extra[name](new if new is not None else data, log)
        ni = copy.copy(info)
        zout.writestr(ni, new if new is not None else data, compress_type=info.compress_type)
    zout.close()
    return outb.getvalue(), log


def text_member_xml_simple(data, log, base_sy, years=None):
    """메타데이터(제목 등): 요소 글자를 하나씩 바꾼다."""
    root = etree.fromstring(data)
    ch = False
    for e in root.iter():
        if not isinstance(e.tag, str) or etree.QName(e).localname not in ("title", "subject", "description"):
            continue
        if e.text and e.text.strip():
            new, c, f, r = dc.convert(e.text, base_sy=base_sy, years=years, where="문서 정보")
            if new != e.text:
                e.text = new; ch = True
                log["changes"] += c
    if not ch:
        return None
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=root.getroottree().docinfo.standalone)


def plain_text(src_bytes, mode):
    """기준 학년도 판단용: XML 글자만 모은다."""
    out = []
    z = zipfile.ZipFile(io.BytesIO(src_bytes))
    for n in z.namelist():
        if XML_PARTS[mode].match(n) and not re.search(r"content\.hpf|docProps|meta\.xml", n):
            try:
                root = etree.fromstring(z.read(n), etree.XMLParser(huge_tree=True))
                out.append(" ".join(t for t in root.itertext()))
            except Exception:
                pass
    return chr(10).join(out)
