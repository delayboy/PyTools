@echo off
@title 自制启动器 by Benson 可追加 -F 参数保存单个EXE文件
set NOW_BAT_DIR=""%~s0""
echo "/c %NOW_BAT_DIR% ::"
%1 mshta vbscript:CreateObject("Shell.Application").ShellExecute("cmd.exe","/c %NOW_BAT_DIR% ::","","runas",1)(window.close)&&exit
cd /d "%~dp0"
rem set PYTHONPATH=Z:\Computer\Program\Program_maker\python3


pyinstaller --onedir -i icon.ico MyD4Helper.py
pause
