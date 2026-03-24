@echo off
REM Build executable for Windows

echo Building File Sharing Server for Windows...
python -m PyInstaller file_sharing_server.spec --clean

if %ERRORLEVEL% EQU 0 (
    echo [OK] Build successful!
    echo Executable location: dist\file-sharing-server
    echo.
    echo Run with: dist\file-sharing-server\file-sharing-server.exe share C:\path\to\folder
) else (
    echo [ERROR] Build failed
    exit /b 1
)
