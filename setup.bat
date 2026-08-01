@echo off
SETLOCAL EnableDelayedExpansion
echo ====================================================================
echo             StealthOverlay System Environment Setup
echo ====================================================================

:: Check for Node.js
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Node.js is not installed. Please install Node.js first.
    pause
    exit /b 1
)

:: Check for Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in system PATH.
    pause
    exit /b 1
)

echo [*] Installing Node.js dependencies...
call npm install

echo [*] Initializing Python Virtual Environment...
if not exist "venv" (
    python -m venv venv
)

echo [*] Installing Python dependencies...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r backend/requirements.txt

echo ====================================================================
echo  Setup complete. Select an option:
echo  [1] Run in Development Mode
echo  [2] Build Production Executables
echo ====================================================================
set /p opt="Enter choice (1-2): "

if "%opt%"=="1" (
    echo [*] Starting local Python backend...
    start cmd /k "venv\Scripts\activate.bat && python backend/server.py"
    echo [*] Launching React Native Windows...
    npx react-native run-windows
) else (
    echo [*] To compile for production, follow the build instructions in the guide.
    pause
)