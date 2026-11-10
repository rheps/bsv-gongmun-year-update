# Install instructions for AI coding agents

You are an AI coding agent (Claude Code, Codex or Antigravity) on Windows. The user asked you to install this skill from `https://github.com/rheps/bsv-gongmun-year-update`, or to fetch its example 공문. Follow these steps. Do not change any other skill, and do not send the user's files anywhere. `git` is not needed.

## A. Install the skill

1. Download and extract the repository into a new empty temporary folder:
   ```
   mkdir "%TEMP%\bsv-gongmun-src"
   curl -fsSL --retry 3 -L -o "%TEMP%\bsv-gongmun-src\repo.zip" https://api.github.com/repos/rheps/bsv-gongmun-year-update/zipball/main
   "%SystemRoot%\System32\tar.exe" -xf "%TEMP%\bsv-gongmun-src\repo.zip" -C "%TEMP%\bsv-gongmun-src"
   ```
   Use Windows `tar.exe` as shown (in Git Bash: `/c/Windows/System32/tar.exe`); the GNU `tar` of Git Bash cannot read zip files. The zip holds one folder `rheps-bsv-gongmun-year-update-<commit>`. Inside it, the folder `bsv-gongmun-year-update` is the skill.
2. Copy that skill folder into the skill folder of each agent. The home folder is `%USERPROFILE%` (in PowerShell `$env:USERPROFILE`, in Python `os.path.expanduser("~")`); use that value, not a path you guess:
   - Claude Code: `%USERPROFILE%\.claude\skills\bsv-gongmun-year-update`
   - Codex: `%USERPROFILE%\.codex\skills\bsv-gongmun-year-update`
   - Antigravity: `%USERPROFILE%\.gemini\config\skills\bsv-gongmun-year-update`

   Install into all three. If a folder `bsv-gongmun-year-update` is already there, it is an older copy of this skill: replace it with the new one.
3. Install the Python packages with the user's Python 3.10 or later, from the extracted folder: `py -3 -m pip install -r requirements.txt` (if `py` is missing, use `python -m pip ...`). kiwipiepy is optional; if only it fails, continue. If no Python 3.10+ exists, ask the user to run `winget install Python.Python.3.14` and stop.
4. Check: `py -3 -E "%USERPROFILE%\.claude\skills\bsv-gongmun-year-update\tools\gongmun.py" check` prints the Python version and whether 한글 and LibreOffice are found.
5. Delete the temporary folder.
6. Tell the user, in Korean:
   > 설치를 마쳤습니다. 공문이 있는 폴더에서 Claude Code, Codex 또는 Antigravity를 열고 이렇게 요청하세요: 작년공문 폴더를 올해 공문으로 바꿔 줘
   >
   > CLI가 이미 열려 있었다면 닫았다가 다시 열어야 새 스킬을 찾습니다.

   If `check` says 한글 is missing, also say that 한글 2020 or later is needed for hwp files.
7. Restart: an agent lists skills when it starts. Tested with Claude Code 2.1.319: a skill installed during a session is not in that session's skill list; it appears after Claude Code is closed and opened again. If the user wants to use it in the same session anyway, read `%USERPROFILE%\.claude\skills\bsv-gongmun-year-update\SKILL.md` (or the Codex / Antigravity copy) and follow it exactly; that works without a restart.

The repository also has `install.py` (`py -3 install.py` in the extracted folder), which does steps 2 and 3 in one go. You may use it instead.

## B. Fetch the example 공문

When the user asks for the example (or gives the link `https://api.github.com/repos/rheps/bsv-gongmun-year-update/contents/examples/sample-gongmun.zip`), run in the current folder:
```
curl -fsSL --retry 3 -H "Accept: application/vnd.github.raw" -o sample-gongmun.zip https://api.github.com/repos/rheps/bsv-gongmun-year-update/contents/examples/sample-gongmun.zip
"%SystemRoot%\System32\tar.exe" -xf sample-gongmun.zip
del sample-gongmun.zip
```
This makes the folder `작년공문`. The example is made-up 공문 with deliberate typos. Then the user can ask: 작년공문 폴더를 올해 공문으로 바꿔 줘
