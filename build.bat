@echo off
echo ============================================
echo   JDAP Orchestrator - Build Executable
echo ============================================
echo.

REM Navigate to script directory
cd /d "%~dp0"

REM Activate venv
if exist "..\..\..venv\Scripts\activate.bat" (
    call "..\..\..venv\Scripts\activate.bat"
)
if exist "..\..\.venv\Scripts\activate.bat" (
    call "..\..\.venv\Scripts\activate.bat"
)

REM Check PyInstaller
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
    echo.
)

REM Clean previous build
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

echo Building jdap_orchestrator.exe...
echo.
pyinstaller jdap_orchestrator.spec --clean

if errorlevel 1 (
    echo.
    echo BUILD FAILED!
    pause
    exit /b 1
)

echo.
echo ============================================
echo   BUILD SUCCESSFUL
echo   Output: dist\jdap_orchestrator.exe
echo ============================================
echo.

REM Create distribution package
if not exist "dist\JDAP_Orchestrator" mkdir "dist\JDAP_Orchestrator"
move "dist\jdap_orchestrator.exe" "dist\JDAP_Orchestrator\" >nul

REM Copy the distribution run.bat
copy "run_dist.bat" "dist\JDAP_Orchestrator\run.bat" >nul

echo Distribution package ready at: dist\JDAP_Orchestrator\
echo.
echo Contents:
dir /b "dist\JDAP_Orchestrator\"
echo.
pause
