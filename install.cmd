@echo off
rem bsv-gongmun-year-update installer for Windows cmd.
rem Usage: curl -fsSL https://raw.githubusercontent.com/rheps/bsv-gongmun-year-update/main/install.cmd -o install.cmd && .\install.cmd && del install.cmd
setlocal EnableExtensions
for /f "tokens=2 delims=:." %%A in ('chcp') do set "BSV_OLDCP=%%A"
chcp 65001 >nul
set "BSV_REPO=rheps/bsv-gongmun-year-update"
set "BSV_BRANCH=main"
if defined BSV_GONGMUN_BRANCH set "BSV_BRANCH=%BSV_GONGMUN_BRANCH%"

rem 1. Find Python 3.10 or later: py launcher, python on PATH, or a per-user install.
set "BSV_PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 set "BSV_PY=py -3"
if defined BSV_PY goto have_py
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 set "BSV_PY=python"
if defined BSV_PY goto have_py
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "BSV_PY="%%D\python.exe""
if defined BSV_PY goto have_py
echo.
echo Python을 찾지 못했습니다. 아래 명령으로 설치한 뒤, 새 cmd 창을 열고 설치 명령을 다시 실행하세요.
echo   winget install Python.Python.3.14
set "BSV_RC=1"
goto end

:have_py
rem 2. Download the repository into a temporary folder (git if present, else zip via curl).
set "BSV_TMP=%TEMP%\bsv-gongmun-install-%RANDOM%%RANDOM%"
mkdir "%BSV_TMP%" >nul 2>&1
where git >nul 2>&1
if errorlevel 1 goto zip
git clone --quiet --depth 1 --branch %BSV_BRANCH% https://github.com/%BSV_REPO%.git "%BSV_TMP%\src" >nul 2>&1
if exist "%BSV_TMP%\src\install.py" goto run
:zip
curl -fsSL -o "%BSV_TMP%\src.zip" "https://github.com/%BSV_REPO%/archive/refs/heads/%BSV_BRANCH%.zip"
if errorlevel 1 goto fail_download
set "BSV_TAR=tar"
if exist "%SystemRoot%\System32\tar.exe" set "BSV_TAR=%SystemRoot%\System32\tar.exe"
"%BSV_TAR%" -xf "%BSV_TMP%\src.zip" -C "%BSV_TMP%"
if errorlevel 1 goto fail_download
for /d %%D in ("%BSV_TMP%\bsv-gongmun-year-update-*") do move "%%D" "%BSV_TMP%\src" >nul
if exist "%BSV_TMP%\src\install.py" goto run
:fail_download
echo.
echo 스킬을 내려받지 못했습니다. 인터넷 연결을 확인한 뒤 다시 시도하세요.
set "BSV_RC=1"
goto cleanup

:run
rem 3. Install packages and copy the skill (messages come from install_messages.json).
%BSV_PY% -E "%BSV_TMP%\src\install.py"
set "BSV_RC=%ERRORLEVEL%"

:cleanup
rmdir /s /q "%BSV_TMP%" >nul 2>&1

:end
if defined BSV_OLDCP chcp %BSV_OLDCP% >nul
endlocal & exit /b %BSV_RC%
