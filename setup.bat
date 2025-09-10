@echo off

pip --version > nul 2>&1
if %errorlevel% neq 0 (
    echo pip is not installed. Please install Python + pip and try again.
    exit /b 1
)

pip install -r requirements.txt