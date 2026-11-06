# -*- coding: utf-8 -*-
"""한글 응답 없음 대비 시험(한글을 실제로 띄우지 않음). 2026-11-04 실제 실행에서 파일 접근 확인 창이
자동으로 닫히지 않아 열기 확인이 멈춘 일을 막는다."""
import os, sys, time, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bsv-gongmun-year-update", "tools"))
try:
    import hwpcom
except Exception:  # pywin32가 없으면 건너뜀
    hwpcom = None


class FakeCom:
    def __init__(self, owner, hang):
        self.owner, self.hang = owner, hang

    def Open(self, *a):
        if self.hang:
            t0 = time.time()
            while not self.owner.killed and time.time() - t0 < 5:
                time.sleep(0.02)
            raise Exception("RPC server unavailable")
        return True


@unittest.skipIf(hwpcom is None, "pywin32 없음")
class Guard(unittest.TestCase):
    def make(self, hang):
        h = object.__new__(hwpcom.Hwp)
        h.mine = set()  # 실제 프로세스는 끄지 않음
        h.hwp = FakeCom(h, hang)
        h.TIMEOUT = 0.2
        return h

    def test_hang_becomes_error_and_marks_killed(self):
        h = self.make(True)
        t0 = time.time()
        with self.assertRaises(RuntimeError):
            h.open("x.hwpx")
        self.assertTrue(h.killed)
        self.assertLess(time.time() - t0, 3)
        with self.assertRaises(RuntimeError):  # 끈 뒤에는 다시 쓰지 않음
            h.open("y.hwpx")

    def test_normal_open_unchanged(self):
        h = self.make(False)
        self.assertTrue(h.open("x.hwpx"))
        time.sleep(0.3)
        self.assertFalse(h.killed)


class StageRetry(unittest.TestCase):
    """한글이 밖에서 꺼져 COM 호출이 실패하면 새 한글로 한 번 더 한다(2026-11-04 실제 실행에서 46개 오류)."""

    def test_dead_server_restarts_once(self):
        import tempfile, types, pipeline
        made = []

        class FakeHwp:
            def __init__(self):
                self.n = len(made); made.append(self); self.killed = False

            def open(self, p, fmt=""):
                if self.n == 0:
                    raise Exception("RPC 서버를 사용할 수 없습니다.")
                return True

            def pages(self):
                return 1

            def save_as(self, p, fmt="HWPX"):
                open(p, "wb").write(b"ok"); return True

            def close_doc(self):
                pass

            def quit(self):
                pass

        saved = sys.modules.get("hwpcom")
        sys.modules["hwpcom"] = types.SimpleNamespace(Hwp=FakeHwp)
        d = tempfile.mkdtemp()
        try:
            pipeline.WORK = d
            src = os.path.join(d, "in.hwp"); open(src, "wb").write(b"x")
            data, pages = pipeline.HwpStage().to_hwpx(src, "k")
            self.assertEqual((data, pages, len(made)), (b"ok", 1, 2))
        finally:
            if saved is not None:
                sys.modules["hwpcom"] = saved
            else:
                sys.modules.pop("hwpcom", None)
            import shutil; shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
