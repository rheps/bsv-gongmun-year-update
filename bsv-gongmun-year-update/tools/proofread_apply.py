# -*- coding: utf-8 -*-
"""윤문 4단계: 검사를 통과한 항목을 모두 변환본에 넣은 새 판을 만든다.

py -3 -E <스킬 폴더>/tools/gongmun.py proofread-apply <결과 폴더>                     # 통과한 항목을 모두 넣은 판
py -3 -E <스킬 폴더>/tools/gongmun.py proofread-apply <결과 폴더> --revert Y004,Y010   # 그 항목만 뺀 다음 판
py -3 -E <스킬 폴더>/tools/gongmun.py proofread-apply <결과 폴더> --restore Y004       # 되돌린 항목을 다시 넣은 다음 판

- 설계 결정: 문장 다듬기(비문·어색한표현)도 검사를 통과하면 확정처럼 바로 적용한다. 승인을 기다리지 않는다.
- 판 N은 언제나 '윤문 전 변환본 + 통과한 항목 - 되돌린 항목'으로 새로 만든다(앞 판에 덧대지 않음).
  되돌린 항목은 판을 거듭해도 이어진다(--restore로 다시 넣을 수 있음). 검사에서 막힌 항목은 어느 판에도 넣지 않는다.
- 새 파일은 변환본 옆에 <이름>_윤문<N><확장자>로 쓴다. 원본·변환본·앞 판은 그대로 둔다. 같은 이름이 있으면 멈춘다.
- 검토표는 검토표.xlsx를 그대로 두고, 「윤문」 시트를 더한 검토표_윤문<N>.xlsx를 새로 만든다(상태: 적용 / 막힘 / 되돌림).
- 기록: <결과 폴더>/_작업기록/윤문/적용기록.json(판마다 넣은 항목·되돌린 항목·파일).
"""
import os, sys, json, shutil, argparse, collections
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proofread_lib as pl
from proofread_guard import reason_text


def write_new(path, data):
    if os.path.exists(pl.L(path)):
        raise SystemExit("이미 있는 파일 - 덮어쓰지 않음: " + path)
    os.makedirs(pl.L(os.path.dirname(path)), exist_ok=True)
    with open(pl.L(path), "wb") as f:
        f.write(data)


def ids_of(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def build_sheet(run, T, n, entries, bad, applied, reverted, new_files, recs):
    from openpyxl import load_workbook, Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    src = os.path.join(run.out, "검토표.xlsx")
    wb = load_workbook(pl.L(src)) if os.path.exists(pl.L(src)) else Workbook()
    name = T["h.sheet"]
    if name in wb.sheetnames:
        del wb[name]
    ws = wb.create_sheet(name)
    heads = [T[k] for k in ("h.id", "h.file", "h.loc", "h.before", "h.after", "h.cat", "h.reason", "h.state", "h.block", "h.out")]
    ws.append(heads)
    for c in ws[1]:
        c.font = Font(bold=True); c.fill = PatternFill("solid", fgColor="DDEBF7")
    badmap = {id(e): rs for e, rs in bad}
    plist = pl.jload(run.list_json)
    where = {(f["기록id"], p["location"]): p["위치"] for f in plist["파일"] for p in f["문단"]}
    for e in entries:
        r = recs.get(e.get("file"), {})
        fn = (r.get("zip", "") + "/" + r.get("rel", "")) if r else e.get("file", "")
        if id(e) in badmap:
            st, why = T["st.blocked"], reason_text(T, badmap[id(e)])
        elif e["id"] in applied:
            st, why = T["st.applied"], ""
        else:
            st, why = T["st.reverted"], ""
        out = new_files.get(e.get("file"), "") if e.get("id") in applied else ""
        ws.append([e.get("id"), fn, where.get((e.get("file"), e.get("location")), e.get("location")), e.get("before"), e.get("after"),
                   e.get("category"), e.get("reason"), st, why,
                   os.path.relpath(out, run.out).replace("\\", "/") if out else ""])
    for i, w in enumerate([7, 50, 18, 45, 45, 11, 40, 10, 40, 50], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    dst = os.path.join(run.out, f"검토표_윤문{n}.xlsx")
    if os.path.exists(pl.L(dst)):
        raise SystemExit("이미 있음 - 덮어쓰지 않음: " + dst)
    wb.save(pl.L(dst))
    return dst


def main(argv=None):
    T = pl.labels()
    ap = argparse.ArgumentParser(description="윤문 적용(새 판 만들기)")
    ap.add_argument("result_dir", help="변환 결과 폴더(<입력>_올해버전)")
    ap.add_argument("--revert", help=T["h.revert_opt"])
    ap.add_argument("--restore", help=T["h.restore_opt"])
    a = ap.parse_args(argv)
    run = pl.Run(a.result_dir)
    data = pl.jload(run.entries)
    entries = data.get("항목", [])
    ok, bad = pl.check_all(run, entries)
    okmap = {e["id"]: e for e in ok}
    allids = {e.get("id") for e in entries}
    vers = pl.jload(run.versions) if os.path.exists(pl.L(run.versions)) else {"작업ID": run.id, "판": []}
    reverted = set(vers["판"][-1].get("되돌린항목", [])) if vers["판"] else set()
    for x in ids_of(a.revert):
        if x not in allids:
            raise SystemExit(T["a.unknown_id"].replace("{ID}", x))
        if x not in okmap:
            raise SystemExit(T["a.revert_blocked"].replace("{ID}", x))
        reverted.add(x)
    for x in ids_of(a.restore):
        if x not in reverted:
            raise SystemExit(T["a.restore_unknown"].replace("{ID}", x))
        reverted.discard(x)
    reverted &= set(okmap)
    applied = [e for e in ok if e["id"] not in reverted]
    ids = sorted(e["id"] for e in applied)
    if not applied or (vers["판"] and sorted(vers["판"][-1]["넣은항목"]) == ids):
        print(T["a.none"])
        return 0
    n = len(vers["판"]) + 1
    plist = pl.jload(run.list_json)
    src_of = {f["기록id"]: os.path.normpath(os.path.join(run.hub, f["파일"])) for f in plist["파일"]}
    by_file = collections.defaultdict(lambda: collections.defaultdict(list))
    for e in applied:
        by_file[e["file"]][e["location"]].append((e["before"], e["after"]))
    new_files = {}
    for fid, ch in by_file.items():
        src = src_of[fid]
        dst = pl.version_path(src, n)
        write_new(dst, pl.apply_to_file(src, ch))
        new_files[fid] = dst
    recs = {r["기록id"]: r for r in run.records()}
    sheet = build_sheet(run, T, n, entries, bad, set(ids), reverted, new_files, recs)
    rel = lambda p: os.path.relpath(p, run.hub).replace("\\", "/")
    nsent = len([e for e in applied if pl.colour_of(e) == "blue"])
    vers["판"].append({"판": n, "날짜": pl.today(), "적용방식": "검사 통과 항목 모두 적용(설계 결정)",
                      "넣은항목": ids, "되돌린항목": sorted(reverted),
                      "파일": {k: rel(v) for k, v in new_files.items()}, "변환본": {k: rel(src_of[k]) for k in new_files},
                      "검토표": rel(sheet), "막힌항목": [e.get("id") for e, _ in bad]})
    pl.jdump(vers, run.versions, overwrite=True)
    print(T["a.done"].replace("{N}", str(n)).replace("{F}", str(len(new_files))).replace("{A}", str(len(applied)))
          .replace("{S}", str(nsent)).replace("{V}", str(len(reverted))).replace("{R}", str(len(bad))))
    for fid, p in new_files.items():
        print("  -", p)
    print(T["a.review"].replace("{PATH}", sheet))
    return 0


if __name__ == "__main__":
    sys.exit(main())
