@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo [1/5] Checking Tailscale CLI...
where tailscale >nul 2>&1
if errorlevel 1 (
  echo Tailscale was not found.
  echo Install Tailscale for Windows first, then run this script again.
  pause
  exit /b 1
)

echo [2/5] Checking Tailscale Windows service...
sc query Tailscale | findstr /I "RUNNING" >nul 2>&1
if errorlevel 1 (
  echo Tailscale service is not running. Starting it...
  net start Tailscale
  if errorlevel 1 (
    echo [ERROR] Failed to start the Tailscale service.
    pause
    exit /b 1
  )
  timeout /t 5 /nobreak >nul
) else (
  echo Tailscale service is already running.
)

echo [3/5] Checking Tailscale connection...
tailscale status >nul 2>&1
if errorlevel 1 (
  echo Tailscale is not connected. Restarting the Windows service...
  net stop Tailscale >nul 2>&1
  timeout /t 2 /nobreak >nul
  net start Tailscale
  if errorlevel 1 (
    echo [ERROR] Failed to restart the Tailscale service.
    pause
    exit /b 1
  )
  timeout /t 8 /nobreak >nul
)

echo Tailscale status:
tailscale status
if errorlevel 1 (
  echo [ERROR] Tailscale is still offline.
  echo Check Tailscale and the proxy at 127.0.0.1:7897.
  pause
  exit /b 1
)

echo [4/5] Checking the local app...
powershell -NoProfile -Command "$r=try{Invoke-WebRequest -UseBasicParsing http://127.0.0.1:3000/api/health -TimeoutSec 3}catch{$null}; if($null -eq $r){exit 1}"
if errorlevel 1 (
  echo The app is not running on http://127.0.0.1:3000
  echo Start scripts\start.bat first.
  pause
  exit /b 1
)

echo [5/5] Configuring persistent Tailscale Serve...
tailscale serve --bg 3000
if errorlevel 1 (
  echo [ERROR] Failed to configure Tailscale Serve.
  pause
  exit /b 1
)

echo.
echo ========================================
echo Remote access is ready.
echo Tailscale is connected and Serve runs in the background.
echo ========================================
echo.
tailscale serve status
pause
