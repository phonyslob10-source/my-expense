@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
set "REQUIREMENTS=%ROOT%\backend\requirements.txt"
set "FRONTEND=%ROOT%\frontend"

cd /d "%ROOT%" || goto :error_root

echo [1/5] Checking Python virtual environment...
if not exist "%PYTHON%" py -3 -m venv "%ROOT%\.venv"
if not exist "%PYTHON%" python -m venv "%ROOT%\.venv"
if not exist "%PYTHON%" goto :error_venv
"%PYTHON%" --version || goto :error_venv

echo [2/5] Installing backend dependencies...
"%PYTHON%" -m pip install -r "%REQUIREMENTS%"
if errorlevel 1 goto :error_backend

echo [3/5] Checking Node.js and npm...
where npm >nul 2>&1
if errorlevel 1 goto :error_npm
call npm --version
if errorlevel 1 goto :error_npm

cd /d "%FRONTEND%" || goto :error_frontend_dir
echo [4/5] Installing frontend dependencies...
call npm install
if errorlevel 1 goto :error_npm_install

echo [5/5] Building frontend...
call npm run build
if errorlevel 1 goto :error_build
if not exist "%FRONTEND%\dist\index.html" goto :error_dist

cd /d "%ROOT%"
echo.
echo ========================================
echo Install and build completed successfully.
echo Frontend build: %FRONTEND%\dist\index.html
echo Next: run scripts\start.bat
echo ========================================
echo.
pause
exit /b 0

:error_root
echo [ERROR] Cannot access project directory.
pause
exit /b 1

:error_venv
echo [ERROR] Python virtual environment could not be created.
pause
exit /b 1

:error_backend
echo [ERROR] Backend dependency installation failed.
pause
exit /b 1

:error_npm
echo [ERROR] npm is not available or returned an error.
pause
exit /b 1

:error_frontend_dir
echo [ERROR] Frontend directory not found.
pause
exit /b 1

:error_npm_install
echo [ERROR] npm install failed.
pause
exit /b 1

:error_build
echo [ERROR] npm run build failed.
pause
exit /b 1

:error_dist
echo [ERROR] Build reported success, but frontend\dist\index.html is missing.
pause
exit /b 1
