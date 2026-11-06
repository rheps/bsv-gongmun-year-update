# -*- coding: utf-8 -*-
"""convert.py 처음부터 끝까지 시험. 합성 자료만 쓴다(실제 문서·학교·개인 자료 없음).
임시 폴더에 합성 입력을 만들고 그 옆에 결과 폴더가 생기는지 본다.
한글·LibreOffice는 열지 않는다(--no-verify, hwp·pdf·xls 입력 없음).
사용: py -3 -m unittest discover -s tests"""
import os, sys, io, json, glob, shutil, zipfile, hashlib, tempfile, unittest, datetime as dt, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "bsv-gongmun-year-update", "tools")
sys.path.insert(0, TOOL)
FIX = os.path.join(HERE, "fixtures", "holidays")
import warnings
warnings.simplefilter("ignore", ResourceWarning)
import convert
from openpyxl import load_workbook

HP = 'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'


def zbytes(members):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in members.items():
            z.writestr(n, d)
    return b.getvalue()


def odt(lines):
    ps = "".join(f"<text:p>{l}</text:p>" for l in lines)
    content = ('<?xml version="1.0" encoding="UTF-8"?><office:document-content '
               'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
               'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
               'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
               'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0">'
               f'<office:body><office:text>{ps}</office:text></office:body></office:document-content>')
    return zbytes({"mimetype": "application/vnd.oasis.opendocument.text", "content.xml": content})


def hwpx(text):
    sec = f'<?xml version="1.0" encoding="UTF-8"?><hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" {HP}><hp:p><hp:run><hp:t>{text}</hp:t></hp:run></hp:p></hs:sec>'
    return zbytes({"mimetype": "application/hwp+zip", "Contents/section0.xml": sec})


def docx(text):
    doc = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f'<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>')
    return zbytes({"word/document.xml": doc})


SERIAL0 = dt.date(1899, 12, 30)


def xlsx(d):
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    styles = f'<?xml version="1.0" encoding="UTF-8"?><styleSheet {ns}><cellXfs count="2"><xf numFmtId="0"/><xf numFmtId="14"/></cellXfs></styleSheet>'
    sheet = (f'<?xml version="1.0" encoding="UTF-8"?><worksheet {ns}><sheetData>'
             '<row r="1"><c r="A1" t="inlineStr"><is><t>일자</t></is></c></row>'
             f'<row r="2"><c r="A2" s="1"><v>{(d - SERIAL0).days}</v></c></row></sheetData></worksheet>')
    wbk = f'<?xml version="1.0" encoding="UTF-8"?><workbook {ns}><sheets><sheet name="계획" sheetId="1"/></sheets></workbook>'
    return zbytes({"xl/styles.xml": styles, "xl/worksheets/sheet1.xml": sheet, "xl/workbook.xml": wbk})


def h(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="gongmun_e2e_")
        cls.rules = os.path.join(cls.root, "표시규칙.json")
        json.dump({"분류별낱말": {"이전 학교 정보": ["가나중"]}}, open(cls.rules, "w", encoding="utf-8"))
        files = {
            "3월/학부모총회 안내.txt": "2025. 3. 14.(금) 학부모 총회\n".encode("utf-8"),
            "3월/2025학년도 계획 공문.odt": odt(["가나중학교", "수신", "내부결재", "제목", "2025학년도 현장체험학습 계획",
                                            "1. 2025학년도 현장체험학습을 다음과 같이 실시하고자 합니다.",
                                            "가. 일시: 2025. 10. 17.(금) 9시 30분", "붙임 계획서 1부. 끝.",
                                            "시행", "가나중학교-1234", "(", "2025. 9. 1.", ")"]),
            "4월/협의회.hwpx": hwpx("2025. 4. 4.(금) 협의회"),
            "4월/운영 계획.docx": docx("2025학년도 운영 계획 2025. 5. 14.(수)"),
            "4월/일정표.xlsx": xlsx(dt.date(2025, 4, 4)),
            "4월/사진.jpg": b"\xff\xd8\xff\xe0 synthetic image bytes",
            "4월/참가명단.txt": "1반 1번 가\n1반 2번 나\n1반 3번 다\n".encode("utf-8"),
        }
        cls.zip_in = os.path.join(cls.root, "작년 업무.zip")
        open(cls.zip_in, "wb").write(zbytes(files))
        cls.dir_in = os.path.join(cls.root, "따로 받은 폴더")
        os.makedirs(cls.dir_in)
        open(os.path.join(cls.dir_in, "기한.txt"), "w", encoding="utf-8").write("제출 기한: 2025. 10. 31.(금)까지\n")
        cls.before = {p: h(p) for p in (cls.zip_in, os.path.join(cls.dir_in, "기한.txt"))}
        with contextlib.redirect_stdout(io.StringIO()) as cls.out:
            cls.rc = convert.main(["--input", cls.zip_in, cls.dir_in, "--holiday-dir", FIX,
                                   "--run-date", "2026-11-04", "--allow-unverified-holidays", "--no-verify", "--quiet",
                                   "--flag-rules", cls.rules])
        cls.res = os.path.join(cls.root, "작년 업무_올해버전")
        cls.task = os.path.join(cls.res, "_작업기록")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def find(self, root, pattern):
        got = [x for x in glob.glob(os.path.join(root, "**", pattern), recursive=True) if "_작업기록" not in x]
        self.assertEqual(len(got), 1, (pattern, got))
        return got[0]

    def test_exit_and_layout(self):
        self.assertEqual(self.rc, 0, self.out.getvalue())
        for p in ("기록/파일목록.json", "기록/결과기록.json", "기록/검증기록.json", "기록/실행정보.json", "기록/변환요약.json"):
            self.assertTrue(os.path.exists(os.path.join(self.task, p)), p)
        self.assertFalse(os.path.exists(os.path.join(self.task, "임시")))
        self.assertTrue(os.path.exists(os.path.join(self.task, "원본", "01_작년 업무.zip")))
        self.assertTrue(os.path.exists(os.path.join(self.res, "검토표.xlsx")))
        self.assertIn(self.res, self.out.getvalue())

    def test_originals_untouched(self):
        for p, v in self.before.items():
            self.assertEqual(h(p), v)
        self.assertEqual(sorted(os.listdir(self.dir_in)), ["기한.txt"])

    def test_text_dates(self):
        s = open(self.find(self.res, "학부모총회 안내.txt"), encoding="utf-8").read()
        self.assertIn("2026. 3. 13.(금)", s)
        s = open(self.find(self.res, "기한.txt"), encoding="utf-8").read()
        self.assertIn("2026. 10. 30.(금)까지", s)

    def test_folder_names_moved(self):
        self.assertTrue(glob.glob(os.path.join(self.res, "01_작년 업무", "3월")))

    def test_odt_paste(self):
        p = self.find(self.res, "*_업무관리시스템_붙여넣기.txt")
        self.assertIn("2026학년도 계획 공문", os.path.basename(p))
        s = open(p, encoding="utf-8-sig").read()
        self.assertIn("2026학년도 현장체험학습 계획", s)
        self.assertIn("1. 관련: ", s)
        self.assertIn("2. 2026학년도", s)
        self.assertIn("2026. 10. 16.(금) 09:30", s)
        self.assertIn("  끝.", s)
        self.assertFalse([x for x in glob.glob(os.path.join(self.res, "**", "*.odt"), recursive=True) if "_작업기록" not in x])

    def test_hwpx_docx(self):
        z = zipfile.ZipFile(self.find(self.res, "협의회.hwpx"))
        self.assertIn("2026. 4. 3.(금)", z.read("Contents/section0.xml").decode("utf-8"))
        z = zipfile.ZipFile(self.find(self.res, "운영 계획.docx"))
        s = z.read("word/document.xml").decode("utf-8")
        self.assertIn("2026학년도", s); self.assertIn("2026. 5. 13.(수)", s)

    def test_xlsx_serial(self):
        z = zipfile.ZipFile(self.find(self.res, "일정표.xlsx"))
        self.assertIn(f"<v>{(dt.date(2026, 4, 3) - SERIAL0).days}</v>", z.read("xl/worksheets/sheet1.xml").decode("utf-8"))

    def test_unconvertible_copied(self):
        p = self.find(self.res, "사진.jpg")
        self.assertEqual(open(p, "rb").read(), b"\xff\xd8\xff\xe0 synthetic image bytes")
        R = json.load(open(os.path.join(self.task, "기록", "결과기록.json"), encoding="utf-8"))
        jpg = [r for r in R if r["rel"].endswith("사진.jpg")][0]
        self.assertEqual(jpg["상태"], "변환 안 함")

    def test_student_data_copied_unchanged(self):
        p = self.find(self.res, "참가명단*")
        self.assertIn("학생자료_변환안함", p)
        self.assertEqual(open(p, encoding="utf-8").read(), "1반 1번 가\n1반 2번 나\n1반 3번 다\n")
        R = json.load(open(os.path.join(self.task, "기록", "결과기록.json"), encoding="utf-8"))
        self.assertEqual([r["상태"] for r in R if r["rel"].endswith("참가명단.txt")], ["학생 자료(변환 안 함)"])

    def test_review_workbook(self):
        lab = convert.MSG()
        wb = load_workbook(os.path.join(self.res, "검토표.xlsx"))
        self.assertEqual(wb.sheetnames, [lab[1], lab[2], lab[3], lab[4], lab[83], lab[77], lab[5]])
        cats = [r[2] for r in wb[lab[4]].iter_rows(min_row=2, values_only=True)]
        self.assertIn(lab[47], cats)  # 표시 규칙 파일의 이전 학교 낱말·학교 이름
        summary = [r for r in wb[lab[1]].iter_rows(values_only=True)]
        self.assertIn((lab[14], 1), [tuple(x[:2]) for x in summary if x and x[0]])
        names = [r[2] for r in wb[lab[2]].iter_rows(min_row=2, values_only=True)]
        self.assertFalse([n for n in names if "참가명단" in str(n)])   # 학생 자료는 검토표에 이름을 적지 않음

    def test_rerun_makes_new_folder(self):
        with contextlib.redirect_stdout(io.StringIO()):
            rc = convert.main(["--input", self.dir_in, "--holiday-dir", FIX, "--run-date", "2026-11-04",
                               "--allow-unverified-holidays", "--no-verify", "--quiet"])
        self.assertEqual(rc, 0)
        a = os.path.join(self.root, "따로 받은 폴더_올해버전")
        self.assertTrue(os.path.exists(os.path.join(a, "기한.txt")))   # 입력이 하나면 결과 폴더 바로 아래
        with contextlib.redirect_stdout(io.StringIO()):
            convert.main(["--input", self.dir_in, "--holiday-dir", FIX, "--run-date", "2026-11-04",
                          "--allow-unverified-holidays", "--no-verify", "--quiet"])
        self.assertTrue(os.path.exists(os.path.join(self.root, "따로 받은 폴더_올해버전2", "기한.txt")))
        self.assertEqual(open(os.path.join(a, "기한.txt"), encoding="utf-8").read(), "제출 기한: 2026. 10. 30.(금)까지\n")


class CommitteeZipIsStudentData(unittest.TestCase):
    """zip 이름에 학생생활교육위원회가 있으면 안의 파일 이름에 낱말이 없어도 학생 자료로 둔다."""

    def test_zip_name_marks_student(self):
        root = tempfile.mkdtemp(prefix="gongmun_committee_")
        try:
            z = os.path.join(root, "2. 비 정기 생산 문서 (학생생활교육위원회).zip")
            open(z, "wb").write(zbytes({"1. 1회/회의 개최 안내.txt": "2025. 4. 4.(금) 회의\n".encode("utf-8")}))
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc = convert.main(["--input", z, "--holiday-dir", FIX, "--run-date", "2026-11-04",
                                   "--allow-unverified-holidays", "--no-verify", "--quiet"])
            self.assertEqual(rc, 0, out.getvalue())
            res = glob.glob(os.path.join(root, "*_올해버전"))[0]
            got = [x for x in glob.glob(os.path.join(res, "**", "회의 개최 안내*"), recursive=True) if "_작업기록" not in x]
            self.assertEqual(len(got), 1)
            self.assertIn("학생자료_변환안함", got[0])
            self.assertEqual(open(got[0], encoding="utf-8").read(), "2025. 4. 4.(금) 회의\n")   # 바꾸지 않음
        finally:
            shutil.rmtree(root, ignore_errors=True)


class Stops(unittest.TestCase):
    def setUp(self):
        self.hub = tempfile.mkdtemp(prefix="gongmun_stop_")

    def tearDown(self):
        shutil.rmtree(self.hub, ignore_errors=True)

    def made(self):
        return [x for x in os.listdir(self.hub) if "_올해버전" in x]

    def test_missing_holiday_year_stops_before_anything(self):
        f = os.path.join(self.hub, "a.txt"); open(f, "w", encoding="utf-8").write("2025. 4. 4.(금)")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = convert.main(["--input", f, "--holiday-dir", FIX, "--target-school-year", "2030", "--quiet"])
        self.assertEqual(rc, 2)
        self.assertIn("2030", out.getvalue())
        self.assertEqual(self.made(), [])

    def test_unverified_holidays_stop_without_flag(self):
        f = os.path.join(self.hub, "a.txt"); open(f, "w", encoding="utf-8").write("2025. 4. 4.(금)")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = convert.main(["--input", f, "--holiday-dir", FIX, "--run-date", "2026-11-04", "--quiet"])
        self.assertEqual(rc, 2)
        self.assertIn("--allow-unverified-holidays", out.getvalue())
        self.assertEqual(self.made(), [])

    def test_shipped_holidays_are_verified(self):
        f = os.path.join(self.hub, "b.txt"); open(f, "w", encoding="utf-8").write("2025. 4. 4.(금)")
        with contextlib.redirect_stdout(io.StringIO()):
            rc = convert.main(["--input", f, "--run-date", "2026-11-04", "--no-verify", "--quiet"])
        self.assertEqual(rc, 0)
        self.assertEqual(open(os.path.join(self.hub, "b_올해버전", "b.txt"), encoding="utf-8").read(), "2026. 4. 3.(금)")

    def test_missing_hwp_stops(self):
        f = os.path.join(self.hub, "c.hwp"); open(f, "wb").write(b"x")
        os.environ["BSV_GONGMUN_NO_HWP"] = "1"
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc = convert.main(["--input", f, "--run-date", "2026-11-04", "--quiet"])
        finally:
            del os.environ["BSV_GONGMUN_NO_HWP"]
        self.assertEqual(rc, 4)
        self.assertIn(convert.T()["d.hwp_missing"], out.getvalue())
        self.assertEqual(self.made(), [])

    def test_missing_input(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = convert.main(["--input", os.path.join(self.hub, "없음.zip"), "--holiday-dir", FIX, "--quiet"])
        self.assertEqual(rc, 3)
        self.assertEqual(self.made(), [])

    def test_existing_output_not_overwritten(self):
        f = os.path.join(self.hub, "d.txt"); open(f, "w", encoding="utf-8").write("2025. 4. 4.(금)")
        o = os.path.join(self.hub, "있는폴더"); os.makedirs(o)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = convert.main(["--input", f, "--output", o, "--run-date", "2026-11-04", "--no-verify", "--quiet"])
        self.assertEqual(rc, 5)
        self.assertEqual(os.listdir(o), [])


class NoLibreOffice(unittest.TestCase):
    """LibreOffice가 없으면 xls는 그대로 복사하고 안내를 남긴다."""

    def test_xls_copied_with_note(self):
        import office
        root = tempfile.mkdtemp(prefix="gongmun_nolo_")
        old = office._SOFFICE
        os.environ["BSV_GONGMUN_NO_LIBREOFFICE"] = "1"
        office._SOFFICE = None
        try:
            d = os.path.join(root, "작년")
            os.makedirs(d)
            open(os.path.join(d, "표.xls"), "wb").write(b"\xd0\xcf\x11\xe0 synthetic")
            open(os.path.join(d, "a.txt"), "w", encoding="utf-8").write("2025. 4. 4.(금)")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = convert.main(["--input", d, "--run-date", "2026-11-04", "--no-verify", "--quiet"])
            self.assertEqual(rc, 0)
            res = os.path.join(root, "작년_올해버전")
            self.assertEqual(open(os.path.join(res, "표.xls"), "rb").read(), b"\xd0\xcf\x11\xe0 synthetic")
            R = json.load(open(os.path.join(res, "_작업기록", "기록", "결과기록.json"), encoding="utf-8"))
            x = [r for r in R if r["rel"] == "표.xls"][0]
            self.assertEqual(x["상태"], "변환 안 함")
            self.assertIn(convert.T()["d.lo_missing_xls"], x["비고"])
        finally:
            del os.environ["BSV_GONGMUN_NO_LIBREOFFICE"]
            office._SOFFICE = old
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=1)
