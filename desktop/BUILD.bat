@echo off
cd /d "%~dp0"
echo Building 91 TV - this takes 5-10 minutes. Do not close this window.
powershell -NoProfile -ExecutionPolicy Bypass -Command "& { .\build.ps1 *>&1 | Tee-Object -FilePath build-log.txt }"
echo.
echo ================================================================
echo Finished. Full output is saved in build-log.txt (same folder).
echo If you see "Portable ZIP:" above, look in the "release" folder.
echo ================================================================
pause
