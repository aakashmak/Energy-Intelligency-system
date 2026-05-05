@echo off
echo Starting OilPulse React Stack...

echo.
echo [1/2] Starting FastAPI backend on port 8000...
start "OilPulse API" cmd /k "cd /d %~dp0 && uvicorn api.main:app --reload --port 8000 --host 0.0.0.0"

timeout /t 3 /nobreak >nul

echo [2/2] Starting React frontend on port 5173...
start "OilPulse Frontend" cmd /k "cd /d %~dp0\frontend && npm run dev"

echo.
echo Dashboard: http://localhost:5173
echo API Docs:  http://localhost:8000/docs
echo.
pause
