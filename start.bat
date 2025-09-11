@echo off

python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed. Please install it and try again.
    exit /b 1
)

:: run the program
python src/main.py