@echo off
echo Installing Video Transcriber...

python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment. Make sure Python 3.12 is installed and in PATH.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Installation complete. Run start.cmd to launch the application.
pause