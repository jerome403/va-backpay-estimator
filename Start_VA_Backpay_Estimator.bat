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
start "" "http://127.0.0.1:5001"
python app.py
pause
