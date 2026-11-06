# -*- coding: utf-8 -*-
"""표시 규칙·공문 서식 시험(합성 글). 사용: py -3 -m unittest discover -s tests"""
import os, sys, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bsv-gongmun-year-update", "tools"))
import dateconv as dc
import gongmun_format as gf


class FlagTerms(unittest.TestCase):
    def tearDown(self):
        dc.add_flag_terms({})

    def test_generic_school_name_flagged(self):
        dc.add_flag_terms({})
        cats = [f["분류"] for f in dc.find_flags("가나중학교 운영위원회")]
        self.assertIn("이전 학교 정보", cats)

    def test_extra_terms_and_regex(self):
        dc.add_flag_terms({"이전 학교 정보": ["다라"], "표어": ["re:함께 [가-힣]+ 교육"]})
        fl = dc.find_flags("다라 지역 함께 크는 교육")
        self.assertTrue(any(f["분류"] == "이전 학교 정보" and "다라" in f["설명"] for f in fl))
        self.assertTrue(any(f["분류"] == "표어" for f in fl))

    def test_overlapping_rules_flag_once(self):
        # 일반 학교 이름 규칙과 표시 규칙 파일의 학교 낱말이 같은 곳을 잡아도 한 번만 올린다(v3 대조에서 찾은 중복)
        dc.add_flag_terms({"이전 학교 정보": ["re:가나중(?:학교)?"]})
        fl = [f for f in dc.find_flags("가나중학교 운영위원회") if f["분류"] == "이전 학교 정보"]
        self.assertEqual(len(fl), 1)

    def test_separate_occurrences_kept(self):
        dc.add_flag_terms({})
        fl = [f for f in dc.find_flags("가나중학교와 다라중학교") if f["분류"] == "이전 학교 정보"]
        self.assertEqual(len(fl), 2)

    def test_reset(self):
        dc.add_flag_terms({"표어": ["다라마"]})
        dc.add_flag_terms({})
        self.assertFalse(any(f["분류"] == "표어" for f in dc.find_flags("다라마")))


class PasteFormat(unittest.TestCase):
    def test_relate_slot_and_renumber(self):
        log = []
        t, lines, items = gf.format_paste("계획", [("1. 계획을 알립니다.", "p"), ("2. 문의: 교무실", "p")], ["붙임 계획서 1부. 끝."], log)
        self.assertEqual(lines[0], "1. 관련: ")
        self.assertEqual(lines[1], "2. 계획을 알립니다.")
        self.assertEqual(lines[2], "3. 문의: 교무실")
        self.assertEqual(lines[-1], "붙임  계획서 1부.  끝.")

    def test_existing_relate_kept(self):
        log = []
        _, lines, _ = gf.format_paste("계획", [("1. 관련: 가나중학교-OOOO(2026. OO. OO.)", "p"), ("2. 다음과 같이 알립니다.", "p")], [], log)
        self.assertEqual(lines[0], "1. 관련: 가나중학교-OOOO(2026. OO. OO.)")
        self.assertTrue(lines[-1].endswith("  끝."))


if __name__ == "__main__":
    unittest.main(verbosity=1)
