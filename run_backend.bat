@echo off
cd /d "%~dp0backend"
echo ==============================================
echo   HE THONG GIAM SAT CAMERA DAHUA - BACKEND
echo ==============================================
echo Dang khoi dong FastAPI Server tai http://localhost:8000 ...
.\venv\Scripts\uvicorn main:app --reload --host 127.0.0.1 --port 8000
pause
