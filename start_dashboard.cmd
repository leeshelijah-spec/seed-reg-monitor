@echo off
setlocal
cd /d "%~dp0"
set "GIT_BASH=%ProgramFiles%\Git\bin\bash.exe"
if not exist "%GIT_BASH%" (
  echo Git Bash not found at "%GIT_BASH%".
  echo Install Git for Windows or run ".\start_dashboard.sh" from Git Bash directly.
  exit /b 1
)
"%GIT_BASH%" -lc "cd /c/PJT/seed-reg-monitor && ./start_dashboard.sh %*"
endlocal
