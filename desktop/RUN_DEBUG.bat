@echo off
rem Use this if 91TV.exe opens and closes. Put it next to 91TV.exe (inside dist\91TV or the unzipped portable folder).
cd /d "%~dp0"
if not exist 91TV.exe ( echo 91TV.exe not found next to this file. & pause & exit /b )
91TV.exe --selftest
echo.
echo ---- selftest report ----
type "%LOCALAPPDATA%\91TV\logs\selftest.txt"
echo.
echo ---- last log lines ----
powershell -NoProfile -Command "Get-Content \"$env:LOCALAPPDATA\91TV\logs\aurora.log\" -Tail 40"
pause
