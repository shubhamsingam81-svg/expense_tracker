@echo off
echo ============================================
echo   JDAP Orchestrator Tool
echo ============================================
echo.

REM Workspace = parent directory of this folder (where project folder + JDAP folder live)
set WORKSPACE=%~dp0..\
pushd "%WORKSPACE%"
set WORKSPACE=%CD%
popd

echo Workspace: %WORKSPACE%
echo.
echo Starting JDAP Orchestrator...
echo.
echo ============================================
echo   Browser will open automatically.
echo   Close browser tab to stop the server.
echo ============================================
echo.

start http://localhost:5500
"%~dp0jdap_orchestrator.exe" --workspace "%WORKSPACE%" --port 5500
