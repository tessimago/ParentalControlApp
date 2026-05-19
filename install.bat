@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: Parental Control App - Installer
:: Must be run as Administrator
:: ============================================================

:: Check for admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] This script must be run as Administrator.
    echo Right-click and select "Run as administrator".
    pause
    exit /b 1
)

echo ============================================================
echo  Parental Control App - Installer
echo ============================================================
echo.

set "PROJECT_DIR=%~dp0"
set "VENV_DIR=%PROJECT_DIR%.venv"
set "SCREENSHOTS_DIR=C:\ProgramData\ParentalControl\.screenshots"
set "PYTHON_INSTALLER_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
set "GIT_INSTALLER_URL=https://github.com/git-for-windows/git/releases/download/v2.44.0.windows.1/Git-2.44.0-64-bit.exe"

:: ---- Step 1: Check Python ----
echo [1/9] Checking for Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Downloading and installing Python 3.11...
    powershell -Command "Invoke-WebRequest -Uri '%PYTHON_INSTALLER_URL%' -OutFile '%TEMP%\python_installer.exe'"
    "%TEMP%\python_installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    del "%TEMP%\python_installer.exe"
    echo Python installed. You may need to restart this script for PATH changes to take effect.
    :: Refresh PATH
    set "PATH=C:\Program Files\Python311;C:\Program Files\Python311\Scripts;%PATH%"
) else (
    echo Python found.
)

:: ---- Step 2: Check Git ----
echo [2/9] Checking for Git...
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Git not found. Downloading and installing Git...
    powershell -Command "Invoke-WebRequest -Uri '%GIT_INSTALLER_URL%' -OutFile '%TEMP%\git_installer.exe'"
    "%TEMP%\git_installer.exe" /VERYSILENT /NORESTART
    del "%TEMP%\git_installer.exe"
    echo Git installed.
    set "PATH=C:\Program Files\Git\bin;%PATH%"
) else (
    echo Git found.
)

:: ---- Step 3: Create virtual environment ----
echo [3/9] Creating virtual environment...
if not exist "%VENV_DIR%" (
    python -m venv "%VENV_DIR%"
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)

:: ---- Step 4: Install dependencies ----
echo [4/9] Installing dependencies...
"%VENV_DIR%\Scripts\pip.exe" install -r "%PROJECT_DIR%requirements.txt" --quiet
echo Dependencies installed.

:: ---- Step 5: Create hidden screenshots folder ----
echo [5/9] Creating screenshots folder...
if not exist "%SCREENSHOTS_DIR%" (
    mkdir "%SCREENSHOTS_DIR%"
    attrib +h +s "%SCREENSHOTS_DIR%"
    echo Screenshots folder created and hidden.
) else (
    echo Screenshots folder already exists.
)

:: ---- Step 6: Create data folder ----
echo [6/9] Creating data folder...
if not exist "%PROJECT_DIR%data" (
    mkdir "%PROJECT_DIR%data"
    echo Data folder created.
) else (
    echo Data folder already exists.
)

:: ---- Step 7: Initialize database ----
echo [7/9] Initializing database...
"%VENV_DIR%\Scripts\python.exe" -c "import sys; sys.path.insert(0, r'%PROJECT_DIR%'); from app.database import init_db; init_db()"
echo Database initialized.

:: ---- Step 8: Install Windows Service ----
echo [8/9] Installing Windows Service...
"%VENV_DIR%\Scripts\python.exe" "%PROJECT_DIR%service.py" install
sc failure ParentalControl reset= 86400 actions= restart/5000/restart/30000/restart/60000
echo Service installed with auto-recovery.

:: ---- Step 9: Start Service ----
echo [9/9] Starting service...
"%VENV_DIR%\Scripts\python.exe" "%PROJECT_DIR%service.py" start
echo Service started.

echo.
echo ============================================================
echo  Installation complete!
echo  Web panel: http://localhost:7847
echo  Default password: admin (change it immediately!)
echo ============================================================
pause
