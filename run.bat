@echo off
title ZPL Visual Editor
cd /d "%~dp0"

:: Check if .venv exists
if exist ".venv\Scripts\python.exe" (
    echo Starting ZPL Visual Editor...
    .venv\Scripts\python.exe main.py 2>> "%~dp0log.txt"
    if errorlevel 1 (
        echo.
        echo HATA OLUSTU! Detaylar icin log.txt dosyasini kontrol edin.
        echo.
        pause
    )
    goto :end
)

:: No venv found - create one
echo Virtual environment not found. Setting up...
echo.

:: Check if python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Creating virtual environment...
python -m venv .venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    pause
    exit /b 1
)

echo Installing dependencies...
.venv\Scripts\pip.exe install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Setup complete! Starting ZPL Visual Editor...
.venv\Scripts\python.exe main.py 2>> "%~dp0log.txt"
if errorlevel 1 (
    echo.
    echo HATA OLUSTU! Detaylar icin log.txt dosyasini kontrol edin.
    echo.
    pause
)

:end
