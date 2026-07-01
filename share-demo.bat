@echo off
title PNB Sahayak - PUBLIC LINK (keep this window open)
cd /d "C:\Users\Dhwani Bansal\Desktop\PnB Assistant"

echo Preparing... (freeing the port in case the app is already running)
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

echo Starting the app (it runs minimized in the taskbar - you can ignore it)...
start /min "PNB Sahayak APP" cmd /k py src\app.py

echo Waiting a few seconds for the app to start...
timeout /t 9 /nobreak >nul

echo.
echo ================================================================
echo    YOUR PUBLIC LINK WILL APPEAR JUST BELOW IN A FEW SECONDS.
echo.
echo    Look for a line like:   https://xxxx-xxxx.trycloudflare.com
echo    Copy that whole line and send it to the Sarvam team.
echo.
echo    KEEP THIS WINDOW OPEN the whole time they are using it.
echo    To stop sharing: just close this window.
echo ================================================================
echo.

"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:8000

echo.
echo The link has stopped. You can close this window now.
pause
