# -*- coding: utf-8 -*-
"""윤문 검사(guard)·적용(apply) 시험. 합성 글만 쓴다(실제 문서·학교·개인 자료 없음).
가짜 결과 폴더를 임시 폴더에 만든다. 한글·LibreOffice는 열지 않는다.
사용: py -3 -m unittest discover -s tests"""
import os, sys, io, json, shutil, zipfile, tempfile, unittest, contextlib
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "bsv-gongmun-year-update", "tools")
sys.path.insert(0, TOOL)
warnings.simplefilter("ignore", ResourceWarning)
import proofread_lib as pl
import proofread_prepare, proofread_guard, proofread_apply
from openpyxl import load_workbook

HP = 'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
REC = "_작업기록"


def zbytes(members):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in members.items():
            z.writestr(n, d)
    return b.getvalue()


def hwpx(paras):
    """paras: 문단마다 run 글 목록(여러 run에 나뉜 글 시험)."""
    ps = "".join("<hp:p>" + "".join(f"<hp:run><hp:t>{t}</hp:t></hp:run>" for t in runs) + "</hp:p>" for runs in paras)
    sec = f'<?xml version="1.0" encoding="UTF-8"?><hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" {HP}>{ps}</hs:sec>'
    return zbytes({"mimetype": "application/hwp+zip", "Contents/section0.xml": sec})


def wbytes(p, b):
    with open(p, "wb") as f:
        f.write(b)


def rbytes(p):
    with open(p, "rb") as f:
        return f.read()


def rtext(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def wjson(obj, p):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def E(i, loc, b, a, kind="확정", cat="띄어쓰기", f="파일-01-0001"):
    return {"id": i, "file": f, "location": loc, "before": b, "after": a, "kind": kind, "category": cat, "reason": "시험"}


class GuardRules(unittest.TestCase):
    P = "2026. 3. 5.(목)까지 가나도교육청 「학교안전법」에 근거하여안전 교육을 실시하오니 협조 바랍니다."

    def bad(self, b, a, cat="띄어쓰기", kind="확정", para=None, protect=()):
        return [k for k, _ in pl.check_entry(E("Y1", "줄 1", b, a, kind, cat), self.P if para is None else para, list(protect))]

    def test_spacing_ok(self):
        self.assertEqual(self.bad("근거하여안전", "근거하여 안전"), [])

    def test_spacing_must_only_change_spaces(self):
        self.assertIn("g.spacing_only", self.bad("근거하여안전", "근거해 안전"))

    def test_digits_blocked(self):
        self.assertIn("g.digits", self.bad("2026. 3. 5.", "2026. 3. 6.", "공문서표기"))

    def test_notation_date_ok(self):
        p = "행사일: 2026.3.5. 끝."
        self.assertEqual(self.bad("2026.3.5.", "2026. 3. 5.", "공문서표기", para=p), [])
        p2 = "행사일은 2026년 3월 5일입니다."
        self.assertEqual(self.bad("2026년 3월 5일", "2026. 3. 5.", "공문서표기", para=p2), [])

    def test_notation_time_and_dot(self):
        p = "점심시간인 12시 40분까지 예방‧관리를 한다. 1시간 동안"
        self.assertEqual(self.bad("12시 40분", "12:40", "공문서표기", para=p), [])
        self.assertEqual(self.bad("예방‧", "예방·", "공문서표기", para=p), [])
        self.assertIn("g.notation_only", self.bad("1시간", "1:간", "공문서표기", para=p))

    def test_proposal_may_drop_repeated_word_only(self):
        p = "급식지도 계획을 붙임과 같이 계획하여 실시하고자 합니다."
        self.assertEqual(self.bad("급식지도 계획을 붙임과", "급식지도를 붙임과", "어색한표현", "제안", para=p), [])
        self.assertIn("g.nouns", self.bad("급식지도 계획을 붙임과 같이 계획하여", "급식지도를 붙임과 같이 하여", "어색한표현", "제안", para=p))
        self.assertIn("g.nouns", self.bad("붙임과 같이 계획하여", "붙임과 같이 계획 계획하여", "어색한표현", "제안", para=p))

    def test_notation_cannot_change_words(self):
        self.assertIn("g.notation_only", self.bad("실시하오니", "실시하니", "공문서표기"))

    def test_quote_blocked(self):
        self.assertIn("g.quote", self.bad("「학교안전법」", "「학교 안전법」"))

    def test_placeholder_blocked(self):
        p = "1. 관련: 교육청 OOOO(2026. OO. OO.)"
        self.assertIn("g.placeholder", self.bad("OOOO", "OOO", "오타", para=p))

    def test_protected_term_blocked(self):
        self.assertIn("g.protected", self.bad("가나도교육청", "가나교육청", "오타", protect=["가나도교육청"]))

    def test_typo_small_ok(self):
        p = "참석해 주시기 바람니다."
        self.assertEqual(self.bad("바람니다", "바랍니다", "오타", para=p), [])

    def test_typo_too_far(self):
        p = "참석해 주시기 바랍니다."
        self.assertIn("g.edit_far", self.bad("주시기 바랍니다", "주십시오", "맞춤법", para=p))

    def test_negation_blocked(self):
        p = "검증을 진행하지 않았다."
        self.assertIn("g.negation", self.bad("않았다", "못했다", "맞춤법", para=p))

    def test_an_ahn_spelling_allowed(self):
        p = "제출하지 안으면 처리할 수 없습니다."
        self.assertEqual(self.bad("안으면", "않으면", "맞춤법", para=p), [])

    def test_sentence_change_cannot_be_confirmed(self):
        self.assertIn("g.sentence_confirmed", self.bad("실시하오니", "실시하니", "비문", "확정"))

    def test_proposal_keeps_nouns(self):
        self.assertEqual(self.bad("교육을 실시하오니 협조 바랍니다", "교육을 실시하니 협조해 주시기 바랍니다", "어색한표현", "제안"), [])

    def test_proposal_changing_meaning_word_blocked(self):
        r = self.bad("안전 교육을 실시하오니", "보건 교육을 실시하오니", "비문", "제안")
        self.assertIn("g.nouns", r)

    def test_not_found_and_many(self):
        self.assertIn("g.not_found", self.bad("없는 글", "없는 말"))
        p = "협조 바랍니다. 협조 바랍니다."
        self.assertIn("g.many", self.bad("협조", "협 조", para=p))

    def test_same_and_kind_category(self):
        self.assertIn("g.same", self.bad("협조", "협조"))
        self.assertIn("g.kind", self.bad("근거하여안전", "근거하여 안전", kind="확인"))
        self.assertIn("g.category", self.bad("근거하여안전", "근거하여 안전", cat="문체"))

    def test_latin_blocked(self):
        p = "누리집 www.goe.go.kr 참고"
        self.assertIn("g.digits", self.bad("www.goe.go.kr", "www.goe.go.kr.", "공문서표기", para=p) + self.bad("www.goe.go.kr", "www.goe.kr", "오타", para=p))

    def test_protected_terms_from_record(self):
        r = {"표시": [{"분류": "이전 학교 정보", "설명": "「가나중학교」 자동 변경 안 함"},
                      {"분류": "금액", "설명": "「38,600원」 자동 변경 안 함"},
                      {"분류": "사람 이름 가능", "설명": "「담임교사가」 자동 변경 안 함"},
                      {"분류": "결재란", "설명": "「결재」 자동 변경 안 함"}]}
        self.assertEqual(pl.protected_terms(r), ["38,600원", "가나중학교", "담임교사"])


class GuardWithoutKiwi(unittest.TestCase):
    """kiwipiepy가 없을 때(설치 실패 등)도 문장 다듬기 검사가 뜻 낱말 바뀜을 막는다."""

    def setUp(self):
        self.saved = (pl._KIWI, pl.KIWI_MISSING)
        pl._KIWI, pl.KIWI_MISSING = None, True

    def tearDown(self):
        pl._KIWI, pl.KIWI_MISSING = self.saved

    def bad(self, b, a, para):
        return [k for k, _ in pl.check_entry({"kind": "제안", "category": "어색한표현", "before": b, "after": a}, para, [])]

    def test_simple_rule(self):
        P = "안전 교육을 실시하오니 협조 바랍니다."
        self.assertEqual(self.bad("실시하오니 협조 바랍니다", "실시하니 협조해 주시기 바랍니다", P), [])
        self.assertIn("g.nouns", self.bad("안전 교육을", "보건 교육을", P))
        p = "급식지도 계획을 붙임과 같이 계획하여 실시하고자 합니다."
        self.assertEqual(self.bad("급식지도 계획을 붙임과", "급식지도를 붙임과", p), [])
        self.assertIn("g.nouns", self.bad("급식지도 계획을 붙임과 같이 계획하여", "급식지도를 붙임과 같이 하여", p))
        self.assertTrue(pl.KIWI_MISSING)


class Flow(unittest.TestCase):
    """준비 → 검사 → 적용(확정) → 승인 → 적용(제안)을 가짜 결과 폴더에서."""

    def setUp(self):
        self.hub = tempfile.mkdtemp(prefix="pr_")
        self.res = os.path.join(self.hub, "작년공문_올해버전")
        w = os.path.join(self.res, REC)
        os.makedirs(os.path.join(w, "기록"))
        out = os.path.join(self.res, "묶음")
        os.makedirs(out)
        self.txt = os.path.join(out, "본문_업무관리시스템_붙여넣기.txt")
        wbytes(self.txt, "[제목]\r\n안전 교육 안내\r\n\r\n[본문]\r\n1. 근거하여안전 교육을 실시하오니 협조 바랍니다.\r\n2. 기해주시기바랍니다.  끝.\r\n".encode("utf-8-sig"))
        self.hw = os.path.join(out, "계획.hwpx")
        wbytes(self.hw, hwpx([["급식 지도", "를 실시 합니다."], ["2026. 3. 9.(월) 부터"], ["학생 명단"]]))
        self.stu = os.path.join(self.res, "학생자료_변환안함", "명단.txt")
        os.makedirs(os.path.dirname(self.stu))
        wbytes(self.stu, "10101 홍길동\n".encode("utf-8"))
        recs = [
            {"기록id": "파일-01-0001", "zip": "01", "rel": "a/본문.odt", "ext": ".odt", "상태": "변환 완료", "결과": [self.txt], "표시": [], "학생정보": False},
            {"기록id": "파일-01-0002", "zip": "01", "rel": "a/계획.hwp", "ext": ".hwp", "상태": "변환 완료", "결과": [self.hw], "표시": [], "학생정보": False},
            {"기록id": "파일-01-0003", "zip": "01", "rel": "a/명단.txt", "ext": ".txt", "상태": "변환 완료", "결과": [self.stu], "표시": [], "학생정보": True},
            {"기록id": "파일-01-0004", "zip": "01", "rel": "a/표.xlsx", "ext": ".xlsx", "상태": "변환 완료", "결과": [os.path.join(out, "표.xlsx")], "표시": [], "학생정보": False},
            {"기록id": "파일-01-0005", "zip": "01", "rel": "a/스캔.pdf", "ext": ".pdf", "상태": "일부", "결과": [os.path.join(out, "스캔 (OCR 변환).hwpx")], "표시": [], "학생정보": False},
            {"기록id": "파일-01-0006", "zip": "01", "rel": "a/견적.pdf", "ext": ".pdf", "상태": "원본 유지(서식 PDF)", "결과": [os.path.join(out, "견적.pdf")], "표시": [], "학생정보": False},
        ]
        wjson(recs, os.path.join(w, "기록", "결과기록.json"))
        self.run = pl.Run(self.res)

    def tearDown(self):
        shutil.rmtree(self.hub, ignore_errors=True)

    def quiet(self, fn, *a):
        with contextlib.redirect_stdout(io.StringIO()) as s:
            rc = fn(*a)
        return rc, s.getvalue()

    def entries(self, items):
        wjson({"항목": items}, self.run.entries)

    def test_prepare_skips(self):
        rc, out = self.quiet(proofread_prepare.main, [self.res])
        d = pl.jload(self.run.list_json)
        self.assertEqual([f["기록id"] for f in d["파일"]], ["파일-01-0001", "파일-01-0002"])
        self.assertEqual(d["학생자료건너뜀"], 1)
        why = {s["기록id"]: s["이유"] for s in d["건너뜀"]}
        T = pl.labels()
        self.assertEqual(why["파일-01-0004"], T["s.sheet"])
        self.assertEqual(why["파일-01-0005"], T["s.ocr"])
        self.assertEqual(why["파일-01-0006"], T["s.status"])
        txt = rtext(self.run.list_txt)
        self.assertNotIn("홍길동", txt + json.dumps(d, ensure_ascii=False))
        self.assertNotIn("명단.txt", txt + json.dumps(d, ensure_ascii=False))
        locs = [p["location"] for p in d["파일"][1]["문단"]]
        self.assertEqual(locs, ["Contents/section0.xml#1", "Contents/section0.xml#2", "Contents/section0.xml#3"])
        self.assertEqual(d["파일"][0]["문단"][0]["location"], "줄 2")
        with self.assertRaises(RuntimeError):
            self.quiet(proofread_prepare.main, [self.res])  # 덮어쓰지 않음

    def test_apply_all_and_revert(self):
        """설계 결정: 검사를 통과한 항목은 문장 다듬기까지 모두 적용, --revert로 골라 빼면 새 판."""
        self.quiet(proofread_prepare.main, [self.res])
        self.entries([
            E("Y001", "줄 5", "근거하여안전", "근거하여 안전"),
            E("Y002", "줄 6", "기해주시기바랍니다", "기해 주시기 바랍니다"),
            E("Y003", "줄 5", "실시하오니 협조 바랍니다", "실시하니 협조해 주시기 바랍니다", "제안", "어색한표현"),
            E("Y004", "Contents/section0.xml#1", "지도를 실시 합니다", "지도를 실시합니다", f="파일-01-0002"),
            E("Y005", "Contents/section0.xml#2", "2026. 3. 9.(월) 부터", "2026. 3. 10.(화)부터", "확정", "공문서표기", "파일-01-0002"),
            E("Y006", "줄 5", "안전", "안 전"),  # Y001과 겹침
        ])
        rc, out = self.quiet(proofread_guard.main, [self.res])
        self.assertEqual(rc, 1)
        chk = pl.jload(self.run.check_json)
        self.assertEqual(sorted(b["id"] for b in chk["막힘"]), ["Y005", "Y006"])   # 검사는 그대로 엄격
        before_txt = rbytes(self.txt)
        before_hw = rbytes(self.hw)
        rc, out = self.quiet(proofread_apply.main, [self.res])
        self.assertEqual(rc, 0)
        v1t = pl.version_path(self.txt, 1)
        s = rbytes(v1t)
        self.assertTrue(s.startswith(b"\xef\xbb\xbf"))
        s = s[3:].decode("utf-8")
        self.assertIn("\r\n1. 근거하여 안전 교육을 실시하니 협조해 주시기 바랍니다.\r\n", s)   # 문장 다듬기도 바로 적용
        self.assertIn("2. 기해 주시기 바랍니다.  끝.\r\n", s)
        hw1 = pl.paragraphs_of(pl.version_path(self.hw, 1))
        self.assertEqual(hw1["Contents/section0.xml#1"][1], "급식 지도를 실시합니다.")
        self.assertEqual(hw1["Contents/section0.xml#2"][1], "2026. 3. 9.(월) 부터")       # 막힌 항목은 안 넣음
        self.assertEqual(rbytes(self.txt), before_txt)   # 변환본은 그대로
        self.assertEqual(rbytes(self.hw), before_hw)
        T = pl.labels()
        ws = load_workbook(os.path.join(self.run.out, "검토표_윤문1.xlsx"))["윤문"]
        head = [c.value for c in ws[1]]
        self.assertNotIn("구분", head)
        col = head.index(T["h.state"])
        st = {r[0]: r[col] for r in ws.iter_rows(min_row=2, values_only=True)}
        self.assertEqual(st, {"Y001": T["st.applied"], "Y002": T["st.applied"], "Y003": T["st.applied"],
                              "Y004": T["st.applied"], "Y005": T["st.blocked"], "Y006": T["st.blocked"]})
        self.assertEqual(set(st.values()), {"적용", "막힘"})
        # 같은 상태로 다시 적용하면 새 판을 만들지 않음
        rc, out = self.quiet(proofread_apply.main, [self.res])
        self.assertIn(T["a.none"], out)
        self.assertFalse(os.path.exists(pl.version_path(self.txt, 2)))
        # 막힌 항목·없는 번호는 되돌릴 수 없음, 되돌리지 않은 항목은 다시 넣을 수 없음
        with self.assertRaises(SystemExit):
            self.quiet(proofread_apply.main, [self.res, "--revert", "Y005"])
        with self.assertRaises(SystemExit):
            self.quiet(proofread_apply.main, [self.res, "--revert", "Y999"])
        with self.assertRaises(SystemExit):
            self.quiet(proofread_apply.main, [self.res, "--restore", "Y001"])
        rc, out = self.quiet(proofread_apply.main, [self.res, "--revert", "Y003,Y004"])
        s2 = rbytes(pl.version_path(self.txt, 2))[3:].decode("utf-8")
        self.assertIn("1. 근거하여 안전 교육을 실시하오니 협조 바랍니다.\r\n", s2)
        self.assertEqual(rbytes(v1t)[3:].decode("utf-8"), s)                 # 앞 판 그대로
        self.assertFalse(os.path.exists(pl.version_path(self.hw, 2)))   # 넣을 항목이 없는 파일은 새 판을 만들지 않음(변환본 그대로)
        vers = pl.jload(self.run.versions)
        self.assertEqual([v["판"] for v in vers["판"]], [1, 2])
        self.assertEqual(vers["판"][1]["되돌린항목"], ["Y003", "Y004"])
        self.assertEqual(vers["판"][1]["넣은항목"], ["Y001", "Y002"])
        ws2 = load_workbook(os.path.join(self.run.out, "검토표_윤문2.xlsx"))["윤문"]
        st2 = {r[0]: r[col] for r in ws2.iter_rows(min_row=2, values_only=True)}
        self.assertEqual(st2["Y003"], T["st.reverted"])
        self.assertEqual(st2["Y001"], T["st.applied"])
        # 되돌린 항목은 다음 실행에도 이어짐
        rc, out = self.quiet(proofread_apply.main, [self.res])
        self.assertIn(T["a.none"], out)
        rc, out = self.quiet(proofread_apply.main, [self.res, "--restore", "Y004"])
        vers = pl.jload(self.run.versions)
        self.assertEqual(vers["판"][2]["되돌린항목"], ["Y003"])
        self.assertEqual(pl.paragraphs_of(pl.version_path(self.hw, 3))["Contents/section0.xml#1"][1], "급식 지도를 실시합니다.")
        self.assertEqual(pl.jload(self.run.versions)["판"][-1]["판"], 3)

    def test_colour_of(self):
        self.assertEqual(pl.colour_of({"category": "비문"}), "blue")
        self.assertEqual(pl.colour_of({"category": "어색한표현"}), "blue")
        for c in ("오타", "맞춤법", "띄어쓰기", "공문서표기"):
            self.assertEqual(pl.colour_of({"category": c}), "red")

    def test_split_runs(self):
        """여러 run에 나뉜 글도 서식 요소를 지우지 않고 바꾼다."""
        data = hwpx([["안전 교", "육을 실시", " 합니다."]])
        new = pl.replace_in_zip(data, "hwpx", {"Contents/section0.xml#1": [("실시 합니다", "실시합니다")]})
        xml = zipfile.ZipFile(io.BytesIO(new)).read("Contents/section0.xml").decode("utf-8")
        self.assertEqual(xml.count("<hp:run>"), 3)
        self.assertEqual(pl.zip_paragraphs(new, "hwpx")[0][2], "안전 교육을 실시합니다.")


class Capture(unittest.TestCase):
    """capture_compare: 텍스트 파일만 있는 가짜 작업(그림 없음, 한글·LibreOffice 안 엶)."""

    def test_red_blue_and_student_hidden(self):
        import capture_compare
        hub = tempfile.mkdtemp(prefix="pc_")
        try:
            R = os.path.join(hub, "a_올해버전")
            w = os.path.join(R, REC)
            os.makedirs(os.path.join(w, "기록"))
            src = os.path.join(w, "원본", "압축해제", "01", "a")
            os.makedirs(src)
            wbytes(os.path.join(src, "메모.txt"), "2025. 3. 4.(화)까지 근거하여안전 교육을 실시하오니 협조 바랍니다.\n".encode("utf-8"))
            wbytes(os.path.join(src, "명단.txt"), "10101 홍길동\n".encode("utf-8"))
            out = os.path.join(R, "a")
            os.makedirs(out)
            res = os.path.join(out, "메모.txt")
            wbytes(res, "2026. 3. 3.(화)까지 근거하여안전 교육을 실시하오니 협조 바랍니다.\n".encode("utf-8"))
            stu = os.path.join(R, "학생자료_변환안함", "명단.txt")
            os.makedirs(os.path.dirname(stu))
            wbytes(stu, "10101 홍길동\n".encode("utf-8"))
            recs = [{"기록id": "파일-01-0001", "zip": "01", "rel": "a/메모.txt", "ext": ".txt", "상태": "변환 완료", "결과": [res], "표시": [],
                     "학생정보": False, "바꿈": [{"위치": "본문", "원문": "2025. 3. 4.(화)", "새글": "2026. 3. 3.(화)", "원래날짜": "2025-03-04"}]},
                    {"기록id": "파일-01-0002", "zip": "01", "rel": "a/명단.txt", "ext": ".txt", "상태": "변환 완료", "결과": [stu], "표시": [],
                     "학생정보": True, "바꿈": []}]
            wjson(recs, os.path.join(w, "기록", "결과기록.json"))
            wjson({"대상학년도": 2026}, os.path.join(w, "기록", "실행정보.json"))
            with contextlib.redirect_stdout(io.StringIO()):
                proofread_prepare.main([R])
                run = pl.Run(R)
                wjson({"항목": [E("Y001", "줄 1", "근거하여안전", "근거하여 안전"),
                               E("Y002", "줄 1", "실시하오니 협조 바랍니다", "실시하니 협조해 주시기 바랍니다", "제안", "어색한표현"),
                               E("Y003", "줄 1", "안전 교육", "보건 교육", "제안", "비문")]}, run.entries)   # 뜻 낱말이 바뀌어 막힘
                proofread_apply.main([R])
                capture_compare.main([R, "--no-render"])
            page = rtext(os.path.join(R, "전후캡처비교.html"))
            self.assertNotIn("홍길동", page)
            self.assertNotIn("명단", page)
            T = capture_compare.T
            self.assertEqual(page.count('<mark class="chg"'), 4)   # 날짜(전·후) + 띄어쓰기(전·후)
            self.assertEqual(page.count('<mark class="sent"'), 2)  # 문장 다듬음: 전은 원래 글, 후는 고친 글
            self.assertIn('<sup class="mn sent">3</sup>실시하오니 협조 바랍니다</mark>', page)
            self.assertIn('<sup class="mn sent">3</sup>실시하니 협조해 주시기 바랍니다</mark>', page)
            for gone in ("callout", "dashed var(--prop)", "mark.prop", T["c.version0"] + "판"):
                self.assertNotIn(gone, page)
            self.assertIn(T["c.sent_item"].replace("{ID}", "Y002"), page)
            self.assertIn("문장 다듬음 Y002:", page)
            self.assertIn(T["c.blocked_heading"], page)
            self.assertIn("검사에서 막혀 적용 안 함", page)
            self.assertIn("보건 교육", page)                       # 막힌 항목은 목록에만
            self.assertIn(T["c.legend_red"], page)
            self.assertIn(T["c.legend_blue"], page)
            self.assertIn('class="legend"', page)
            rep = pl.jload(os.path.join(w, "캡처", "판1", "mark_report.json"))
            f1 = rep["파일별"]["파일-01-0001"]
            sent = [x for x in f1["번호별"] if x["색"] == "blue"]
            self.assertEqual([(x["윤문id"], x["찾음"]) for x in sent], [("Y002", ["a", "b"])])
            self.assertEqual(f1["못찾은곳"], [])
            self.assertEqual(f1["막힘"], ["Y003"])
            with self.assertRaises(SystemExit):   # 같은 판 HTML은 덮어쓰지 않음(두 번째는 _윤문1 이름, 그다음은 막힘)
                with contextlib.redirect_stdout(io.StringIO()):
                    capture_compare.main([R, "--no-render"])
                    capture_compare.main([R, "--no-render"])
            self.assertTrue(os.path.exists(os.path.join(R, "전후캡처비교_윤문1.html")))
            with contextlib.redirect_stdout(io.StringIO()):   # --붙임: 새 이름으로 따로 만든다
                capture_compare.main([R, "--no-render", "--붙임", "_v2"])
            self.assertTrue(os.path.exists(os.path.join(R, "전후캡처비교_윤문1_v2.html")))
            self.assertTrue(os.path.exists(os.path.join(w, "캡처", "판1", "mark_report_v2.json")))
            self.assertEqual(rtext(os.path.join(R, "전후캡처비교.html")), page)
            with self.assertRaises(SystemExit):
                with contextlib.redirect_stdout(io.StringIO()):
                    capture_compare.main([R, "--no-render", "--붙임", "v2"])
            # 되돌리면 다음 판에서는 상자 없이 「되돌림」 목록에만
            with contextlib.redirect_stdout(io.StringIO()):
                proofread_apply.main([R, "--revert", "Y002"])
                capture_compare.main([R, "--no-render"])
            p2 = rtext(os.path.join(R, "전후캡처비교_윤문2.html"))
            self.assertEqual(p2.count('<mark class="sent"'), 0)
            self.assertIn(T["c.reverted_heading"], p2)
            self.assertIn('class="off rev"', p2)
        finally:
            shutil.rmtree(hub, ignore_errors=True)


class CaptureDraw(unittest.TestCase):
    """그림 위 표시: 빨강·파랑 모두 실선 상자, 말풍선 없음."""

    def test_solid_boxes_both_colours(self):
        import capture_compare as cc
        from PIL import Image
        d = tempfile.mkdtemp(prefix="pd_")
        self.addCleanup(shutil.rmtree, d, True)
        p = os.path.join(d, "p.jpg")
        Image.new("RGB", (600, 800), (255, 255, 255)).save(p)
        out = os.path.join(d, "o.jpg")
        size = (600 * 72 / cc.DPI, 800 * 72 / cc.DPI)          # 그림 1픽셀 = 쪽 좌표 72/DPI
        sc = 600 / size[0]
        cc.draw_marks(p, size, [("4", "blue", (100 / sc, 300 / sc, 200 / sc, 315 / sc)),
                                ("5", "red", (100 / sc, 500 / sc, 200 / sc, 515 / sc))], out)
        im = Image.open(out).convert("RGB")
        blue = lambda c: c[2] > 150 and c[0] < 120
        red = lambda c: c[0] > 150 and c[2] < 120
        self.assertTrue(all(blue(im.getpixel((x, 298))) for x in range(110, 195)))   # 파랑도 끊김 없는 실선
        self.assertTrue(all(red(im.getpixel((x, 498))) for x in range(110, 195)))
        inside = [im.getpixel((x, y)) for x in range(110, 190) for y in range(304, 312)]
        self.assertTrue(all(min(c) > 200 for c in inside))                           # 상자 안 글을 덮지 않음
        self.assertFalse(hasattr(cc, "place_callout") or hasattr(cc, "dashed_rect"))

    def test_text_panel_colours(self):
        import capture_compare as cc
        h = cc.text_panel("가나다\n라마바", "t", [(0, 3, 1, True, "red"), (4, 7, 2, True, "blue")])
        self.assertIn('<mark class="chg"><sup class="mn chg">1</sup>가나다</mark>', h)
        self.assertIn('<mark class="sent"><sup class="mn sent">2</sup>라마바</mark>', h)
        self.assertNotIn("callout", h)


if __name__ == "__main__":
    unittest.main()
