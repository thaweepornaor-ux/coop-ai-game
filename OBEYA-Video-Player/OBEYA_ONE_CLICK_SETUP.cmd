@echo off
setlocal
title OBEYA Video Player - One Click Setup
echo =========================================================
echo           OBEYA VIDEO PLAYER - DESKTOP SETUP
echo =========================================================
echo.
echo One-time setup. Your original OBEYA.mp4 and icon PNG
echo should be in Downloads or on the Desktop.
echo.
echo It uses the internet only to download the player code.
echo After setup, use the new OBEYA icon on your Desktop offline.
echo.
set "SETUP_URL=https://raw.githubusercontent.com/thaweepornaor-ux/coop-ai-game/obeya-player-build-kit/OBEYA-Video-Player/OBEYA_INSTALL_DESKTOP.ps1"
set "SETUP_SCRIPT=%TEMP%\OBEYA_INSTALL_DESKTOP.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri $env:SETUP_URL -OutFile $env:SETUP_SCRIPT"
if errorlevel 1 (
  echo.
  echo Download failed. Internet is required for the FIRST SETUP only.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SETUP_SCRIPT%"
if errorlevel 1 (
  echo.
  echo Setup did not finish. Check the error above.
  pause
  exit /b 1
)
echo.
echo DONE - OBEYA Video Player has opened and the Desktop
echo shortcut is ready for future offline double-click use.
echo.
pause
