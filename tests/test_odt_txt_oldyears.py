# -*- coding: utf-8 -*-
"""2026-11-10 고친 두 가지 시험(합성 자료만).
1) odt는 결과로 내지 않고 띄어쓰기를 살린 txt만 만든다(공문 본문 → 업무관리시스템 붙여넣기 글, 그 밖의 odt → _본문.txt).
2) 2022·2023·2024학년도 같은 옛 문서도 대상 학년도(여기서는 2026학년도) 안으로 옮긴다.
사용: py -3 -m unittest discover -s tests"""
import os, sys, io, glob, shutil, zipfile, tempfile, unittest, contextlib, warnings, datetime as dt, json

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "bsv-gongmun-year-update", "tools")
sys.path.insert(0, TOOL)
HOL = os.path.join(TOOL, "holidays")          # 공식 자료로 확인한 2026·2027 공휴일(대체공휴일 포함)
warnings.simplefilter("ignore", ResourceWarning)
import dateconv as dc
import make_paste
import convert
from openpyxl import Workbook, load_workbook

NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
      'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
      'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
      'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
      'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
      'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"')
LIST_STYLES = ('<office:automatic-styles>'
               '<text:list-style style:name="L1">'
               + "".join(f'<text:list-level-style-number text:level="{k}" style:num-format="1" style:num-suffix="."/>' for k in range(1, 7))
               + '</text:list-style>'
               '<text:list-style style:name="L2"><text:list-level-style-bullet text:level="1" text:bullet-char="•"/></text:list-style>'
               '</office:automatic-styles>')


def zbytes(members):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in members.items():
            z.writestr(n, d)
    return b.getvalue()


def odt(body_xml):
    content = (f'<?xml version="1.0" encoding="UTF-8"?><office:document-content {NS}>{LIST_STYLES}'
               f'<office:body><office:text>{body_xml}</office:text></office:body></office:document-content>')
    manifest = ('<?xml version="1.0" encoding="UTF-8"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">'
                '<manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/>'
                '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/></manifest:manifest>')
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:   # mimetype 먼저, 압축 없이(LibreOffice가 여는 odt)
        z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.text", compress_type=zipfile.ZIP_STORED)
        z.writestr("content.xml", content, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("META-INF/manifest.xml", manifest, compress_type=zipfile.ZIP_DEFLATED)
    return b.getvalue()


def P(x):
    return f"<text:p>{x}</text:p>"


def LI(x, sub=""):
    return f"<text:list-item>{P(x)}{sub}</text:list-item>"


def LIST(items, style=None):
    st = f' text:style-name="{style}"' if style else ""
    return f"<text:list{st}>{''.join(items)}</text:list>"


S = lambda n=1: '<text:s/>' if n == 1 else f'<text:s text:c="{n}"/>'
TAB, BR = "<text:tab/>", "<text:line-break/>"


def second_friday(y, m):
    d = dt.date(y, m, 1)
    return 1 + (4 - d.weekday()) % 7 + 7


def gongmun_odt(year, extra_items=""):
    """공문 본문 모양 odt(제목·수신·시행 줄, 자동 번호 목록, 여러 칸 빈칸·탭·줄바꿈, 붙임 두 개)."""
    y, y1 = year, year + 1
    may, jan = second_friday(y, 5), second_friday(y1, 1)     # 5월·1월 둘째 금요일 → 2026. 5. 8. / 2027. 1. 8.
    nested = LIST([LI(f"일시:{S()}{y}. 5. {may}.(금){TAB}09:00~15:00"),
                   LI("장소: 체험관", LIST([LI(f"집결{S(3)}장소: 운동장")]))])
    body = LIST([LI(f"관련: 가나교육지원청-1234({y}. 2. 20.)"),
                 LI(f"{y}학년도 체험학습을{S(2)}다음과 같이 운영합니다.", nested),
                 LI(f"안전 교육을 실시하여 주시기 바랍니다.{BR}가. 대상: 전교생{BR}나. 방법: 강당 집합"),
                 LI(f"K-{BR}에듀파인 품의는 {y1}. 1. {jan}.(금)까지 합니다.") + extra_items], "L1")
    return odt(P("가나중학교") + P("수신") + P("내부결재") + P("제목") + P(f"{y}학년도 체험학습 운영 계획") + body
               + P(f"붙임{S()}1. 운영 계획서 1부.{BR}2. 참가 명단 1부.{S()}끝.") + P("시행") + P("가나중학교-5678"))


def plain_odt():
    """공문 본문 모양이 아닌 odt(협의록): 빈칸·탭·빈 문단·글머리표·표."""
    tbl = ('<table:table><table:table-row><table:table-cell>' + P("구분") + '</table:table-cell><table:table-cell>'
           + P("내용") + '</table:table-cell></table:table-row><table:table-row><table:table-cell>' + P("일시")
           + '</table:table-cell><table:table-cell>' + P("2023. 4. 7.(금)") + '</table:table-cell></table:table-row></table:table>')
    return odt(P("2023학년도 1학년부 협의록") + P("") + P(f"참석:{S(2)}담임{TAB}6명") + P(f"{S(4)}안건 1{S()}/{S()}안건 2")
               + LIST([LI("수행평가 일정"), LI("체험학습")], "L2") + tbl)


EXPECTED_PLAIN = ("2023학년도 1학년부 협의록\n"
                  "\n"
                  "참석:  담임\t6명\n"
                  "    안건 1 / 안건 2\n"
                  "• 수행평가 일정\n"
                  "• 체험학습\n"
                  "구분\t내용\n"
                  "일시\t2023. 4. 7.(금)")


class OdtSpacing(unittest.TestCase):
    """odt 글 읽기: text:s(c개), 탭, 줄바꿈, 자동 번호 목록."""

    def test_parse_spacing_and_numbering(self):
        log = []
        t, body, att = make_paste.parse(gongmun_odt(2023), log)
        self.assertEqual(t, "2023학년도 체험학습 운영 계획")
        lines = [s for s, _ in body]
        self.assertEqual(lines[0], "1. 관련: 가나교육지원청-1234(2023. 2. 20.)")
        self.assertEqual(lines[1], "2. 2023학년도 체험학습을  다음과 같이 운영합니다.")   # text:c="2" → 빈칸 두 개
        self.assertEqual(lines[2], "  가. 일시: 2023. 5. 12.(금)\t09:00~15:00")         # 탭은 탭 문자
        self.assertEqual(lines[3], "  나. 장소: 체험관")
        self.assertEqual(lines[4], "    1) 집결   장소: 운동장")                          # text:c="3" → 빈칸 세 개
        self.assertEqual(lines[5], "3. 안전 교육을 실시하여 주시기 바랍니다.")
        self.assertEqual(lines[6], "  가. 대상: 전교생")      # 줄바꿈 뒤 새 항목은 줄을 바꿈(전에는 앞 줄에 이어 붙었음)
        self.assertEqual(lines[7], "  나. 방법: 강당 집합")
        self.assertEqual(lines[8], "4. K-에듀파인 품의는 2024. 1. 12.(금)까지 합니다.")   # 붙임표로 나뉜 낱말은 붙여 씀
        self.assertEqual(att, ["붙임 1. 운영 계획서 1부.", "2. 참가 명단 1부. 끝."])

    def test_soft_wrap_and_range(self):
        def one(x):
            root = make_paste.etree.fromstring(f'<text:p {NS}>{x}</text:p>')
            return make_paste.odt_ptext(root)
        self.assertEqual(one(f"수련활동 안내 {BR}및 안전교육"), "수련활동 안내 및 안전교육")
        self.assertEqual(one(f"숙소 화재 예방교육,{BR}숙소 안전교육"), "숙소 화재 예방교육, 숙소 안전교육")
        self.assertEqual(one(f"09:10{BR}-09:40"), "09:10-09:40")
        self.assertEqual(one(f"신청합니다.{BR}붙임 1부."), "신청합니다.\n붙임 1부.")
        self.assertEqual(one(f"가{S(5)}나{TAB}{TAB}다"), "가     나\t\t다")

    def test_plain_text_exact(self):
        self.assertEqual("\n".join(make_paste.plain_text(plain_odt())), EXPECTED_PLAIN)

    def test_item_labels(self):
        self.assertEqual([make_paste.item_label(d, 1) for d in range(1, 9)], ["1.", "가.", "1)", "가)", "(1)", "(가)", "①", "㉮"])
        self.assertEqual(make_paste.item_label(2, 14), "하.")
        self.assertEqual(make_paste.item_label(2, 15), "거.")


def run_convert(inputs, run_date="2026-11-10"):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        rc = convert.main(["--input", *inputs, "--holiday-dir", HOL, "--run-date", run_date, "--no-verify", "--quiet"])
    return rc, out.getvalue()


def outputs(res):
    return [x for x in glob.glob(os.path.join(res, "**", "*"), recursive=True)
            if os.path.isfile(x) and "_작업기록" not in x]


class OdtToTxtEndToEnd(unittest.TestCase):
    """odt 하나, odt만 있는 폴더를 넣으면 txt만 나오고 odt는 나오지 않는다."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="gongmun_odt_")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_single_odt_file(self):
        src = os.path.join(self.root, "2023학년도 체험학습 운영 계획(공문 본문).odt")
        open(src, "wb").write(gongmun_odt(2023))
        rc, out = run_convert([src])
        self.assertEqual(rc, 0, out)
        res = os.path.join(self.root, "2023학년도 체험학습 운영 계획(공문 본문)_올해버전")
        files = outputs(res)
        self.assertFalse([f for f in files if f.lower().endswith(".odt")], files)
        txt = [f for f in files if f.endswith("_업무관리시스템_붙여넣기.txt")]
        self.assertEqual(len(txt), 1, files)
        self.assertIn("2026학년도", os.path.basename(txt[0]))
        s = open(txt[0], encoding="utf-8-sig").read().replace("\r\n", "\n")
        expected = ("[제목]\n2026학년도 체험학습 운영 계획\n\n[본문]\n"
                    "1. 관련: 가나교육지원청-OOOO(2026. OO. OO.)\n"
                    "2. 2026학년도 체험학습을  다음과 같이 운영합니다.\n"
                    "  가. 일시: 2026. 5. 8.(금)\t09:00~15:00\n"
                    "  나. 장소: 체험관\n"
                    "    1) 집결   장소: 운동장\n"
                    "3. 안전 교육을 실시하여 주시기 바랍니다.\n"
                    "  가. 대상: 전교생\n"
                    "  나. 방법: 강당 집합\n"
                    "4. K-에듀파인 품의는 2027. 1. 8.(금)까지 합니다.\n"
                    "\n"
                    "붙임  1. 운영 계획서 1부.\n"
                    "      2. 참가 명단 1부.  끝.\n"
                    "\n[붙임 목록]\n운영 계획서 1부.\n참가 명단 1부.\n")
        self.assertEqual(s, expected)
        # 검토표에도 odt가 결과로 나오지 않는다
        wb = load_workbook(os.path.join(res, "검토표.xlsx"))
        ws = wb.worksheets[1]
        outs = [str(r[3].value or "") for r in ws.iter_rows(min_row=2)]
        self.assertTrue(outs and all(".odt" not in o for o in outs), outs)

    def test_folder_with_only_odt(self):
        d = os.path.join(self.root, "작년공문")
        os.makedirs(os.path.join(d, "1. 체험학습"))
        os.makedirs(os.path.join(d, "2. 협의회"))
        open(os.path.join(d, "1. 체험학습", "체험학습 운영 계획(공문 본문).odt"), "wb").write(gongmun_odt(2023))
        open(os.path.join(d, "2. 협의회", "1학년부 협의록.odt"), "wb").write(plain_odt())
        rc, out = run_convert([d])
        self.assertEqual(rc, 0, out)
        files = outputs(os.path.join(self.root, "작년공문_올해버전"))
        self.assertFalse([f for f in files if f.lower().endswith(".odt")], files)
        paste = [f for f in files if f.endswith("_업무관리시스템_붙여넣기.txt")]
        plain = [f for f in files if f.endswith("협의록_본문.txt")]
        self.assertEqual((len(paste), len(plain)), (1, 1), files)
        s = open(plain[0], encoding="utf-8-sig").read().replace("\r\n", "\n")
        # 협의록 날짜만 옮기고(2023. 4. 7.(금) → 2026. 4. 3.(금)), 빈칸·탭·빈 줄은 그대로
        exp = EXPECTED_PLAIN.replace("2023학년도", "2026학년도").replace("2023. 4. 7.(금)", "2026. 4. 3.(금)") + "\n"
        self.assertEqual(s, exp)


class OldYears(unittest.TestCase):
    """2022·2023·2024학년도 문서 날짜를 2026학년도 안으로(3~12월 → 2026년, 1~2월 → 2027년), 같은 주·같은 요일, 공휴일 피함."""

    @classmethod
    def setUpClass(cls):
        dc.configure(2026, holiday_dir=HOL)

    def conv(self, s, sy):
        return dc.convert(s, base_sy=sy, years=2026 - sy)[0]

    def test_2022(self):
        self.assertEqual(self.conv("2022. 3. 7.(월) 입학식", 2022), "2026. 3. 3.(화) 입학식")      # 3. 2. 대체공휴일 → 3. 3.
        self.assertEqual(self.conv("2022. 7. 15.(금)", 2022), "2026. 7. 16.(목)")                # 7. 17. 제헌절 → 7. 16.
        self.assertEqual(self.conv("2023. 1. 13.(금)", 2022), "2027. 1. 8.(금)")
        self.assertEqual(self.conv("2022학년도 운영 계획", 2022), "2026학년도 운영 계획")
        self.assertEqual(self.conv("10월 7일(금)", 2022), "10월 2일(금)")

    def test_2023(self):
        self.assertEqual(self.conv("2023. 9. 27.(수)", 2023), "2026. 9. 23.(수)")
        self.assertEqual(self.conv("2024. 2. 16.(금)", 2023), "2027. 2. 19.(금)")
        self.assertEqual(self.conv("2023년 5월 1일(월)", 2023), "2026년 5월 4일(월)")
        self.assertEqual(self.conv("'23학년도", 2023), "'26학년도")

    def test_2024(self):
        self.assertEqual(self.conv("2024. 10. 4.(금)", 2024), "2026. 10. 2.(금)")
        self.assertEqual(self.conv("2024. 7. 19.(금)", 2024), "2026. 7. 16.(목)")
        self.assertEqual(self.conv("2025. 1. 2.(목)", 2024), "2027. 1. 7.(목)")
        self.assertEqual(self.conv("2024학년도", 2024), "2026학년도")

    def test_relate_line(self):
        for sy in (2022, 2023, 2024):
            self.assertEqual(self.conv(f"1. 관련: 가나교육지원청-1234({sy}. 2. 20.)", sy),
                             "1. 관련: 가나교육지원청-OOOO(2026. OO. OO.)")

    def test_curriculum_and_old_history_kept(self):
        self.assertEqual(self.conv("2022 개정 교육과정에 따라", 2024), "2022 개정 교육과정에 따라")
        self.assertEqual(self.conv("2015 개정 교육과정", 2022), "2015 개정 교육과정")
        self.assertEqual(self.conv("2019년 개교", 2025), "2019년 개교")     # 문서보다 많이 앞선 연도는 그대로

    def test_mixed_set_end_to_end(self):
        root = tempfile.mkdtemp(prefix="gongmun_old_")
        try:
            d = os.path.join(root, "옛공문")
            hp = 'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
            sec = (f'<?xml version="1.0" encoding="UTF-8"?><hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" {hp}>'
                   '<hp:p><hp:run><hp:t>2022학년도 협의회 2022. 3. 7.(월)</hp:t></hp:run></hp:p></hs:sec>')
            files = {
                "2022/2022학년도 협의회.hwpx": zbytes({"mimetype": "application/hwp+zip", "Contents/section0.xml": sec}),
                "2023/2023학년도 안내.txt": "2023학년도 안내 2023. 9. 27.(수), 2024. 2. 16.(금)\n".encode("utf-8"),
                "2024/2024학년도 계획(공문 본문).odt": gongmun_odt(2024),
            }
            for rel, b in files.items():
                p = os.path.join(d, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(b)
            wb = Workbook(); ws = wb.active; ws.append(["일자"]); ws.append([dt.datetime(2024, 7, 19)])
            ws["A2"].number_format = "yyyy-mm-dd"
            wb.save(os.path.join(d, "2024", "2024학년도 일정표.xlsx"))
            rc, out = run_convert([d])
            self.assertEqual(rc, 0, out)
            res = os.path.join(root, "옛공문_올해버전")
            outs = outputs(res)
            self.assertFalse([f for f in outs if f.lower().endswith(".odt")], outs)
            names = [os.path.basename(f) for f in outs]
            for n in ("2026학년도 협의회.hwpx", "2026학년도 안내.txt", "2026학년도 일정표.xlsx"):
                self.assertIn(n, names)
            hx = [f for f in outs if f.endswith("협의회.hwpx")][0]
            self.assertIn("2026학년도 협의회 2026. 3. 3.(화)", zipfile.ZipFile(hx).read("Contents/section0.xml").decode("utf-8"))
            tx = [f for f in outs if f.endswith("안내.txt")][0]
            self.assertIn("2026학년도 안내 2026. 9. 23.(수), 2027. 2. 19.(금)", open(tx, encoding="utf-8").read())
            xl = load_workbook([f for f in outs if f.endswith("일정표.xlsx")][0]).active
            self.assertEqual(xl["A2"].value.date(), dt.date(2026, 7, 16))
            pt = open([f for f in outs if f.endswith("_업무관리시스템_붙여넣기.txt")][0], encoding="utf-8-sig").read()
            self.assertIn("2026학년도 체험학습 운영 계획", pt)
            self.assertIn("  가. 일시: 2026. 5. 8.(금)\t09:00~15:00", pt)
            info = json.load(open(os.path.join(res, "_작업기록", "기록", "실행정보.json"), encoding="utf-8"))
            self.assertEqual(info["대상학년도"], 2026)
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=1)
