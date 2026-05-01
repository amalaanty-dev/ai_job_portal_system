@echo off
REM Zecpath ATS API — Windows dev runner
cd /d "%~dp0\.."
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
