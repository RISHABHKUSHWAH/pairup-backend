@echo off
cd /d "%~dp0"
echo [PairUp] Cleaning up any old process on port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /f /pid %%a >nul 2>&1

echo [PairUp] Starting Django Backend on 0.0.0.0:8000 (accessible from PC and phone)...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" manage.py runserver 0.0.0.0:8000
) else (
    python manage.py runserver 0.0.0.0:8000
)
pause
