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
:: Remove trailing backslash for safety
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
set "VENV_DIR=%PROJECT_DIR%\.venv"
set "SCREENSHOTS_DIR=C:\ProgramData\ParentalControl\.screenshots"
set "PYTHON_INSTALLER_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
set "GIT_INSTALLER_URL=https://github.com/git-for-windows/git/releases/download/v2.44.0.windows.1/Git-2.44.0-64-bit.exe"

:: ---- Step 1: Check Python ----
echo [1/10] Checking for Python...
set "PYTHON_CMD="

:: Try common locations
where python >nul 2>&1 && set "PYTHON_CMD=python" && goto :python_found
if exist "C:\Program Files\Python311\python.exe" set "PYTHON_CMD=C:\Program Files\Python311\python.exe" && goto :python_found
if exist "C:\Program Files\Python312\python.exe" set "PYTHON_CMD=C:\Program Files\Python312\python.exe" && goto :python_found
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe" && goto :python_found
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe" && goto :python_found

:: Python not found - install it
echo Python not found. Downloading Python 3.11...
echo (This may take a few minutes)
curl -Lo "%TEMP%\python_installer.exe" "%PYTHON_INSTALLER_URL%"
if !errorlevel! neq 0 (
    echo [ERROR] Failed to download Python. Check your internet connection.
    pause
    exit /b 1
)
echo Installing Python silently...
"%TEMP%\python_installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 Include_launcher=1
if !errorlevel! neq 0 (
    echo [ERROR] Python installation failed.
    pause
    exit /b 1
)
del "%TEMP%\python_installer.exe" 2>nul

:: Refresh PATH from registry (append to existing to preserve System32, PowerShell, etc.)
for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYSTEM_PATH=%%B"
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USER_PATH=%%B"
set "PATH=%PATH%;%SYSTEM_PATH%;%USER_PATH%"

:: Try to find python again
where python >nul 2>&1 && set "PYTHON_CMD=python" && goto :python_found
if exist "C:\Program Files\Python311\python.exe" set "PYTHON_CMD=C:\Program Files\Python311\python.exe" && goto :python_found
echo [ERROR] Python installed but cannot be found. Please restart this script.
pause
exit /b 1

:python_found
echo Python found: %PYTHON_CMD%
"%PYTHON_CMD%" --version

:: ---- Step 2: Check Git ----
echo.
echo [2/10] Checking for Git...
where git >nul 2>&1
if !errorlevel! equ 0 (
    echo Git found.
    goto :git_done
)
echo Git not found. Downloading Git...
curl -Lo "%TEMP%\git_installer.exe" "%GIT_INSTALLER_URL%"
if !errorlevel! neq 0 (
    echo [ERROR] Failed to download Git. Check your internet connection.
    pause
    exit /b 1
)
echo Installing Git silently...
"%TEMP%\git_installer.exe" /VERYSILENT /NORESTART /SP-
del "%TEMP%\git_installer.exe" 2>nul
:: Refresh PATH
for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYSTEM_PATH=%%B"
set "PATH=%PATH%;%SYSTEM_PATH%;C:\Program Files\Git\cmd"
where git >nul 2>&1
if !errorlevel! neq 0 (
    echo [WARNING] Git installed but PATH not updated. Auto-update feature may not work until reboot.
) else (
    echo Git installed.
)
:git_done

:: ---- Step 2b: Initialize git repo if missing (ZIP downloads don't include .git) ----
if not exist "%PROJECT_DIR%\.git" (
    echo Initializing git repository for auto-updates...
    where git >nul 2>&1
    if !errorlevel! equ 0 (
        pushd "%PROJECT_DIR%"
        git init >nul 2>&1
        git remote add origin https://github.com/tessimago/ParentalControlApp.git >nul 2>&1
        git fetch origin main >nul 2>&1
        if !errorlevel! equ 0 (
            git reset --mixed origin/main >nul 2>&1
            echo Git repo initialized. Auto-update will work.
        ) else (
            echo [WARNING] Could not fetch from GitHub. Auto-update may not work until network is available.
        )
        popd
    ) else (
        echo [WARNING] Git not available. Auto-update feature will not work.
    )
) else (
    echo Git repository already initialized.
)

:: ---- Step 3: Create virtual environment ----
echo.
echo [3/10] Creating virtual environment...
if exist "%VENV_DIR%\Scripts\python.exe" (
    echo Virtual environment already exists.
    goto :venv_done
)
"%PYTHON_CMD%" -m venv "%VENV_DIR%"
if !errorlevel! neq 0 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)
echo Virtual environment created.
:venv_done

:: ---- Step 4: Install dependencies ----
echo.
echo [4/10] Installing dependencies...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip --quiet 2>nul
"%VENV_DIR%\Scripts\python.exe" -m pip install -r "%PROJECT_DIR%\requirements.txt" --quiet
if !errorlevel! neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo Dependencies installed.

:: ---- Step 5: Verify install ----
echo.
echo [5/11] Verifying Python packages...
"%VENV_DIR%\Scripts\python.exe" -c "import flask, psutil, mss, PIL, bcrypt; print('All packages OK')"
if !errorlevel! neq 0 (
    echo [ERROR] Some packages failed to install.
    pause
    exit /b 1
)

:: ---- Step 6: Create hidden screenshots folder ----
echo.
echo [6/11] Creating screenshots folder...
if not exist "%SCREENSHOTS_DIR%" (
    mkdir "%SCREENSHOTS_DIR%"
    attrib +h +s "%SCREENSHOTS_DIR%"
    echo Screenshots folder created and hidden.
) else (
    echo Screenshots folder already exists.
)

:: ---- Step 7: Create data folder ----
echo.
echo [7/11] Creating data folder...
if not exist "%PROJECT_DIR%\data" (
    mkdir "%PROJECT_DIR%\data"
    echo Data folder created.
) else (
    echo Data folder already exists.
)

:: ---- Step 8: Initialize database ----
echo.
echo [8/11] Initializing database...
"%VENV_DIR%\Scripts\python.exe" -c "import sys, os; sys.path.insert(0, os.path.abspath(r'%PROJECT_DIR%')); from app.database import init_db; init_db()"
if !errorlevel! neq 0 (
    echo [ERROR] Database initialization failed.
    pause
    exit /b 1
)
echo Database initialized.

:: ---- Step 9: Install as startup task ----
echo.
echo [9/11] Installing startup task...
"%VENV_DIR%\Scripts\python.exe" "%PROJECT_DIR%\service.py" install
if !errorlevel! neq 0 (
    echo [WARNING] Task registration failed. You can still run manually with run_dev.py
)

:: ---- Step 10: Register companion process (runs in user session for screenshots) ----
echo.
echo [10/11] Registering companion process for screenshots...
schtasks /create /tn "ParentalControlCompanion" /tr "\"%VENV_DIR%\Scripts\pythonw.exe\" \"%PROJECT_DIR%\companion.pyw\"" /sc onlogon /rl highest /f >nul 2>&1
if !errorlevel! neq 0 (
    echo [WARNING] Could not register companion task. Screenshots may not work from service.
) else (
    echo Companion registered to run at login.
)
:: Also start it now
start "" "%VENV_DIR%\Scripts\pythonw.exe" "%PROJECT_DIR%\companion.pyw"

:: ---- Step 11: Start service now ----
echo.
echo [11/11] Starting service...
start "" "%VENV_DIR%\Scripts\pythonw.exe" "%PROJECT_DIR%\run_service.pyw"
echo Service started.

echo.
echo ============================================================
echo  Installation complete!
echo.
echo  Web panel: http://localhost:7847
echo  Default password: admin (change it immediately!)
echo.
echo  NOTE: Schedule enforcement is DISABLED on first run.
echo  Configure your schedule via the web panel before enabling.
echo ============================================================
pause
