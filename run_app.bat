@echo off
setlocal
title Video Processing Web Server (Verbose Log Mode)

set "VENV_DIR=venv"

echo ===================================================
echo [START] Initializing Video Processing Web Server
echo ===================================================
echo.

if not exist "%VENV_DIR%" (
    echo [INFO] Virtual environment not found. Creating '%VENV_DIR%'...
    python -m venv %VENV_DIR%
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        goto ERROR_EXIT
    )
    echo [SUCCESS] Virtual environment created.
) else (
    echo [INFO] Existing virtual environment found at '%VENV_DIR%'.
)
echo.

echo [INFO] Activating virtual environment...
call "%VENV_DIR%\Scripts\activate"
if errorlevel 1 (
    echo [ERROR] Failed to activate the virtual environment.
    goto ERROR_EXIT
)
echo [SUCCESS] Virtual environment activated.
echo.

echo [INFO] Checking and installing dependencies...
python -m pip install --upgrade pip
pip install Flask Waitress
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install openai-whisper

echo.
echo ===================================================
echo [SUCCESS] Environment verification complete.
echo ===================================================
echo.
echo [INFO] Launching Flask Server via Waitress...
echo [INFO] A browser window should open automatically. 
echo [INFO] Press Ctrl+C in this window to stop the server.
echo.

python app.py
if errorlevel 1 (
    echo.
    echo [ERROR] Flask server crashed or failed to start.
    goto ERROR_EXIT
)

goto END

:ERROR_EXIT
echo.
echo [CRITICAL] Execution halted due to an error.
pause
exit /b 1

:END
pause