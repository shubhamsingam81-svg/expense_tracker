@echo off
echo ============================================
echo   JDAP Orchestrator Tool
echo ============================================
echo.

REM Determine workspace root (2 levels up from this script)
set WORKSPACE=%~dp0..\..\
pushd %WORKSPACE%
set WORKSPACE=%CD%
popd

echo Workspace: %WORKSPACE%
echo.

REM Activate venv if it exists
if exist "%WORKSPACE%\.venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call "%WORKSPACE%\.venv\Scripts\activate.bat"
) else (
    echo WARNING: No .venv found at %WORKSPACE%\.venv
    echo Using system Python. Flask must be installed globally.
)

REM Check if Flask is installed
python -c "import flask" 2>nul
if errorlevel 1 (
    echo Installing Flask...
    pip install flask
    echo.
)

echo.
echo Starting JDAP Orchestrator...
echo.
echo ============================================
echo   Open http://localhost:5500 in browser
echo   Do NOT open index.html directly!
echo ============================================
echo.
start http://localhost:5500
python "%~dp0app.py" --workspace "%WORKSPACE%" --port 5500
pause
