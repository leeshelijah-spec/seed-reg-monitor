@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if exist "%PYTHON_EXE%" goto run

where python >nul 2>&1
if %errorlevel% equ 0 (
  set "PYTHON_EXE=python"
  goto run
)

echo Python executable not found.
echo Create .venv or install Python, then run ".\wrapup.sh" or ".\wrapup.cmd" again.
exit /b 1

:run
"%PYTHON_EXE%" "%~dp0scripts\wrapup.py" %*
endlocal
