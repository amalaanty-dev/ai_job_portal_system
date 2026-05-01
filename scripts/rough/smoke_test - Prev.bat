@echo off
REM ============================================================
REM Zecpath ATS API — Smoke test (Windows)
REM Exercises full pipeline: JD upload -> resume upload ->
REM parse -> score -> shortlist. Files land in api_data/ and
REM api_data_results/ for inspection.
REM
REM Prereq: server running at http://localhost:8000
REM         a sample resume at .\sample_resume.pdf
REM ============================================================

setlocal EnableDelayedExpansion
set BASE=http://localhost:8000/v1

if not exist sample_resume.pdf (
    echo [!] Place a PDF named sample_resume.pdf in this folder first.
    exit /b 1
)

echo.
echo [1/5] Uploading JD...
curl -s -X POST %BASE%/jd/upload ^
  -H "Content-Type: application/json" ^
  -d "{\"job_title\":\"Backend Developer\",\"required_skills\":[\"Python\",\"Django\"],\"experience_required\":2}" ^
  -o jd_resp.json
type jd_resp.json
echo.

REM Extract job_id (very rough — for real use, parse JSON properly)
for /f "tokens=2 delims=:," %%A in ('findstr "job_id" jd_resp.json') do (
    set JOB_ID=%%~A
    set JOB_ID=!JOB_ID:"=!
    set JOB_ID=!JOB_ID: =!
)
echo Got JOB_ID=!JOB_ID!
echo.

echo [2/5] Uploading resume...
curl -s -X POST %BASE%/resume/upload ^
  -F "file=@sample_resume.pdf" ^
  -F "job_id=!JOB_ID!" ^
  -o resume_resp.json
type resume_resp.json
echo.

for /f "tokens=2 delims=:," %%A in ('findstr "resume_id" resume_resp.json') do (
    set RESUME_ID=%%~A
    set RESUME_ID=!RESUME_ID:"=!
    set RESUME_ID=!RESUME_ID: =!
)
for /f "tokens=2 delims=:," %%A in ('findstr "candidate_id" resume_resp.json') do (
    set CAND_ID=%%~A
    set CAND_ID=!CAND_ID:"=!
    set CAND_ID=!CAND_ID: =!
)
echo Got RESUME_ID=!RESUME_ID!  CAND_ID=!CAND_ID!
echo.

echo [3/5] Parsing resume...
curl -s -X POST %BASE%/resume/parse ^
  -H "Content-Type: application/json" ^
  -d "{\"resume_id\":\"!RESUME_ID!\"}"
echo.

echo [4/5] Scoring candidate...
curl -s -X POST %BASE%/ats/score ^
  -H "Content-Type: application/json" ^
  -d "{\"candidate_id\":\"!CAND_ID!\",\"job_id\":\"!JOB_ID!\"}"
echo.

echo [5/5] Shortlisting...
curl -s -X POST %BASE%/ats/shortlist ^
  -H "Content-Type: application/json" ^
  -d "{\"job_id\":\"!JOB_ID!\",\"threshold\":0}"
echo.

del jd_resp.json resume_resp.json 2>nul

echo.
echo ============================================================
echo Inspect generated files:
echo   api_data\raw_resumes\
echo   api_data\jds\
echo   api_data_results\parsed\
echo   api_data_results\scores\
echo   api_data_results\shortlists\
echo ============================================================

dir /b api_data\raw_resumes 2>nul
dir /b api_data\jds 2>nul
dir /b api_data_results\parsed 2>nul
dir /b api_data_results\scores 2>nul
dir /b api_data_results\shortlists 2>nul

endlocal
