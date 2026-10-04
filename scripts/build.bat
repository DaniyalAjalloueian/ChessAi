@echo off
setlocal

echo ============================================
echo   Local Chess AI - Building Windows EXE
echo ============================================
echo.

cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] The virtual environment was not found.
    echo         Run scripts\install.bat first.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Could not activate the virtual environment.
    pause
    exit /b 1
)

echo [1/2] Installing PyInstaller...
python -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo [ERROR] Could not install PyInstaller.
    pause
    exit /b 1
)

echo [2/2] Building executable...
python -m PyInstaller --noconfirm --clean LocalChessAI.spec
if errorlevel 1 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build complete!
echo   Output: dist\LocalChessAI\LocalChessAI.exe
echo.
echo   Remember to place stockfish.exe inside
echo   dist\LocalChessAI\engine\bin\  or select
echo   it from the Settings page.
echo ============================================
echo.
pause
endlocal