@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 goto folder_error
set "PYTHONUTF8=1"

where py >nul 2>nul
if errorlevel 1 goto try_python
py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>nul
if errorlevel 1 goto try_python
py -3 training_console.py --open
goto finish

:try_python
where python >nul 2>nul
if errorlevel 1 goto no_python
python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>nul
if errorlevel 1 goto no_python
python training_console.py --open
goto finish

:no_python
echo Python 3.10 or newer is required.
echo Install it from https://www.python.org/downloads/windows/
echo Select "Add Python to PATH" during installation.
goto finish

:folder_error
echo Cannot open the application folder. Extract the entire ZIP to a local folder.

:finish
echo.
pause
endlocal
