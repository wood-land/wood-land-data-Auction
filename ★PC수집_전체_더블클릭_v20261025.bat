@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if exist gosi\requirements.txt python -m pip install -q -r gosi\requirements.txt
if exist eiass\requirements.txt python -m pip install -q -r eiass\requirements.txt
python run_pc_all.py
pause
