# -*- coding: utf-8 -*-
"""본문 학생 식별 신호 시험. 합성 자료만 쓴다(가짜 이름·가짜 학번).
사용: py -3 -m unittest discover -s tests"""
import os, sys, io, json, glob, shutil, tempfile, unittest, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bsv-gongmun-year-update", "tools"))
FIX = os.path.join(HERE, "fixtures", "holidays")
import warnings
warnings.simplefilter("ignore", ResourceWarning)
import convert


def hit(text, path="메모.txt"):
    return convert.student_signals(path, text)["학생정보"]


class Positives(unittest.TestCase):
    def test_two_ids_with_names_in_memo(self):
        self.assertTrue(hit("3. 추가 참여 2명 (20315 가나다, 20422 라마바) 포함하면 다시 품의"))

    def test_single_id_name_pair(self):
        self.assertTrue(hit("10101 가나다 학생 결석"))

    def test_id_name_adjacent(self):
        self.assertTrue(hit("30512가나다"))

    def test_name_before_id(self):
        self.assertTrue(hit("가나다(10203) 제출 완료"))

    def test_grade_class_number_name(self):
        self.assertTrue(hit("2학년 3반 15번 가나다 지각"))
        self.assertTrue(hit("3반 7번 라마바"))

    def test_header_with_ids(self):
        self.assertTrue(hit("학번\n이름\n10101\n10102\n10103"))
        self.assertTrue(hit("번호 이름 비고\n20101\n20102"))


class Negatives(unittest.TestCase):
    def test_dates(self):
        self.assertFalse(hit("2025. 10. 15.(수) 회의, 25.10.15. 기준, 2025-10-15 시행, 20251015 공고"))

    def test_amounts(self):
        self.assertFalse(hit("1인당 12,000원, 총 1,250,000원, 12000원 납부, 21050원 환불"))
        self.assertFalse(hit("합계 10120 원"))

    def test_phone_and_account(self):
        self.assertFalse(hit("문의 031-123-4567, 010-2015-1234, 계좌 123-20150-12"))

    def test_doc_number_and_postal(self):
        self.assertFalse(hit("제10101호 공문, 우편번호 10101 경기도, (우)21010 인천시"))

    def test_counts_with_units(self):
        self.assertFalse(hit("10101명 참가, 20240년도, 10150까지 접수"))

    def test_plain_gongmun(self):
        self.assertFalse(hit("1. 관련: 교육청 공문(2025. 3. 4.)\n2. 학생 안전교육을 실시하고자 합니다.\n3반 15번까지 배정"))

    def test_long_number_not_phone(self):
        self.assertFalse(hit("값 3401012345678901234 / 0.0101234567890 / 9010101234567"))

    def test_form_example_status_word(self):
        self.assertFalse(hit("예시\n<>10301 불참\n체험학습비 10302 지참"))

    def test_blank_form_header_only(self):
        self.assertFalse(hit("학번\t이름\t비고\n\t\t\n"))


class MemoGoesToTask(unittest.TestCase):
    """파일 이름에 낱말이 없어도 본문에 학번·이름이 있으면 바꾸지 않고 학생자료_변환안함에만 둔다."""

    def test_memo_kept_in_task(self):
        root = tempfile.mkdtemp(prefix="gongmun_memo_")
        try:
            src = os.path.join(root, "자료")
            os.makedirs(os.path.join(src, "품의"))
            open(os.path.join(src, "품의", "품의 시 주의점.txt"), "w", encoding="cp949").write(
                "2025. 10. 15. 이후 추가 2명 (20315 가나다, 20422 라마바) 포함 품의\n")
            open(os.path.join(src, "품의", "안내.txt"), "w", encoding="utf-8").write("2025. 10. 15.(수) 회의 안내\n")
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc = convert.main(["--input", src, "--holiday-dir", FIX, "--run-date", "2026-11-04",
                                   "--allow-unverified-holidays", "--no-verify", "--quiet"])
            self.assertEqual(rc, 0, out.getvalue())
            res = os.path.join(root, "자료_올해버전")
            hits = [x for x in glob.glob(os.path.join(res, "**", "*주의점*"), recursive=True) if "_작업기록" not in x]
            self.assertEqual(len(hits), 1)
            self.assertIn("학생자료_변환안함", hits[0])
            self.assertIn("2025. 10. 15.", open(hits[0], encoding="cp949").read())   # 바꾸지 않고 그대로 복사
            self.assertEqual(len([x for x in glob.glob(os.path.join(res, "**", "안내.txt"), recursive=True) if "_작업기록" not in x]), 1)
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
