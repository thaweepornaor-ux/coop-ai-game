@echo off
setlocal
title OBEYA Video Player - Single EXE Builder
cd /d "%~dp0"
echo =====================================================
echo     OBEYA Video Player - Windows Single EXE Build
echo =====================================================
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0BUILD_OBEYA.ps1"
if errorlevel 1 (
  echo.
  echo BUILD FAILED - See the error above.
  pause
  exit /b 1
)
echo.
echo Ready: OBEYA.exe -- copy just this file to Desktop.
echo.
pause
