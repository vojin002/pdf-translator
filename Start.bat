@echo off
title PDF Translator
chcp 65001 >nul
echo.
echo  ============================================
echo    PDF Translator
echo  ============================================
echo.

:: ---- Python already installed? ----
python --version >nul 2>&1
if not errorlevel 1 goto :launch

echo  Python is not installed. Starting automatic installation...
echo.

:: ---- Try winget (Windows 10 May 2020+ and Windows 11) ----
winget --version >nul 2>&1
if not errorlevel 1 (
    echo  [1/2] Installing Python via winget...
    winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 goto :download
    echo  [2/2] Starting application...
    goto :launch_refresh
)

:: ---- Fallback: download Python installer ----
:download
echo  [1/3] Downloading Python installer...
powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe' -OutFile '%TEMP%\python_setup.exe' -UseBasicParsing" 2>nul

if not exist "%TEMP%\python_setup.exe" (
    echo.
    echo  [ERROR] Could not download Python automatically.
    echo.
    echo  Please install manually:
    echo    1. Go to https://www.python.org/downloads/
    echo    2. Download and install Python
    echo    3. Check "Add Python to PATH"
    echo    4. Run Start.bat again
    echo.
    pause
    exit /b 1
)

echo  [2/3] Installing Python (this may take a few minutes)...
"%TEMP%\python_setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1
del "%TEMP%\python_setup.exe" 2>nul

echo  [3/3] Starting application...

:: ---- Launch with refreshed PATH (after new install) ----
:launch_refresh
powershell -Command "$env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path','User'); Start-Process pythonw -ArgumentList 'Run.pyw' -WorkingDirectory '%~dp0'"
exit /b

:: ---- Normal launch ----
:launch
start "" pythonw Run.pyw
exit /b
