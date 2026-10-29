@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%~dp0scripts\launch.py"
  goto finished
)
python -c "import sys" >nul 2>&1
if not errorlevel 1 (
  python "%~dp0scripts\launch.py"
  goto finished
)
py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 (
  py -3 "%~dp0scripts\launch.py"
  goto finished
)
echo Python was not found. Install Python 3.9 or later and restart this launcher.
echo https://www.python.org/downloads/windows/
:finished
echo.
pause
endlocal
