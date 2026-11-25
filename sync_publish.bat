@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY="%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
if not exist %PY% set PY=python
%PY% -I sync_publish.py 双机同步发布
pause
