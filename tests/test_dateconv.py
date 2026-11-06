# -*- coding: utf-8 -*-
"""날짜 엔진 시험(v3 시험 34개를 옮김). 공휴일은 tests/fixtures/holidays의 고정 사본을 쓴다.
사용: py -3 -m unittest discover -s tests"""
import sys, os, json, shutil, tempfile, unittest, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bsv-gongmun-year-update", "tools"))
FIX = os.path.join(HERE, "fixtures", "holidays")
import dateconv as dc

D = dt.date


def _w(tmp, y, hs):
    with open(os.path.join(tmp, f"{y}.json"), "w", encoding="utf-8") as f:
        json.dump({"연도": y, "holidays": hs}, f)


def setup_2026():
    dc.configure(2026, holiday_dir=FIX, allow_unverified=True)


class TargetYear(unittest.TestCase):
    def test_run_date_spring(self):
        self.assertEqual(dc.resolve_target_sy(D(2027, 4, 10)), 2027)

    def test_run_date_january(self):
        self.assertEqual(dc.resolve_target_sy(D(2027, 1, 15)), 2026)

    def test_run_date_boundaries(self):
        self.assertEqual(dc.resolve_target_sy(D(2027, 2, 28)), 2026)
        self.assertEqual(dc.resolve_target_sy(D(2027, 3, 1)), 2027)

    def test_override(self):
        self.assertEqual(dc.resolve_target_sy(D(2026, 11, 4), override=2027), 2027)
        self.assertEqual(dc.resolve_target_sy(D(2026, 11, 4), override="2027"), 2027)

    def test_override_changes_mapping(self):
        tmp = tempfile.mkdtemp()
        try:
            for y in (2027, 2028):
                _w(tmp, y, [{"date": f"{y}-01-01", "name": "신정", "verified": True}])
            dc.configure(2027, holiday_dir=tmp)
            self.assertEqual(dc.shift_date(D(2025, 5, 14))[0].year, 2027)
            self.assertEqual(dc.shift_date(D(2026, 1, 14))[0].year, 2028)
            out = dc.convert("1. 관련: 가나중학교-100(2026. 4. 2.)", base_sy=2026)[0]
            self.assertEqual(out, "1. 관련: 가나중학교-OOOO(2027. OO. OO.)")
        finally:
            shutil.rmtree(tmp)
            setup_2026()


class HolidayData(unittest.TestCase):
    def test_missing_file_stops(self):
        tmp = tempfile.mkdtemp()
        try:
            _w(tmp, 2030, [])
            with self.assertRaises(dc.HolidayDataError) as cm:
                dc.configure(2030, holiday_dir=tmp)
            self.assertIn("2031년", str(cm.exception))
            self.assertIn("공휴일 목록", str(cm.exception))
        finally:
            shutil.rmtree(tmp)
            setup_2026()

    def test_unverified_stops_without_permission(self):
        with self.assertRaises(dc.HolidayDataError) as cm:
            dc.configure(2026, holiday_dir=FIX)
        self.assertIn("2026-05-01", str(cm.exception))
        self.assertIn("--allow-unverified-holidays", str(cm.exception))
        setup_2026()

    def test_unverified_allowed_with_warning(self):
        w = dc.configure(2026, holiday_dir=FIX, allow_unverified=True)
        self.assertTrue(any("2027년" in x for x in w))
        self.assertTrue(any("2026-07-17" in x for x in w))

    def test_no_year_literal_needed(self):
        # 2026이 아닌 대상 학년도에서도 같은 코드로 동작
        tmp = tempfile.mkdtemp()
        try:
            for y in (2030, 2031):
                _w(tmp, y, [])
            dc.configure(2030, holiday_dir=tmp)
            self.assertEqual(dc.convert("2029학년도 2029. 4. 3.(화)", base_sy=2029)[0], "2030학년도 2030. 4. 2.(화)")
        finally:
            shutil.rmtree(tmp)
            setup_2026()


class Mapping(unittest.TestCase):
    def setUp(self):
        setup_2026()

    def conv(self, s, **k):
        return dc.convert(s, **k)[0]

    def test_2024_may_to_2026(self):
        # 2024-05-14 둘째 화 → 2026-05-12 둘째 화
        self.assertEqual(dc.shift_date(D(2024, 5, 14))[0], D(2026, 5, 12))
        self.assertEqual(self.conv("2024. 5. 14.(화)", base_sy=2024), "2026. 5. 12.(화)")

    def test_2025_january_to_2027(self):
        # 2025-01-14 둘째 화 → 2027-01-12 둘째 화
        self.assertEqual(dc.shift_date(D(2025, 1, 14))[0], D(2027, 1, 12))

    def test_2023_doc(self):
        out, ch, fl, _ = dc.convert("2023학년도 2023. 10. 17.(화) 개최", base_sy=2023)
        self.assertEqual(out, "2026학년도 2026. 10. 20.(화) 개최")

    def test_mixed_years_in_one_doc(self):
        # 2025학년도 문서 안의 2024학년도 날짜도 올해로 옮기되 표시한다
        out, ch, fl, _ = dc.convert("2024. 10. 31.(목) 결과, 2025. 10. 30.(목) 예정", base_sy=2025)
        self.assertEqual(out, "2026. 10. 29.(목) 결과, 2026. 10. 29.(목) 예정")
        self.assertTrue(any(f["분류"] == "다른 학년도 날짜" for f in fl))

    def test_related_always_target(self):
        self.assertEqual(self.conv("1. 관련: 가나중학교-7506(2024.12.5.)"), "1. 관련: 가나중학교-OOOO(2026. OO. OO.)")
        self.assertEqual(self.conv("관련: 가나중학교-100(2026. 1. 5.)"), "관련: 가나중학교-OOOO(2026. OO. OO.)")
        self.assertEqual(self.conv("1. 관련: 가나중학교-12(2023. 3. 2.)", base_sy=2023), "1. 관련: 가나중학교-OOOO(2026. OO. OO.)")
        self.assertEqual(self.conv("가. 가나중학교-17495(2024.12.29.) 2025학년도 계획"),
                         "가. 가나중학교-OOOO(2026. OO. OO.) 2026학년도 계획")
        self.assertEqual(self.conv("1. 관련: 2025학년도 제2차 추경"), "1. 관련: 2026학년도 제2차 추경")

    def test_period_feb_to_mar(self):
        out, ch, fl, _ = dc.convert("2026. 2. 23.(월) ~ 2026. 3. 6.(금)")
        self.assertEqual(out, "2027. 2. 22.(월) ~ 2027. 3. 5.(금)")
        self.assertTrue(any(f["분류"] == "학년도 넘는 기간" for f in fl))

    def test_period_fixed_end(self):
        # 끝날 2/28(학년도 끝)은 길이를 유지하지 않고 월·일 유지 → 3월로 넘어가지 않음
        out, ch, fl, _ = dc.convert("2025년 1월 9일(목) ~ 2025년 2월 28일(금)", base_sy=2024)
        self.assertEqual(out, "2027년 1월 14일(목) ~ 2027년 2월 28일(일)")
        self.assertTrue(any(f["분류"] == "기간 길이 바뀜" for f in fl))

    def test_period_calendar_year(self):
        # 1. 1. ~ 12. 31.처럼 학년도에 걸친 기간은 대상 학년도와 가장 많이 겹치는 해로
        out, ch, fl, _ = dc.convert("2025. 1. 1. ~ 2025. 12. 31.")
        self.assertEqual(out, "2026. 1. 1. ~ 2026. 12. 31.")
        self.assertTrue(any(f["분류"] == "학년도 넘는 기간" for f in fl))

    def test_period_dec_to_jan(self):
        out, ch, fl, _ = dc.convert("2025. 12. 22.(월) ~ 2026. 1. 2.(금)")
        new = [c["새날짜"] for c in ch]
        self.assertTrue(new[0] < new[1])
        self.assertEqual((D.fromisoformat(new[1]) - D.fromisoformat(new[0])).days, 11)

    def test_order_reversal_flag(self):
        out, ch, fl, _ = dc.convert("1차 2024. 12. 2.(월), 2차 2025. 3. 4.(화)", base_sy=2024)
        self.assertTrue(any(f["분류"] == "날짜 순서 바뀜" for f in fl))

    def test_multi_year_period_flag(self):
        out, ch, fl, _ = dc.convert("기간: 2025. 3. 1. ~ 2028. 2. 29.")
        self.assertIn("2028. 2. 29.", out)
        self.assertTrue(any(f["분류"] == "여러 해 기간" for f in fl))

    def test_year_only(self):
        self.assertEqual(self.conv("2025학년도 제1회"), "2026학년도 제1회")
        self.assertEqual(self.conv("2024학년도 제1회", base_sy=2024), "2026학년도 제1회")
        self.assertEqual(self.conv("2025년 계획"), "2026년 계획")
        self.assertEqual(self.conv("'25학년도"), "'26학년도")

    def test_year_month(self):
        self.assertEqual(self.conv("2025년 10월 중"), "2026년 10월 중")
        self.assertEqual(self.conv("2024년 10월 중", base_sy=2024), "2026년 10월 중")
        self.assertEqual(self.conv("2026년 2월 중"), "2027년 2월 중")
        self.assertEqual(self.conv("2025. 10. 중"), "2026. 10. 중")

    def test_law_kept(self):
        out, ch, fl, _ = dc.convert("법률 제12345호(2024. 3. 1.)에 따라 2025. 4. 4.(금) 개최")
        self.assertIn("법률 제12345호(2024. 3. 1.)", out)
        self.assertIn("2026. 4. 3.(금)", out)
        self.assertEqual(self.conv("(2025.12.19.신설.)"), "(2025.12.19.신설.)")
        self.assertEqual(self.conv("시행 가나중학교-5444"), "시행 가나중학교-5444")

    # ---- v2에서 옮긴 시험(같은 규칙)
    def test_nth_weekday(self):
        self.assertEqual(dc.shift_date(D(2025, 4, 4))[0], D(2026, 4, 3))
        self.assertEqual(dc.shift_date(D(2025, 3, 14))[0], D(2026, 3, 13))

    def test_fifth_week_last(self):
        self.assertEqual(dc.shift_date(D(2025, 5, 30))[0], D(2026, 5, 29))
        n, info = dc.shift_date(D(2025, 12, 29))
        self.assertEqual(n, D(2026, 12, 28)); self.assertTrue(info["마지막주로"])

    def test_holiday_move(self):
        n, info = dc.shift_date(D(2025, 6, 4))
        self.assertEqual(n, D(2026, 6, 2)); self.assertIn("이동", info)
        self.assertEqual(dc.shift_date(D(2025, 8, 18))[0], D(2026, 8, 18))
        self.assertEqual(dc.shift_date(D(2025, 5, 2))[0], D(2026, 5, 4))
        self.assertEqual(dc.shift_date(D(2026, 1, 2))[0], D(2027, 1, 4))

    def test_fixed_dates(self):
        self.assertEqual(self.conv("2026.02.28.(토)까지"), "2027.02.28.(일)까지")
        self.assertEqual(self.conv("2024. 3. 1.(금)", base_sy=2024), "2026. 3. 1.(일)")
        out, ch, fl, _ = dc.convert("3월 1일부터")
        self.assertEqual(out, "3월 1일부터")

    def test_weekend_src(self):
        out, ch, fl, _ = dc.convert("잔액 반납: 2025.12.13.(금)까지")
        self.assertIn("2026.12.11.(금)", out)
        self.assertTrue(any(f["분류"] == "원문 요일 오류" for f in fl))

    def test_formats(self):
        self.assertEqual(self.conv("2025년 4월 4일 금요일 (13:10 ~ 13:30)"), "2026년 4월 3일 금요일 (13:10 ~ 13:30)")
        self.assertEqual(self.conv("2025-04-04"), "2026-04-03")
        self.assertEqual(self.conv("(25.10.15.)"), "(26.10.21.)")
        self.assertEqual(self.conv("(24.10.16.)", base_sy=2024), "(26.10.21.)")

    def test_ranges(self):
        self.assertEqual(self.conv("2025. 10. 30.(목) ~ 31.(금)"), "2026. 10. 29.(목) ~ 30.(금)")
        self.assertEqual(self.conv("2025.10.30.(목)~10.31.(금)"), "2026.10.29.(목)~10.30.(금)")
        self.assertEqual(self.conv("2025. 7. 23.(수) ~ 7. 25.(금)"), "2026. 7. 22.(수) ~ 7. 24.(금)")

    def test_noyear(self):
        self.assertEqual(self.conv("10.31.(금)까지 제출"), "10.30.(금)까지 제출")
        self.assertEqual(self.conv("1. 9.(금) 방학식"), "1. 8.(금) 방학식")
        self.assertEqual(self.conv("제출 기한: 10. 31. 까지"), "제출 기한: 10. 30. 까지")
        self.assertEqual(self.conv("1. 2. 3. 목차"), "1. 2. 3. 목차")

    def test_no_false(self):
        self.assertEqual(self.conv("13:10 ~ 13:30"), "13:10 ~ 13:30")
        self.assertEqual(self.conv("1,392,000 원"), "1,392,000 원")
        self.assertEqual(self.conv("가나중학교-2025 문서"), "가나중학교-2025 문서")

    def test_numeric(self):
        self.assertEqual(self.conv("작성일: 20251015"), "작성일: 20261021")
        self.assertEqual(self.conv("작성일: 20241016", base_sy=2024), "작성일: 20261021")
        self.assertEqual(self.conv("번호 20251015 확인"), "번호 20251015 확인")
        self.assertEqual(dc.convert("20251015", date_context=True)[0], "20261021")

    def test_check(self):
        self.assertEqual(dc.check_weekdays("2026. 4. 3.(금)"), [])
        self.assertEqual(dc.check_weekdays("2026. 4. 4.(금)"), ["2026. 4. 4.(금)"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
