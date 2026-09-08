@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
set "FRONTEND=%ROOT%\frontend"

cd /d "%ROOT%" || goto :error_root
if not exist "%PYTHON%" goto :error_python
if not exist "%FRONTEND%\dist\index.html" goto :error_dist

echo Starting backend server...
echo.
"%PYTHON%" -m uvicorn backend.app.main:app --host 0.0.0.0 --port 3000

if errorlevel 1 goto :error_server
exit /b 0

:error_root
echo [ERROR] Cannot access project directory.
pause
exit /b 1

:error_python
echo [ERROR] Project Python environment not found.
echo Run scripts\install-and-build.bat first.
pause
exit /b 1

:error_dist
echo [ERROR] Frontend build not found.
echo Run scripts\install-and-build.bat first.
pause
exit /b 1

:error_server
echo [ERROR] Backend server stopped with an error.
pause
exit /b 1
