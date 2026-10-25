@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
python run_pc.py
pause
