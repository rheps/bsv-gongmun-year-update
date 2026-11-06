# -*- coding: utf-8 -*-
"""한글 2022 COM helper: hidden instance + security-dialog watcher.

The watcher only clicks buttons in dialogs owned by the Hwp process this
script started (allow / OK style buttons), and logs every dialog it sees.
"""
import os, sys, time, threading, ctypes, json
import pythoncom, win32com.client, win32gui, win32con, win32process, win32api

ALLOW_WORDS = ["모두 허용", "접근 허용", "허용", "예(&Y)", "예", "확인", "OK"]
LOG = []


def _dialog_texts(hwnd):
    out = []
    def cb(h, _):
        try:
            out.append((h, win32gui.GetClassName(h), win32gui.GetWindowText(h)))
        except Exception:
            pass
        return True
    try:
        win32gui.EnumChildWindows(hwnd, cb, None)
    except Exception:
        pass
    return out


def _wpf_allow(hwnd):
    """WPF 파일 접근 확인 창이면(hwp_allow.ps1로 확인) Alt+Y(「접근 허용」 한 번)를 보낸다."""
    import subprocess
    ps = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hwp_allow.ps1")
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps, "-Hwnd", str(int(hwnd))],
                           capture_output=True, timeout=30)
        out = p.stdout.decode("utf-8", "ignore").strip()
    except Exception as ex:
        return "error: " + repr(ex)
    if out != "access-dialog":
        return out or "unknown"
    lp = 1 | (0x15 << 16) | (1 << 29)
    win32api.PostMessage(hwnd, win32con.WM_SYSKEYDOWN, ord("Y"), lp)
    win32api.PostMessage(hwnd, win32con.WM_SYSCHAR, ord("y"), lp)
    win32api.PostMessage(hwnd, win32con.WM_SYSKEYUP, ord("Y"), lp | (3 << 30))
    return "alt+y"


class Watcher(threading.Thread):
    def __init__(self, pid_getter):
        super().__init__(daemon=True)
        self.pid_getter = pid_getter
        self.stop = False
        self.wpf_done = {}   # hwnd → 마지막으로 누른 시각

    def run(self):
        while not self.stop:
            pids = self.pid_getter()
            for h in list(self.wpf_done):   # 닫혔다가 다시 뜬 창은 다시 누를 수 있게
                try:
                    if not win32gui.IsWindowVisible(h):
                        self.wpf_done.pop(h, None)
                except Exception:
                    self.wpf_done.pop(h, None)
            if pids:
                def cb(h, _):
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(h)
                        if pid in pids and win32gui.IsWindowVisible(h):
                            cls = win32gui.GetClassName(h)
                            title = win32gui.GetWindowText(h)
                            if cls.startswith("HwndWrapper[hwp.exe") and not title.endswith("한글") and time.time() - self.wpf_done.get(h, 0) > 4:
                                # 2026-11-05: 한글 업데이트 뒤 파일 접근 확인 창이 WPF 창으로 바뀌어 Button 자식이 없다.
                                # 작은 창만 골라 hwp_allow.ps1(UI Automation)로 「접근 허용」 하나만 누른다.
                                l, t, r, b = win32gui.GetWindowRect(h)
                                if 0 < r - l < 900 and 0 < b - t < 500:
                                    self.wpf_done[h] = time.time()
                                    rc = _wpf_allow(h)
                                    LOG.append({"t": time.time(), "title": title, "cls": cls, "wpf": rc})
                                return True
                            if cls == "#32770" or "보안" in title or "접근" in title:
                                kids = _dialog_texts(h)
                                texts = [t for _, c, t in kids if t]
                                LOG.append({"t": time.time(), "title": title, "cls": cls, "texts": texts[:20]})
                                for word in ALLOW_WORDS:
                                    for kh, kc, kt in kids:
                                        if kc == "Button" and kt.replace("&", "") == word.replace("&", ""):
                                            win32api.PostMessage(kh, win32con.BM_CLICK, 0, 0)
                                            LOG[-1]["clicked"] = kt
                                            return True
                    except Exception:
                        pass
                    return True
                try:
                    win32gui.EnumWindows(cb, None)
                except Exception:
                    pass
            time.sleep(0.3)


def hwp_pids():
    import subprocess
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Hwp.exe", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True, encoding="cp949", errors="ignore").stdout
    pids = set()
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) > 1 and parts[1].isdigit():
            pids.add(int(parts[1]))
    return pids


class Hwp:
    def __init__(self):
        pythoncom.CoInitialize()
        self.before = hwp_pids()
        self.hwp = win32com.client.DispatchEx("HWPFrame.HwpObject")
        time.sleep(1)
        self.mine = hwp_pids() - self.before
        self.w = Watcher(lambda: self.mine)
        self.w.start()
        try:
            self.hwp.XHwpWindows.Item(0).Visible = False
        except Exception:
            pass
        try:
            # 0x00020021-ish: auto answer message boxes with default/OK/Yes
            self.hwp.SetMessageBoxMode(0x00011111)
        except Exception:
            pass

    TIMEOUT = 120  # 한 파일 열기·저장 최대 초. 넘으면 이 도구가 띄운 한글만 끄고 오류로 남긴다

    killed = False

    def _kill(self):
        """시간 초과: 응답하지 않는 창(예: 자동으로 닫히지 않는 파일 접근 확인 창)에 묶인 한글을 끈다.
        이 객체가 띄운 Hwp.exe만 끈다."""
        self.killed = True
        for pid in set(getattr(self, "mine", set())) & hwp_pids():
            try:
                h = win32api.OpenProcess(win32con.PROCESS_TERMINATE, 0, pid)
                win32api.TerminateProcess(h, 0)
            except Exception:
                pass

    def _guard(self, fn, *args):
        if self.killed:
            raise RuntimeError("한글이 시간 초과로 종료됨")
        timer = threading.Timer(self.TIMEOUT, self._kill)
        timer.daemon = True
        timer.start()
        try:
            return fn(*args)
        except Exception:
            if self.killed:
                raise RuntimeError(f"한글이 {self.TIMEOUT}초 안에 답하지 않아 종료함")
            raise
        finally:
            timer.cancel()

    def open(self, path, fmt="", arg="forceopen:true;suspendpassword:true;versionwarning:false"):
        return self._guard(self.hwp.Open, os.path.abspath(path), fmt, arg)

    def save_as(self, path, fmt="HWPX", arg=""):
        return self._guard(self.hwp.SaveAs, os.path.abspath(path), fmt, arg)

    def pages(self):
        return self.hwp.PageCount

    def text(self):
        return self.hwp.GetTextFile("UNICODE", "")

    def close_doc(self):
        try:
            self.hwp.Clear(1)
        except Exception:
            pass

    def quit(self):
        try:
            self.hwp.Clear(1)
        except Exception:
            pass
        try:
            self.hwp.Quit()
        except Exception:
            pass
        self.w.stop = True
        time.sleep(1.5)
        for pid in self.mine & hwp_pids():
            try:
                h = win32api.OpenProcess(win32con.PROCESS_TERMINATE, 0, pid)
                win32api.TerminateProcess(h, 0)
            except Exception:
                pass
