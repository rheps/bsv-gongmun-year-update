---
name: bsv-gongmun-year-update
description: Use when a Korean teacher wants last year's (or an older year's) 공문 and attachments turned into this school year's version - 작년 공문 올해 버전, 작년공문 폴더를 올해 공문으로, 공문 날짜 올해로, 인수인계 받은 공문 재사용, hwp를 hwpx로, pdf를 편집 가능하게, 공문 연도 변환 - for a folder, zip or files the teacher names.
---

# 공문 year update (portable)

## Overview
A tested local tool moves earlier-year 공문 bundles into the target school year and writes a review sheet and a before/after page. **Run the tool. Do not write your own converter, re-implement date rules, or hand-edit documents** - hand-made scripts lose formatting, skip the holiday and 관련 rules, and leave no 검토표.

Everything stays on this computer. Never send document contents, file names or 검토표 text to any service (no translation, OCR or AI upload). The only things that read the files are the tool and you.

## Tool
`TOOL` = `tools/gongmun.py` in this skill's folder (installed copies: `%USERPROFILE%\.claude\skills\bsv-gongmun-year-update`, `%USERPROFILE%\.codex\skills\...`, `%USERPROFILE%\.gemini\config\skills\...`). Run it with `py -3 -E "<TOOL>" ...`; if `py` is missing use `python`, or the path in `tools/python_path.txt`. Quote paths: Korean names and spaces are normal. `py -3 -E "<TOOL>" check` shows whether 한글, LibreOffice and kiwipiepy are present.

## Steps
1. **Find the input** the teacher means (folder, zip or files; e.g. `작년공문` in the current folder). Ask only if it is really unclear.
2. **Convert** (about 30 s for 7 files):
   `py -3 -E "<TOOL>" convert --input "<folder|zip|file>" [...]`
   - Target school year = school year of today (Mar-Dec: this year; Jan-Feb: last year). Add `--target-school-year N` only if the teacher names another year.
   - If the teacher says the files are student records, add `--student-data`.
   - It prints `결과 폴더: ...`. Output is a new folder beside the input, `<input>_올해버전` (then `_올해버전2`, ...). Originals are never changed.
   - Older documents (2022, 2023, 2024학년도 ...) also move into the target school year: Mar-Dec dates to the target year, Jan-Feb to the next, same week and weekday, holidays avoided. Only the target year's two holiday files are needed.
   - **odt → txt only.** No odt file is ever output. A 공문 body odt becomes `<name>_업무관리시스템_붙여넣기.txt` (paste-ready: spaces from `text:s`, tabs and line breaks kept; list numbers as 1.→가.→1)→가)→(1)→(가) with 2-space indents; `붙임  1. …`; `  끝.`). Any other odt becomes `<name>_본문.txt`. A student-looking odt gets only its unchanged text as `_본문.txt`. Do not convert odt yourself.
   - Stops (exit 2) when a holiday file is missing or unverified: report the Korean message. Do not edit holiday files or pass `--allow-unverified-holidays` unless the teacher accepts a preview, and then say so.
   - Stops (exit 4) when 한글 is missing: tell the teacher 한글 2020+ is needed.
3. **Proofread (윤문)** - always, unless the teacher says no. Steps 3-6 below.
4. **Capture page**: `py -3 -E "<TOOL>" capture "<결과 폴더>"` makes `전후캡처비교.html` in the result folder (later runs: `전후캡처비교_윤문<N>.html`).
5. **Report** (below). Check that no Hwp.exe or soffice process you started is left running. Never run `Hwp.exe --version`.

## Proofread (윤문)
Fix last year's typos and 비문 without touching content. Edit the Korean directly - no English draft, no translation service. Every entry that passes the guard is applied; colours only say what kind of fix it was: **red** = 오타, 맞춤법, 띄어쓰기, 공문서표기 (and the date changes); **blue** = 문장 다듬음.

1. `py -3 -E "<TOOL>" proofread-prepare "<결과 폴더>"` writes `_작업기록/윤문/본문목록.txt` (`[location] text` per paragraph). Student files, spreadsheets, OCR text and files copied unchanged are skipped by design.
2. Read every listed paragraph and write `_작업기록/윤문/윤문.json`:
   `{"항목": [{"id": "Y001", "file": "<기록id from ===== line>", "location": "<as listed>", "before": "...", "after": "...", "kind": "확정|제안", "category": "...", "reason": "짧은 한국어"}]}`
   - `before` = smallest span that occurs **once** in that paragraph; one fix per entry.
   - `확정` (red): `오타`, `맞춤법` (되/돼, 안/않, -로서/-로써), `띄어쓰기` (`기한내`→`기한 내`, `소독실시`→`소독 실시`, `실시 하오니`→`실시하오니`), `공문서표기` (`12시 40분`→`12:40`, `예방‧관리`→`예방·관리`, `2026. 3. 5.`, two spaces before `끝.`).
   - `제안` (blue, still applied): `비문` (`질서 지도한다`→`질서를 지도한다`), `어색한표현` (`~를 통해`, `~에 있어`, `되어지다`, `-의` chains, `형성이 이루어지다`→`형성하다`).
   - Keep 공문 conventions (`관련:`, `붙임`, `끝.`, `1.→가.→1)→가)`, `위 호와 관련하여`, `~하여 주시기 바랍니다`, 개조식 `~함`), 합쇼체 and facts. Never touch digits, dates, amounts, names, 「」 or quoted text, `OOOO` / `OO. OO.`. A correct sentence gets no entry. If a 비문 needs a new meaning word, write no entry; mention it in the report.
3. `py -3 -E "<TOOL>" proofread-guard "<결과 폴더>"` blocks unsafe entries (changed digits, names, negation, meaning words...). Rewrite a blocked entry or leave it; never weaken the guard or edit files by hand.
4. `py -3 -E "<TOOL>" proofread-apply "<결과 폴더>"` writes `<name>_윤문1<ext>` beside each converted file and `검토표_윤문1.xlsx`. Converted files stay.
5. Then run step 4 above (capture).
6. Only if the teacher disagrees with an entry: `proofread-apply "<결과 폴더>" --revert Y004,Y010` (new 판; `--restore Y004` puts one back), then capture again.

## Report to the teacher (plain Korean, no code)
- Result folder path, 검토표.xlsx, 검토표_윤문1.xlsx, 전후캡처비교 HTML (open it in a browser).
- Counts by result (변환 완료, 원본 유지, 변환 안 함), files copied unchanged and why.
- For each odt input, the txt file made from it (odt files are not made).
- Student-looking files: how many, copied unchanged into `학생자료_변환안함`, not shown on the page.
- 확인할 곳: top categories with counts from the 검토표 「확인할 곳」 sheet (e.g. 날짜 순서 바뀜, 사람 이름일 수 있음, 관련 문서 OOOO to fill in). For `원본 유지(서식 PDF)` list page and old → new dates to fix by hand.
- 윤문: applied count by colour with a few examples, every 문장 다듬음 (id: before → after), blocked entries and why, how to undo (`되돌려 줘` + id).
- What was not checked (e.g. LibreOffice missing, so xls copied unchanged).

## Common mistakes
| Mistake | Instead |
|---|---|
| Writing a Python script to change dates | Run `convert`; it handles holidays, 관련, weekdays |
| Saving results over the originals | The tool writes a new `_올해버전` folder |
| Handing back an odt or converting odt by hand | The tool gives only txt for odt; point the teacher to that txt |
| Marking a sentence fix `확정` | `제안`; it is still applied (blue) |
| Rewriting a whole sentence in one entry | Smallest span, one fix per entry |
| "Fixing" a flagged date/name/number | Leave it; mention it under 확인할 곳 |
| Asking approval before applying passed entries | Apply all that pass; offer `--revert` |
| Uploading text to check spelling | Everything stays local |
