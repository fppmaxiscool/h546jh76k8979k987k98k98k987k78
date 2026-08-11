@echo off
cd /d "%~dp0"
echo Installing requirements...
python -m pip install -r requirements.txt
if errorlevel 1 goto :error
echo Starting bot...
python bot.py
pause
exit /b 0

:error
echo Failed to install requirements. Check that Python is installed and on PATH.
pause
exit /b 1
