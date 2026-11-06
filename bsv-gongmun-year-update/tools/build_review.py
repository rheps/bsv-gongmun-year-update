# -*- coding: utf-8 -*-
"""검토표.xlsx 만들기(v3과 같은 시트: 요약, 파일별, 날짜 바꿈, 확인할 곳, 숫자 날짜, 서식 정리, 공휴일).
화면 문구는 이 폴더의 문구.txt(번호. 문구)에서 읽는다."""
import os, re, collections, datetime as dt
import dateconv as dc

HERE = os.path.dirname(os.path.abspath(__file__))


def L(p):
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + os.path.abspath(p)


def load_labels(tsy, path=None):
    lab = {}
    with open(path or os.path.join(HERE, "문구.txt"), encoding="utf-8") as fh:
        text = fh.read()
    for line in text.splitlines():
        m = re.match(r"(\d+)\.\s*(.*)", line.strip())
        if m:
            lab[int(m.group(1))] = m.group(2).replace("{Y}", str(tsy)).replace("{Y1}", str(tsy + 1))
    # 41번 문구 속 학년도는 대상 학년도로 맞춘다
    lab[41] = re.sub(r"20\d{2}학년도", f"{tsy}학년도", lab[41])
    return lab


CAT = {"이전 학교 정보": 47, "표어": 48, "교육지원청·관계 기관": 49, "주소·우편번호": 50, "전화·팩스": 51,
       "홈페이지·메일": 52, "회차": 53, "문서번호·시행번호": 54, "금액": 55, "중학교 기준·학교급": 56, "업체 이름": 57,
       "결재란": 58, "사람 이름 가능": 59, "원문 요일 오류": 60, "연도 없는 날짜": 61, "원래 주말 날짜": 62,
       "기간에 휴일 포함": 63, "공휴일 확인 불가": 64, "다른 연도 표기": 65, "바꾸지 않은 연도": 66,
       "연도 같은 숫자": 67, "바꾸지 않은 연도 숫자": 68, "관련 문서·법령 날짜": 69, "원래 다른 연도 문서": 70,
       "그림 포함(로고 등)": 71, "시트 이름 연도": 72, "수식 속 연도": 73, "기간 달 바뀜": 74, "고정 날짜": 75, "날짜일 수 있는 숫자": 89, "관련 안 법령 인용": 91,
       "다른 학년도 날짜": 100, "학년도 넘는 기간": 101, "여러 해 기간": 102, "날짜 순서 바뀜": 103, "기간 길이 바뀜": 104,
       "문서 학년도와 날짜 학년도 다름": 105, "OCR 확인 필요": 127,
       "원본 유지(서식 PDF)": 136, "날짜 순서 확인": 137, "띄어쓰기 확인": 145}
STAT = {"변환 완료": 30, "일부": 31, "변환 안 함": 32, "OCR 필요": 33, "오류": 34, "중복(같은 파일)": 35,
        "중복(hwp 일괄 변환본)": 36, "원본 유지(서식 PDF)": 136, "학생 자료(변환 안 함)": "d.student_status"}


def stat_label(st, lab):
    """상태 이름(화면 문구). 배포판에서 더한 상태는 배포문구.json에서 읽는다."""
    k = STAT.get(st)
    if isinstance(k, str):
        import json
        with open(os.path.join(HERE, "배포문구.json"), encoding="utf-8") as f:
            return json.load(f)[k]
    return lab[k] if k in lab else st
RULE = {"같은 주차·요일": 37, "같은 주차·요일(날짜 칸)": 37, "기간 끝날(길이 유지)": 38, "고정 날짜(월·일 유지)": 76,
        "숫자 날짜": 84, "관련 문서(번호 OOOO·월일 OO)": 90, "연도 → 대상 학년도": 96, "연-월(대상 학년도)": 97,
        "관련 줄 연도": 98, "연도 기간(같은 만큼)": 99, "딸린 날짜(같은 날수)": 138}


def build(results, vrows, info, dst, out_root, student_count=0, labels=None, holiday_dir=None):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter

    TSY = int(info["대상학년도"])
    LAB = labels or load_labels(TSY)

    def lab(table, k):
        if table is STAT:
            return stat_label(k, LAB)
        return LAB[table[k]] if k in table and table[k] in LAB else k

    V = {v["파일"]: v for v in (vrows or [])}
    wb = Workbook()
    HFONT = Font(bold=True)
    HFILL = PatternFill("solid", fgColor="DDEBF7")

    def sheet(ws, headers, rows, widths):
        ws.append(headers)
        for c in ws[1]:
            c.font = HFONT; c.fill = HFILL
        for r in rows:
            ws.append(r)
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

    def bundle(r):
        parts = r["rel"].split("/")
        return f"{r['zip']}/{parts[0]}" if len(parts) > 1 else r["zip"]

    def rel_out(p):
        return os.path.relpath(p, out_root).replace("\\", "/")

    files_rows, date_rows, flag_rows, fmt_rows, num_rows = [], [], [], [], []
    for i, r in enumerate(results, 1):
        outs = r.get("결과") or []
        vs = [V.get(o) for o in outs if V.get(o)]
        opened = ""
        vo = [v for v in vs if v.get("열림") is not None]
        if vo:
            opened = LAB[45] if all(v.get("열림") for v in vo) else LAB[46]
        pages = ""
        main = [v for v in vo if not v["파일"].endswith(".txt")]
        if main:
            v = main[0]
            pages = f"{v.get('원본쪽수') or '?'} → {v.get('쪽수') or '?'}"
        seen, uf = set(), []
        for f in r.get("표시", []):
            k = (f["분류"], f["원문"])
            if k in seen:
                continue
            seen.add(k); uf.append(f)
        extra = []
        for v in vs:
            if v.get("확인안함") and v["확인안함"] not in ("원본 그대로 복사",) and "--no-verify" not in v["확인안함"]:
                extra.append(v["확인안함"])
            if v.get("요일불일치"):
                extra.append("확인 필요: 새 파일에서 날짜와 요일이 맞지 않는 곳 " + ", ".join(x.replace("\r", "").replace("\n", "") for x in v["요일불일치"][:3])
                             + " (OCR로 날짜가 두 줄로 나뉘어 요일을 못 고침)")
        note = " / ".join(r.get("비고", []) + extra + [e for e in r.get("오류", []) if "Traceback" not in e])
        for f in r.get("서식정리", []):
            fmt_rows.append([i, r["zip"] + "/" + r["rel"], f["위치"], f["원래"], f["고친것"], f["근거"]])
        files_rows.append([i, bundle(r), r["zip"] + "/" + r["rel"], "\n".join(rel_out(o) for o in outs),
                           lab(STAT, r["상태"]), len([c for c in r.get("바꿈", []) if c.get("새날짜")]), len(uf), note,
                           LAB[45] if r.get("학생정보") else "", opened, pages, len(r.get("서식정리", []))])
        for c in r.get("바꿈", []):
            nd = f"{c['새날짜']}({c['새요일']})" if c.get("새날짜") else ""
            rl = lab(RULE, c.get("규칙", ""))
            date_rows.append([i, r["zip"] + "/" + r["rel"], c.get("위치", ""), c.get("원문", "")[:120], c.get("새글", "")[:120],
                              c.get("원래날짜", ""), nd, rl, c.get("이동", "")])
            if c.get("규칙") == "숫자 날짜":
                conf = {"높음": LAB[86], "보통": LAB[87]}.get(c.get("확신"), c.get("확신", ""))
                num_rows.append([i, r["zip"] + "/" + r["rel"], c.get("위치", ""), c.get("원문", ""), c.get("새글", ""),
                                 c.get("원래날짜", ""), nd, conf, c.get("근거문맥", "")])
        for f in uf:
            flag_rows.append([i, r["zip"] + "/" + r["rel"], lab(CAT, f["분류"]), f.get("위치", ""), f.get("원문", "")[:150], f.get("설명", "")])

    # 요약
    ws = wb.active; ws.title = LAB[1]
    ws.append([LAB[41]]); ws.append([LAB[94]]); ws.append([LAB[42]]); ws.append([LAB[92]]); ws.append([LAB[93]]); ws.append([])
    ws.append([LAB[95], f"{TSY}학년도 ({info['대상기간']})"])
    for w in info.get("공휴일경고", []):
        ws.append([LAB[107], re.sub(r"^확인되지 않은 공휴일: ", "", w)])
    ws.append([LAB[44], len(results)])
    if student_count:
        ws.append([LAB[14], student_count])
    ws.append([])
    cnt = collections.Counter((r["상태"], r["ext"]) for r in results)
    exts = sorted({e for _, e in cnt})
    ws.append([LAB[10]] + exts + [LAB[44]])
    for c in ws[ws.max_row]:
        c.font = HFONT; c.fill = HFILL
    for st in STAT:
        row = [lab(STAT, st)] + [cnt.get((st, e), 0) for e in exts]
        row.append(sum(row[1:]))
        if row[-1]:
            ws.append(row)
    ws.append([])
    ws.append([LAB[24], LAB[44]])
    for c in ws[ws.max_row]:
        c.font = HFONT; c.fill = HFILL
    fc = collections.Counter(f[2] for f in flag_rows)
    for k, n in fc.most_common():
        ws.append([k, n])
    ws.column_dimensions["A"].width = 34
    for rr in range(1, 6):
        ws.cell(rr, 1).alignment = Alignment(wrap_text=False)

    sheet(wb.create_sheet(LAB[2]), [LAB[6], LAB[7], LAB[8], LAB[9], LAB[10], LAB[11], LAB[12], LAB[13], LAB[14], LAB[15], LAB[16], LAB[78]],
          files_rows, [6, 30, 70, 70, 14, 10, 10, 50, 9, 10, 12, 10])
    sheet(wb.create_sheet(LAB[3]), [LAB[6], LAB[8], LAB[17], LAB[18], LAB[19], LAB[20], LAB[21], LAB[22], LAB[23]],
          date_rows, [6, 60, 18, 40, 40, 12, 16, 20, 50])
    sheet(wb.create_sheet(LAB[4]), [LAB[6], LAB[8], LAB[24], LAB[17], LAB[18], LAB[25]],
          flag_rows, [6, 60, 22, 18, 60, 60])
    sheet(wb.create_sheet(LAB[83]), [LAB[6], LAB[8], LAB[17], LAB[18], LAB[19], LAB[20], LAB[21], LAB[85], LAB[88]],
          num_rows, [6, 60, 22, 30, 30, 12, 16, 10, 30])
    sheet(wb.create_sheet(LAB[77]), [LAB[6], LAB[8], LAB[17], LAB[80], LAB[81], LAB[79]], fmt_rows, [6, 60, 16, 50, 50, 70])
    hol = []
    for y in (TSY, TSY + 1):
        hd = dc.load_holidays(y, holiday_dir) or {"holidays": []}
        for h in sorted(hd["holidays"], key=lambda x: x["date"]):
            why = "; ".join(x for x in (h.get("note"), h.get("source_url")) if x)
            hol.append([h["date"], dc.WD[dt.date.fromisoformat(h["date"]).weekday()], h["name"],
                        LAB[45] if h.get("verified") else LAB[46], why])
    sheet(wb.create_sheet(LAB[5]), [LAB[26], LAB[27], LAB[28], LAB[106], LAB[29]], hol, [12, 6, 24, 10, 90])
    for wsx in wb.worksheets[1:]:
        for row in wsx.iter_rows(min_row=2):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
    if os.path.exists(L(dst)):
        raise RuntimeError("검토표가 이미 있음 - 덮어쓰지 않음: " + dst)
    os.makedirs(L(os.path.dirname(dst)), exist_ok=True)
    wb.save(L(dst))
    return {"파일별": len(files_rows), "날짜바꿈": len(date_rows), "확인할곳": len(flag_rows),
            "확인할곳분류": dict(fc.most_common())}
