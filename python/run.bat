@echo off
chcp 65001 >nul
echo.
echo ============================================================
echo     SocketBridge AI Combat System v2.0
echo     The Binding of Isaac: Repentance
echo ============================================================
echo.

echo [1/3] Checking environment...
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found!
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo [2/3] Running environment check...
python -c "import sys; sys.path.insert(0, '.'); from socketbridge import *" 2>nul
if errorlevel 1 (
    echo Error: Module import failed!
    pause
    exit /b 1
)

echo [3/3] System ready!
echo.

echo Select mode:
echo   1. Basic Bridge (receive data only)
echo   2. AI Combat (automatic)
echo   3. Run Tests
echo   4. Exit
echo.

set /p choice="Enter choice (1-4): "

if "%choice%"=="1" (
    echo Starting basic bridge...
    python run.py --basic
) else if "%choice%"=="2" (
    echo Starting AI combat system...
    python run.py --ai
) else if "%choice%"=="3" (
    echo Running tests...
    python test_integration.py
    echo.
    python test_windows_compatibility.py
) else if "%choice%"=="4" (
    echo Goodbye!
) else (
    echo Invalid choice!
)

pause
