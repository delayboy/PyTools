@echo off
chcp 65001 >nul
@title 自制启动器 by Benson
for /f "delims=" %%i in ('powershell -NoProfile -Command "Write-Host ((Get-Item -LiteralPath '%~0').FullName)"') do set NOW_BAT_PATH=%%i
for %%i in ("%NOW_BAT_PATH%") do set NOW_BAT_DIR2=%%~dpi
set NOW_BAT_DIR=""%~s0""
echo %NOW_BAT_DIR2%
echo "/c %NOW_BAT_DIR% ::"
%1 mshta vbscript:CreateObject("Shell.Application").ShellExecute("cmd.exe","/c %NOW_BAT_DIR% ::","","runas",1)(window.close)&&exit
cd /d %NOW_BAT_DIR2%
set PYTHONPATH=Z:\Computer\Program\Program_maker\python3

python 同步手机音乐文件夹.py
pause
