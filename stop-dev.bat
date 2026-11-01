@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev\stop_all.ps1" %*
echo.
pause