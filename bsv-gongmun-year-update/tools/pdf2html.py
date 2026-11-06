# -*- coding: utf-8 -*-
"""글자 PDF → 표·문단을 살린 HTML (한글에서 열어 hwpx로 저장하기 위한 중간 파일)."""
import html
import pymupdf as fitz


def pdf_to_html(path):
    d = fitz.open(path)
    out = ['<html><head><meta charset="utf-8"><style>table{border-collapse:collapse;width:100%}td{border:1px solid #000;padding:2px 4px;word-break:break-all}</style></head><body>']
    for pno, page in enumerate(d):
        items = []
        try:
            tabs = page.find_tables().tables
        except Exception:
            tabs = []
        boxes = [fitz.Rect(t.bbox) for t in tabs]
        for t in tabs:
            rows = t.extract()
            # 모든 행에서 비어 있는 열은 뺀다(잘게 나뉜 격자 때문에 생기는 빈 열)
            if rows:
                ncol = max(len(rw) for rw in rows)
                keep = [j for j in range(ncol) if any(j < len(rw) and (rw[j] or "").strip() for rw in rows)]
                rows = [[rw[j] if j < len(rw) else "" for j in keep] for rw in rows]
                rows = [rw for rw in rows if any((c or "").strip() for c in rw)]
            h = ["<table>"]
            for row in rows:
                h.append("<tr>" + "".join(f"<td>{html.escape(c or '').replace(chr(10), '<br>')}</td>" for c in row) + "</tr>")
            h.append("</table>")
            items.append((t.bbox[1], "".join(h)))
        for b in page.get_text("blocks"):
            x0, y0, x1, y1, txt, _, typ = b
            if typ != 0 or not txt.strip():
                continue
            r = fitz.Rect(x0, y0, x1, y1)
            if any(r.intersects(bx) and (r & bx).get_area() > 0.5 * r.get_area() for bx in boxes):
                continue
            lines = [html.escape(l) for l in txt.strip().split("\n")]
            items.append((y0, "<p>" + "<br>".join(lines) + "</p>"))
        items.sort(key=lambda x: x[0])
        out += [s for _, s in items]
        if pno < len(d) - 1:
            out.append('<p style="page-break-before:always"></p>')
    out.append("</body></html>")
    return "\n".join(out), len(d)
