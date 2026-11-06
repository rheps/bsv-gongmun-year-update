# -*- coding: utf-8 -*-
"""2026-11-04 고친 세 가지 시험(합성 자료만): 서식 PDF 원본 유지, 딸린 날짜 순서, odt 붙여넣기 글 띄어쓰기.
사용: py -3 -m unittest discover -s tests"""
import os, sys, io, json, glob, shutil, zipfile, hashlib, tempfile, unittest, contextlib, warnings
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bsv-gongmun-year-update", "tools"))
FIX = os.path.join(HERE, "fixtures", "holidays")
warnings.simplefilter("ignore", ResourceWarning)
import pymupdf as fitz
import dateconv as dc
import pdflayout
import make_paste
import gongmun_format as gf
import convert
from openpyxl import load_workbook

# 작은 PNG(도장·로고 자리)
PNG = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 4, 4), 0).tobytes("png")


def layout_pdf(path):
    """가로 쪽, 표 괘선, 그림, 날짜 두 개가 있는 견적서 모양 PDF."""
    d = fitz.open()
    p = d.new_page(width=842, height=595)
    p.insert_text((60, 80), "견적서", fontname="korea", fontsize=20)
    p.insert_text((60, 120), "견적일 : 2025년 10월 23일", fontname="korea", fontsize=11)
    p.insert_text((60, 145), "기간 : 2025년 10월 30일(목) ~ 31일(금)", fontname="korea", fontsize=11)
    for k, t in enumerate(["품명 숙박비 단체 급식비 수련활동비 시설이용료", "인원 173명 단가 8,000원 공급가액 1,384,000원"]):
        p.insert_text((70, 200 + 30 * k), t, fontname="korea", fontsize=10)
    for k in range(6):
        p.draw_line((60, 180 + 30 * k), (780, 180 + 30 * k))
    for x in (60, 300, 540, 780):
        p.draw_line((x, 180), (x, 330))
    p.insert_image(fitz.Rect(700, 40, 760, 100), stream=PNG)
    d.save(path); d.close()


def plain_pdf(path):
    d = fitz.open()
    p = d.new_page(width=595, height=842)
    for i, t in enumerate(["안내", "학부모 총회를 2025년 3월 14일(금)에 엽니다.", "많은 참석 바랍니다."]):
        p.insert_text((60, 80 + 24 * i), t, fontname="korea", fontsize=11)
    d.save(path); d.close()


class LayoutPdf(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gongmun_fix_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_detect_layout_and_plain(self):
        a, b = os.path.join(self.tmp, "a.pdf"), os.path.join(self.tmp, "b.pdf")
        layout_pdf(a); plain_pdf(b)
        self.assertTrue(pdflayout.detect(a)["서식"])
        self.assertFalse(pdflayout.detect(b)["서식"])  # 글만 있는 PDF는 예전처럼 hwpx로 다시 만든다

    def test_planned_dates_with_page_and_box(self):
        dc.configure(2026, holiday_dir=FIX, allow_unverified=True)
        a = os.path.join(self.tmp, "a.pdf"); layout_pdf(a)
        items, ch, fl = pdflayout.planned_dates(a, 2025, 1)
        got = {(x["쪽"], x["원문"], x["새글"]) for x in items}
        self.assertIn((1, "2025년 10월 23일", "2026년 10월 22일"), got)
        self.assertIn((1, "2025년 10월 30일(목)", "2026년 10월 29일(목)"), got)
        self.assertIn((1, "31일(금)", "30일(금)"), got)
        for x in items:
            self.assertEqual(len(x["상자"]), 4)
            self.assertLess(x["상자"][0], x["상자"][2])

    def test_e2e_kept_unchanged_and_listed(self):
        src = os.path.join(self.tmp, "입력"); os.makedirs(src)
        pdf = os.path.join(src, "2025학년도 견적서.pdf"); layout_pdf(pdf)
        self.assertEqual(convert.pdf_kind(pdf), "글자")  # 글자 PDF여야 한글(OCR)을 열지 않음
        before = hashlib.sha256(open(pdf, "rb").read()).hexdigest()
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = convert.main(["--input", src, "--holiday-dir", FIX, "--run-date", "2026-11-04",
                               "--allow-unverified-holidays", "--no-verify", "--quiet"])
        self.assertEqual(rc, 0, out.getvalue())
        res = os.path.join(self.tmp, "입력_올해버전")
        task = os.path.join(res, "_작업기록")
        self.assertFalse(glob.glob(os.path.join(res, "**", "*.hwpx"), recursive=True))
        outs = [x for x in glob.glob(os.path.join(res, "**", "*.pdf"), recursive=True) if "_작업기록" not in x]
        self.assertEqual(len(outs), 1)
        self.assertEqual(hashlib.sha256(open(outs[0], "rb").read()).hexdigest(), before)
        R = json.load(open(os.path.join(task, "기록", "결과기록.json"), encoding="utf-8"))
        self.assertEqual(R[0]["상태"], "원본 유지(서식 PDF)")
        self.assertEqual(len(R[0]["고칠날짜"]), 3)
        lab = convert.MSG()
        wb = load_workbook(os.path.join(res, "검토표.xlsx"))
        rows = [r for r in wb[lab[4]].iter_rows(min_row=2, values_only=True) if r[2] == lab[136]]
        self.assertEqual(len(rows), 3)
        self.assertTrue(any(r[3] == lab[143].replace("{N}", "1") and "→ 2026년 10월 22일" in r[5] for r in rows))
        files = [r for r in wb[lab[2]].iter_rows(min_row=2, values_only=True)]
        self.assertEqual(files[0][4], lab[136])
        s = out.getvalue()
        self.assertIn(lab[144], s)
        self.assertIn("2025년 10월 23일 → 2026년 10월 22일", s)
        summ = json.load(open(os.path.join(task, "기록", "변환요약.json"), encoding="utf-8"))
        self.assertEqual(len(summ["원본유지서식PDF"][0]["고칠날짜"]), 3)


class LinkedDays(unittest.TestCase):
    def setUp(self):
        dc.configure(2026, holiday_dir=FIX, allow_unverified=True)

    def test_day_only_follows_anchor(self):
        # 2025-10-15(수) → 2026-10-21(수). 다음 날인 16일은 22일로 같이 옮겨 회의 → 품의 순서를 지킨다
        new, ch, fl, _ = dc.convert("10월 15일에 있을 운영위원회 이후 16일쯤 품의하세요.", base_sy=2025)
        self.assertIn("10월 21일에", new)
        self.assertIn("22일쯤", new)
        c = [x for x in ch if x.get("규칙") == "딸린 날짜(같은 날수)"][0]
        self.assertEqual((c["원래날짜"], c["새날짜"]), ("2025-10-16", "2026-10-22"))

    def test_non_dates_untouched(self):
        t = "10월 15일 출발, 1박2일, 3일간, (숙박형, 1일형), 5일 이내 제출"
        new, ch, fl, _ = dc.convert(t, base_sy=2025)
        for s in ("1박2일", "3일간", "1일형", "5일 이내"):
            self.assertIn(s, new)
        self.assertFalse([x for x in ch if x.get("규칙") == "딸린 날짜(같은 날수)"])

    def test_unclear_dependency_flagged(self):
        # 앞에 기준 날짜가 없고 뒤에만 있으면 옮기지 않고 '날짜 순서 확인'
        new, ch, fl, _ = dc.convert("16일쯤 품의, 운영위원회는 10월 15일", base_sy=2025)
        self.assertTrue(new.startswith("16일쯤"))
        self.assertIn(dc.CAT_ORDER, [f["분류"] for f in fl])
        # 옮긴 날이 다른 달로 넘어가면 옮기지 않고 표시
        # 2025-10-22(수) → 2026-10-28(수). 31일은 같은 날수로 옮기면 11월 3일이라 '31일'로 쓸 수 없음
        new, ch, fl, _ = dc.convert("10월 22일 회의 후 31일까지 정리", base_sy=2025)
        self.assertIn("10월 28일", new)
        self.assertIn("31일까지", new)
        self.assertIn(dc.CAT_ORDER, [f["분류"] for f in fl])

    def test_file_name_kept_and_listed(self):
        self.assertEqual(dc.name_day_refs("15일 학운위 이후 품의 시 주의점"), ["15일"])
        tmp = tempfile.mkdtemp(prefix="gongmun_fix_")
        try:
            f = os.path.join(tmp, "15일 학운위 메모.txt")
            open(f, "w", encoding="utf-8").write("10월 15일 학운위 이후 16일쯤 품의\n")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = convert.main(["--input", f, "--holiday-dir", FIX, "--run-date", "2026-11-04",
                                   "--allow-unverified-holidays", "--no-verify", "--quiet"])
            self.assertEqual(rc, 0)
            res = os.path.join(tmp, "15일 학운위 메모_올해버전")
            out = os.path.join(res, "15일 학운위 메모.txt")
            self.assertIn("22일쯤", open(out, encoding="utf-8").read())
            R = json.load(open(os.path.join(res, "_작업기록", "기록", "결과기록.json"), encoding="utf-8"))
            self.assertTrue(any(x["분류"] == dc.CAT_ORDER and x["위치"] == "파일 이름" for x in R[0]["표시"]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_document_order_reversal_flagged(self):
        ch = [{"위치": "본문 1번째 문단", "원문": "2. 25.", "원래날짜": "2026-02-25", "새날짜": "2027-02-24"},
              {"위치": "본문 2번째 문단", "원문": "3. 4.", "원래날짜": "2026-03-04", "새날짜": "2026-03-03"},
              {"위치": "본문 3번째 문단", "원문": "3. 10.", "원래날짜": "2026-03-10", "새날짜": "2026-03-09"}]
        fl = dc.order_check(ch)
        self.assertEqual(len(fl), 1)
        self.assertEqual(fl[0]["분류"], "날짜 순서 바뀜")
        self.assertEqual(dc.order_check(ch[1:]), [])


ODT_NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
          'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
          'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
          'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"')


def odt_raw(paras):
    content = (f'<?xml version="1.0" encoding="UTF-8"?><office:document-content {ODT_NS}><office:body><office:text>'
               + "".join(f"<text:p>{p}</text:p>" for p in paras) + "</office:text></office:body></office:document-content>")
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("content.xml", content)
    return b.getvalue()


class PasteSpacing(unittest.TestCase):
    def parse(self, paras):
        log = []
        t, body, att = make_paste.parse(odt_raw(["제목", "안내", "수신"] + paras + ["시행"]), log)
        return t, " / ".join(s for s, _ in body), log

    def test_space_elements_and_line_breaks(self):
        t, body, log = self.parse([
            '<text:span>1. 매뉴얼에 근거하여</text:span><text:span><text:s/>안전 점검에 만전을 기해주시기</text:span><text:span><text:s/>바랍니다.</text:span>',
            '2. 줄을 바꾼<text:line-break/>문장과 K-<text:line-break/>에듀파인<text:s text:c="2"/>끝.'])
        self.assertIn("근거하여 안전 점검에 만전을 기해주시기 바랍니다.", body)
        self.assertIn("줄을 바꾼 문장과", body)
        self.assertIn("K-에듀파인", body)  # 붙임표로 나뉜 낱말 안에는 빈칸을 넣지 않음
        self.assertTrue(any(x[3] == make_paste.R_JOIN for x in log))

    def test_colon_rule_and_spacing_check(self):
        log = []
        t2, lines, items = gf.format_paste("안내", [("1. 조사항목:2026학년도 현황", "p"), ("2. 일시: 18:00까지", "p")], [], log)
        self.assertIn("조사항목: 2026학년도", lines[1])
        self.assertIn("18:00", lines[2])
        self.assertTrue(any(x[3] == gf.R_COLON for x in log))
        fl = gf.spacing_check(["만전을 기해주시기바랍니다.", "일금칠백일십팔만일천팔백원정"])
        self.assertEqual(len(fl), 1)
        self.assertEqual(fl[0]["분류"], "띄어쓰기 확인")


if __name__ == "__main__":
    unittest.main(verbosity=1)
