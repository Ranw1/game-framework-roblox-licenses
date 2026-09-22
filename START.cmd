@echo off
setlocal
where python >nul 2>nul
if errorlevel 1 goto trylauncher
python "%~dp0license_manager.py" %*
goto finish
:trylauncher
py -3 "%~dp0license_manager.py" %*
:finish
pause
