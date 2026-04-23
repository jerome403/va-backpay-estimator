@echo off
title VA Backpay Estimator - Spearman Appeals LLC
color 0B
echo.
echo  ============================================
echo    VA Backpay Estimator - Spearman Appeals LLC
echo  ============================================
echo.
echo  Starting server...
echo  Once running, your browser will open to:
echo.
echo    http://127.0.0.1:5001
echo.
echo  Press Ctrl+C to stop the server.
echo  ============================================
echo.

cd /d "%~dp0"

rem Point to the shared ClientFolders used by va-form-filler.
rem Change this path if your ClientFolders lives somewhere else.
set "CLIENT_FOLDERS_BASE=C:\Users\jerom\OneDrive - Spearman Appeals LLC\VA Client Automation\ClientFolders"

start "" "http://127.0.0.1:5001"
python app.py
pause
