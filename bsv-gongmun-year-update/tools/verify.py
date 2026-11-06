# -*- coding: utf-8 -*-
"""변환 결과 확인: 한글/LibreOffice에서 열기, 쪽수, 요일-날짜 일치, 남은 지난 연도 표기, 붙여넣기 글 서식.

convert.py가 run(results, tmp, use_office)로 부른다. 대상 학년도는 dateconv.configure로 이미 정해져 있어야 한다.
use_office=False면 한글·LibreOffice를 열지 않고 글(txt)만 확인한다.
"""
import os, re, json, shutil, subprocess, collections
import dateconv as dc

import office


def _T(k):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "배포문구.json"), encoding="utf-8") as f:
        return json.load(f)[k]


def L(p):
    p = os.path.abspath(p)
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


def _old_re():
    return re.compile(r"(?<!\d)(" + "|".join(str(y) for y in range(dc.SRC_LO, dc.TSY)) + r")(?!\d)")


def residual(text):
    """대상 학년도보다 앞선 연도(4자리 숫자)가 남은 곳: [{"연도", "글"}]"""
    return [{"연도": int(m.group(1)), "글": text[max(0, m.start() - 25): m.end() + 15].replace("\n", " ").replace("\r", " ")}
            for m in _old_re().finditer(text)]


def _txt(path):
    t = open(L(path), "rb").read()
    try:
        return t.decode("utf-8-sig")
    except Exception:
        return t.decode("cp949", "ignore")


def run(results, tmp, use_office=True):
    V = os.path.join(tmp, "v"); os.makedirs(V, exist_ok=True)
    prof = "file:///" + os.path.join(tmp, "lo_profile").replace("\\", "/")
    h = None
    lo_jobs, rows = [], []
    try:
        for i, r in enumerate(results):
            for k, f in enumerate(r.get("결과", [])):
                ext = os.path.splitext(f)[1].lower()
                v = {"파일": f, "원본": r["zip"] + "/" + r["rel"], "열림": None, "쪽수": None,
                     "요일불일치": [], "남은옛연도": [], "원본쪽수": r.get("원본쪽수")}
                if r.get("그대로복사"):
                    v["확인안함"] = "원본 그대로 복사"
                    rows.append(v); continue
                key = f"{i:04d}_{k}"
                if ext == ".txt" or ext in (".md", ".csv"):
                    s = _txt(f)
                    v["열림"] = True
                    v["요일불일치"] = dc.check_weekdays(s)
                    v["남은옛연도"] = residual(s)
                    if f.endswith("_업무관리시스템_붙여넣기.txt"):
                        v["서식확인"] = {"끝표시": s.count("  끝."), "붙임띄움": s.count("붙임  "), "관련칸": s.count("1. 관련: ")}
                elif not use_office:
                    v["확인안함"] = "한글·LibreOffice 확인을 건너뜀(--no-verify)"
                elif ext == ".hwpx":
                    tin = os.path.join(V, key + ".hwpx"); shutil.copyfile(L(f), tin)
                    for attempt in (1, 2):  # 한글이 도중에 꺼지면 새로 띄워 한 번 더 연다
                        try:
                            if h is None or (i % 60 == 0 and attempt == 1) or getattr(h, "killed", False):
                                if h:
                                    h.quit()
                                import hwpcom
                                h = hwpcom.Hwp()
                            ok = h.open(tin)
                            v["열림"] = bool(ok); v.pop("오류", None)
                            if ok:
                                v["쪽수"] = h.pages()
                                t = h.text() or ""
                                v["요일불일치"] = dc.check_weekdays(t)
                                v["남은옛연도"] = residual(t)
                                v["글자수"] = len(t)
                            h.close_doc()
                            break
                        except Exception as e:
                            v["열림"] = False; v["오류"] = str(e)
                            if h:
                                h.quit()
                            h = None
                elif ext in (".odt", ".docx", ".xlsx") and not office.soffice():
                    v["확인안함"] = _T("d.lo_missing_verify")
                elif ext in (".odt", ".docx", ".xlsx"):
                    tin = os.path.join(V, key + ext); shutil.copyfile(L(f), tin)
                    lo_jobs.append((tin, v))
                rows.append(v)
    finally:
        if h:
            h.quit()
    if lo_jobs:
        import pymupdf as fitz
        outdir = os.path.join(V, "lo"); os.makedirs(outdir, exist_ok=True)
        files = [j[0] for j in lo_jobs]
        for s in range(0, len(files), 25):
            try:
                subprocess.run([office.soffice(), f"-env:UserInstallation={prof}", "--headless", "--convert-to", "pdf",
                                "--outdir", outdir] + files[s:s + 25], capture_output=True, timeout=900)
            except Exception:
                pass
        for tin, v in lo_jobs:
            pdf = os.path.join(outdir, os.path.splitext(os.path.basename(tin))[0] + ".pdf")
            if os.path.exists(pdf):
                d = fitz.open(pdf)
                v["열림"] = True; v["쪽수"] = len(d)
                t = "".join(p.get_text() for p in d)
                d.close()
                v["요일불일치"] = dc.check_weekdays(t)
                v["남은옛연도"] = residual(t)
            else:
                v["열림"] = False
    return rows


def summary(rows):
    """기록에 둘 요약(문서 글은 넣지 않음)."""
    c = collections.Counter((os.path.splitext(v["파일"])[1].lower(), v["열림"]) for v in rows)
    return {
        "확인한파일": len(rows),
        "형식별열림": {f"{e} {o}": n for (e, o), n in sorted(c.items(), key=str)},
        "요일불일치파일": sum(1 for v in rows if v["요일불일치"]),
        "옛연도남은파일": sum(1 for v in rows if v["남은옛연도"]),
        "쪽수달라진파일": sum(1 for v in rows if v.get("원본쪽수") and v.get("쪽수") and v["원본쪽수"] != v["쪽수"]),
        "열리지않은파일": sum(1 for v in rows if v["열림"] is False),
    }
