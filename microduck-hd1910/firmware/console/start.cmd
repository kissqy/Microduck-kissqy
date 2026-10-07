@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 console.py --dashboard --feetech --open
goto finish
:use_python
python console.py --dashboard --feetech --open
:finish
if errorlevel 1 pause
endlocal
