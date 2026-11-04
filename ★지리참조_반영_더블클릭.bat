@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0eiass"
python run_georef.py
pause
