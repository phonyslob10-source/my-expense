@echo off
setlocal
cd /d "%~dp0.."
echo [1/3] Checking Tailscale...
where tailscale >nul 2>&1
if errorlevel 1 (
  echo Tailscale was not found.
  echo Install Tailscale for Windows first, then run this script again.
  echo https://tailscale.com/download/windows
  pause
  exit /b 1
)
echo [2/3] Checking the local app...
powershell -NoProfile -Command "$r=try{Invoke-WebRequest -UseBasicParsing http://127.0.0.1:3000/api/health -TimeoutSec 3}catch{$null}; if($null -eq $r){exit 1}"
if errorlevel 1 (
  echo The app is not running on http://127.0.0.1:3000
  echo Start scripts\start.bat first.
  pause
  exit /b 1
)
echo [3/3] Enabling private HTTPS access through Tailscale Serve...
tailscale serve 3000
echo.
echo Tailscale Serve is configured.
echo Keep Tailscale connected on both Windows and iPhone.
pause
