# Install instructions for AI coding agents

You are an AI coding agent (Claude Code, Codex or Antigravity) on Windows. The user asked you to install this skill from `https://github.com/rheps/bsv-gongmun-year-update`, or to fetch its example 공문. Follow these steps exactly. Do not write your own installer, do not change any other skill, and do not send the user's files anywhere.

## A. Install the skill

Run these in the shell you already have (cmd syntax shown; in PowerShell or Git Bash use the same commands with that shell's variable syntax). `git` is not needed.

1. Download and extract the repository into a new temporary folder:
   ```
   mkdir "%TEMP%\bsv-gongmun-src"
   curl -fsSL --retry 3 -L -o "%TEMP%\bsv-gongmun-src\repo.zip" https://api.github.com/repos/rheps/bsv-gongmun-year-update/zipball/main
   tar -xf "%TEMP%\bsv-gongmun-src\repo.zip" -C "%TEMP%\bsv-gongmun-src"
   ```
   The zip holds one folder named `rheps-bsv-gongmun-year-update-<commit>`.
2. Run the installer that is in that folder with the user's Python (3.10 or later): `py -3 install.py` (if `py` is missing, use `python install.py`). Run it from inside the extracted folder. It:
   - runs `pip install -r requirements.txt` (kiwipiepy is optional; a failure there only prints a note),
   - copies the skill folder `bsv-gongmun-year-update` into all three skill folders:
     - Claude Code: `%USERPROFILE%\.claude\skills\bsv-gongmun-year-update`
     - Codex: `%USERPROFILE%\.codex\skills\bsv-gongmun-year-update`
     - Antigravity: `%USERPROFILE%\.gemini\config\skills\bsv-gongmun-year-update`
   - replaces only its own earlier install; any other folder with that name is moved to `%USERPROFILE%\.bsv-gongmun-year-update\backup\` first, never deleted.
3. If no Python 3.10+ is found, tell the user to run `winget install Python.Python.3.14`, then try again. Do not install Python yourself without asking.
4. Delete `%TEMP%\bsv-gongmun-src`.
5. Tell the user, in Korean, exactly the last lines the installer printed. Its success message is:
   > 설치를 마쳤습니다. 공문이 있는 폴더에서 Claude Code, Codex 또는 Antigravity를 열고 이렇게 요청하세요: 작년공문 폴더를 올해 공문으로 바꿔 줘
6. Restart: if the skill is not offered in this session, tell the user to close and reopen the agent (Claude Code, Codex or Antigravity) once.

Manual fallback (only if `install.py` cannot run): copy the folder `bsv-gongmun-year-update` from the extracted repository to the three paths above, then run `py -3 -m pip install -r requirements.txt` in the extracted folder.

## B. Fetch the example 공문

When the user asks for the example (or gives the link `https://api.github.com/repos/rheps/bsv-gongmun-year-update/contents/examples/sample-gongmun.zip`), run in the current folder:
```
curl -fsSL --retry 3 -H "Accept: application/vnd.github.raw" -o sample-gongmun.zip https://api.github.com/repos/rheps/bsv-gongmun-year-update/contents/examples/sample-gongmun.zip
tar -xf sample-gongmun.zip
del sample-gongmun.zip
```
This makes the folder `작년공문`. The example is made-up 공문 with deliberate typos. Then the user can ask: 작년공문 폴더를 올해 공문으로 바꿔 줘
