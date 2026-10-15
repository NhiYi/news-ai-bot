@echo off
cd /d "%~dp0"
python main.py --publish
if errorlevel 1 exit /b 1
