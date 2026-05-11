@echo off

setlocal

cd /d %~dp0

echo Installing Video Transcriber...

python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment. Make sure Python is installed and in PATH.
    pause
    exit /b 1
)

venv\Scripts\python -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip.
    pause
    exit /b 1
)

venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Installation complete. Run start.cmd to launch the application.
pause