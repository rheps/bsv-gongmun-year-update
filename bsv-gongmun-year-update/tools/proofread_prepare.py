# -*- coding: utf-8 -*-
"""윤문 1단계: 변환한 파일에서 읽을 글을 뽑는다(convert.py 다음에 실행).

py -3 -E <스킬 폴더>/tools/gongmun.py proofread-prepare <결과 폴더>

쓰는 파일(<결과 폴더>/_작업기록/윤문/ 안, 덮어쓰지 않음):
- 본문목록.json: 파일마다 {기록id, 파일, 형식, 문단:[{location, 위치, text}]}와 건너뛴 파일과 그 이유
- 본문목록.txt : 에이전트가 읽을 글. 「[location] 글」 한 줄씩
학생 자료, 중복, 변환 안 한 파일, 원본 유지(서식 PDF), OCR 글, 표 계산 파일은 뽑지 않는다(학생 자료는 이름도 적지 않음).
"""
import os, sys, argparse
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proofread_lib as pl


def main(argv=None):
    ap = argparse.ArgumentParser(description="윤문할 글 뽑기")
    ap.add_argument("result_dir", help="변환 결과 폴더(<입력>_올해버전)")
    a = ap.parse_args(argv)
    T = pl.labels()
    run = pl.Run(a.result_dir)
    files, skipped, lines = [], [], []
    nstudent = 0
    for r in run.records():
        why = pl.skip_reason(r)
        if why == "s.student":
            nstudent += 1
            continue
        if why:
            skipped.append({"기록id": r["기록id"], "파일": r["zip"] + "/" + r["rel"], "이유": T[why]})
            continue
        src = pl.proof_target(r)
        paras = [{"location": loc, "위치": w, "text": t}
                 for loc, (w, t) in pl.paragraphs_of(src).items() if pl.HANGUL.search(t) and not t.strip().startswith(("[제목]", "[본문]", "[붙임 목록]"))]
        rel = os.path.relpath(src, run.hub).replace("\\", "/")
        files.append({"기록id": r["기록id"], "파일": rel, "형식": pl.file_mode(src), "문단": paras})
        lines.append(f"===== {r['기록id']} | {rel}")
        lines += [f"[{p['location']}] {p['text']}" for p in paras]
        lines.append("")
    out = {"작업ID": run.id, "만든날": pl.today(), "파일": files, "건너뜀": skipped, "학생자료건너뜀": nstudent}
    pl.jdump(out, run.list_json)
    os.makedirs(pl.L(run.dir), exist_ok=True)
    if os.path.exists(pl.L(run.list_txt)):
        raise SystemExit("이미 있음 - 덮어쓰지 않음: " + run.list_txt)
    with open(pl.L(run.list_txt), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(T["p.done"].replace("{N}", str(len(files))).replace("{M}", str(sum(len(f["문단"]) for f in files)))
          .replace("{S}", str(len(skipped) + nstudent)))
    for s in skipped:
        print("  -", s["기록id"], s["이유"])
    if nstudent:
        print("  -", T["p.student"].replace("{N}", str(nstudent)))
    print(T["p.list"].replace("{PATH}", run.list_txt))


if __name__ == "__main__":
    sys.exit(main())
