@echo off
setlocal EnableDelayedExpansion

echo ============================================
echo   Local Chess AI - Installation
echo ============================================
echo.

cd /d "%~dp0.."

REM ---------------------------------------------------------------
REM  Locate a usable Python 3.11+ interpreter.
REM  Priority:
REM    1) py -3.11   (launcher, exact version)
REM    2) py -3      (launcher, newest Python 3)
REM    3) python     (from PATH)
REM  For each candidate we verify that it reports a version >= 3.11.
REM ---------------------------------------------------------------
set "PY_CMD="

call :try_python "py -3.11"
if defined PY_CMD goto :python_found

call :try_python "py -3"
if defined PY_CMD goto :python_found

call :try_python "python"
if defined PY_CMD goto :python_found

echo [ERROR] No suitable Python 3.11+ interpreter was found.
echo.
echo   Detected Python launcher environments (if any):
py -0p 2>nul
echo.
echo   To fix this, do ONE of the following:
echo.
echo     * Install Python 3.11 or newer from
echo         https://www.python.org/downloads/windows/
echo       During setup, tick "Add python.exe to PATH".
echo.
echo     * Or if Python is already installed but not on PATH, open a new
echo       terminal and confirm with:   py -3 --version
echo.
echo     * Or set the environment variable PYLAUNCHER_ALLOW_INSTALL=1 and
echo       re-run this script so the launcher may install a matching
echo       runtime through winget.
echo.
pause
exit /b 1

:python_found
echo Using interpreter: !PY_CMD!
for /f "delims=" %%v in ('!PY_CMD! --version 2^>^&1') do echo   %%v
echo.

echo [1/3] Creating virtual environment...
if exist ".venv\Scripts\python.exe" (
    echo       .venv already exists, skipping creation.
) else (
    !PY_CMD! -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        pause
        exit /b 1
    )
)

echo [2/3] Activating virtual environment...
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Could not activate the virtual environment.
    pause
    exit /b 1
)

echo [3/3] Installing dependencies...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip.
    pause
    exit /b 1
)
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Installation completed successfully.
echo.
echo   Next steps:
echo     1. Download Stockfish from
echo        https://stockfishchess.org/download/
echo     2. Either place stockfish.exe inside
echo        engine\bin\  or  select it from the
echo        Settings page inside the application.
echo     3. Run  scripts\run.bat
echo ============================================
echo.
pause
endlocal
exit /b 0

REM ---------------------------------------------------------------
REM  :try_python "<command>"
REM  Runs the given command with "--version" and checks that the
REM  reported version is 3.11 or newer. On success, sets PY_CMD.
REM ---------------------------------------------------------------
:try_python
set "CANDIDATE=%~1"
set "PY_CMD="
for /f "tokens=2" %%V in ('%CANDIDATE% --version 2^>^&1') do set "VER=%%V"
if not defined VER goto :eof
for /f "tokens=1,2 delims=." %%A in ("!VER!") do (
    set "MAJOR=%%A"
    set "MINOR=%%B"
)
if not defined MAJOR goto :eof
if not defined MINOR goto :eof
if !MAJOR! LSS 3 goto :eof
if !MAJOR! EQU 3 if !MINOR! LSS 11 goto :eof
set "PY_CMD=%CANDIDATE%"
goto :eof