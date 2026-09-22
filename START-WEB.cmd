@echo off
setlocal
where py >nul 2>nul
if errorlevel 1 goto python
py -3 "%~dp0web_manager.py" %*
goto finish
:python
python "%~dp0web_manager.py" %*
:finish
pause
