# -*- coding: utf-8 -*-
"""윤문 3단계: 에이전트가 쓴 윤문.json을 검사한다(바꾸면 안 되는 것을 바꿨는지).

py -3 -E <스킬 폴더>/tools/gongmun.py proofread-guard <결과 폴더>

통과·막힘을 화면에 쓰고 <결과 폴더>/_작업기록/윤문/윤문_검사.json에 남긴다(같은 이름이 있으면 _2, _3 ...).
막힌 항목은 적용하지 않는다. 고쳐 쓴 뒤 다시 검사하면 된다. 검사 규칙은 proofread_lib.check_entry 설명.
돌려주는 값: 모두 통과 0, 막힌 항목이 있으면 1.
"""
import os, sys, argparse
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proofread_lib as pl


def reason_text(T, rs):
    return " / ".join(T[k].replace("{W}", w) if w else T[k].replace(": {W}", "").replace("{W}", "") for k, w in rs)


def next_free(p):
    if not os.path.exists(pl.L(p)):
        return p
    stem, ext = os.path.splitext(p)
    k = 2
    while os.path.exists(pl.L(f"{stem}_{k}{ext}")):
        k += 1
    return f"{stem}_{k}{ext}"


def run_check(run, T):
    data = pl.jload(run.entries)
    ok, bad = pl.check_all(run, data.get("항목", []))
    return data, ok, bad


def main(argv=None):
    ap = argparse.ArgumentParser(description="윤문.json 검사")
    ap.add_argument("result_dir", help="변환 결과 폴더(<입력>_올해버전)")
    a = ap.parse_args(argv)
    T = pl.labels()
    run = pl.Run(a.result_dir)
    data, ok, bad = run_check(run, T)
    rep = {"작업ID": run.id, "검사일": pl.today(), "통과": [e["id"] for e in ok],
           "막힘": [{"id": e.get("id"), "file": e.get("file"), "location": e.get("location"), "category": e.get("category"),
                    "kind": e.get("kind"), "이유": reason_text(T, rs)} for e, rs in bad]}
    pl.jdump(rep, next_free(run.check_json))
    if pl.KIWI_MISSING:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "배포문구.json"), encoding="utf-8") as f:
            import json
            print(json.load(f)["d.kiwi_missing"])
    print(T["g.summary"].replace("{P}", str(len(ok))).replace("{R}", str(len(bad))))
    for b in rep["막힘"]:
        print(f"  - {b['id']} ({b['kind']}·{b['category']}): {b['이유']}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
