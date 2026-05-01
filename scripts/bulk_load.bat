@echo off
REM Bulk-load resumes + JDs into the running ATS API.
REM Pass through any args, e.g. scripts\bulk_load.bat --reset --threshold 60
cd /d "%~dp0\.."
python scripts\bulk_load.py %*
