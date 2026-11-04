@echo off
setlocal EnableExtensions
title OBEYA - Create One EXE on Desktop
echo ========================================================
echo               OBEYA VIDEO PLAYER
echo      ONE-TIME BUILD - ONE EXE FOR WINDOWS
echo ========================================================
echo.
echo Put the original OBEYA.mp4 and OBEYA icon PNG in
echo your Downloads folder. Their numbered copies are OK.
echo This will create a single OBEYA.exe on your Desktop.
echo.
set "WORK=%LOCALAPPDATA%\OBEYA One-File Builder"
if not exist "%WORK%" mkdir "%WORK%"
set "BASE=https://raw.githubusercontent.com/thaweepornaor-ux/coop-ai-game/obeya-player-build-kit/OBEYA-Video-Player/"
echo Downloading small offline player source files...
for %%F in (OBEYA.html OBEYA_ONEFILE_Launcher.cs BUILD_OBEYA_ONEFILE.ps1) do (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri ('%BASE%%%F') -OutFile (Join-Path '%WORK%' '%%F')"
  if errorlevel 1 goto FAILED
)
echo.
echo Starting the one-time Windows build...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%WORK%\BUILD_OBEYA_ONEFILE.ps1"
if errorlevel 1 goto FAILED
echo.
echo SUCCESS. Your Desktop now has the complete OBEYA.exe.
echo You need ONLY this one EXE from now on. No more setup.
echo.
pause
exit /b 0
:FAILED
echo.
echo BUILD FAILED. Keep this window and read the error above.
echo Do not claim the file was created if BUILD FAILED is shown.
echo.
pause
exit /b 1
