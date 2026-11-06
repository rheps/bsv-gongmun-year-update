# -*- coding: utf-8 -*-
"""이 컴퓨터에 있는 프로그램 찾기: 한글(COM), LibreOffice(soffice.exe), 한컴 OCR 글자 자료(tessdata).

한글은 hwp → hwpx, 글자 PDF → hwpx, hwpx 쪽 그림에 꼭 필요하다(없으면 convert.py가 멈춘다).
LibreOffice는 없어도 된다(xls는 그대로 복사하고, odt·docx·xlsx는 열기 확인과 쪽 그림을 건너뛴다).
Hwp.exe --version 같은 명령은 쓰지 않는다. 레지스트리와 파일 위치만 본다.
"""
import os, glob, shutil

_SOFFICE = None


def hwp_available():
    """한글 COM(HWPFrame.HwpObject)이 등록되어 있는지."""
    if os.environ.get("BSV_GONGMUN_NO_HWP"):
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"HWPFrame.HwpObject\CLSID"):
            return True
    except Exception:
        return False


def soffice():
    """soffice.exe 경로(없으면 None). BSV_SOFFICE 환경 변수로 지정할 수 있다."""
    global _SOFFICE
    if _SOFFICE is not None:
        return _SOFFICE or None
    if os.environ.get("BSV_GONGMUN_NO_LIBREOFFICE"):
        _SOFFICE = ""
        return None
    cands = [os.environ.get("BSV_SOFFICE", "")]
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
        cands.append(os.path.join(base, "LibreOffice", "program", "soffice.exe"))
        cands += sorted(glob.glob(os.path.join(base, "LibreOffice*", "program", "soffice.exe")))
    w = shutil.which("soffice")
    if w:
        cands.append(w)
    for c in cands:
        if c and os.path.isfile(c):
            _SOFFICE = c
            return c
    _SOFFICE = ""
    return None


def tessdata():
    """한컴 오피스에 들어 있는 OCR 글자 자료 폴더(없으면 None)."""
    pats = []
    for base in (os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), os.environ.get("ProgramFiles", r"C:\Program Files")):
        pats.append(os.path.join(base, "HNC", "*", "HOffice*", "Bin", "HncOcr", "tessdata"))
        pats.append(os.path.join(base, "Hnc", "*", "HOffice*", "Bin", "HncOcr", "tessdata"))
    for p in pats:
        for d in sorted(glob.glob(p), reverse=True):
            if os.path.isdir(d):
                return d
    env = os.environ.get("TESSDATA_PREFIX")
    if env and os.path.isdir(env):
        return env
    return None
