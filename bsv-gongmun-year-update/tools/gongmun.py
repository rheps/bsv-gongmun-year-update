# -*- coding: utf-8 -*-
"""bsv-gongmun-year-update 도구 하나로 부르기.

  py -3 -E gongmun.py convert --input <zip·폴더·파일 ...> [--target-school-year N] ...
  py -3 -E gongmun.py proofread-prepare <결과 폴더>
  py -3 -E gongmun.py proofread-guard   <결과 폴더>
  py -3 -E gongmun.py proofread-apply   <결과 폴더> [--revert Y004,Y010] [--restore Y004]
  py -3 -E gongmun.py capture           <결과 폴더> [--판 N] [--no-render] [--붙임 _v2]
  py -3 -E gongmun.py check             (한글·LibreOffice·kiwipiepy가 있는지 확인)

각 명령은 --help로 옵션을 보여 준다. 문서 내용을 이 컴퓨터 밖으로 보내지 않는다.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("PYMUPDF_SUGGEST_LAYOUT_ANALYZER", "0")   # PyMuPDF 안내 문구를 끔
if HERE not in sys.path:
    sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

COMMANDS = {"convert": "convert", "proofread-prepare": "proofread_prepare", "proofread-guard": "proofread_guard",
            "proofread-apply": "proofread_apply", "capture": "capture_compare"}


def check():
    import office, importlib
    out = {"python": sys.version.split()[0], "hwp": office.hwp_available(), "libreoffice": office.soffice(),
           "ocr_tessdata": office.tessdata()}
    for m in ("openpyxl", "pymupdf", "lxml", "PIL", "olefile", "win32com", "kiwipiepy"):
        try:
            importlib.import_module(m)
            out[m] = True
        except Exception as ex:
            out[m] = "없음: " + type(ex).__name__
    for k, v in out.items():
        print(f"{k}: {v}")
    return 0 if out["hwp"] and all(out[m] is True for m in ("openpyxl", "pymupdf", "lxml", "PIL", "olefile", "win32com")) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "check":
        return check()
    if cmd not in COMMANDS:
        print(__doc__)
        return 2
    mod = __import__(COMMANDS[cmd])
    return mod.main(rest)


if __name__ == "__main__":
    sys.exit(main())
