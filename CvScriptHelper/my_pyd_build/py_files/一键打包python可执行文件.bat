@echo off
@title 自制启动器 by Benson 可追加 -F 参数保存单个EXE文件
set NOW_BAT_DIR=""%~s0""
echo "/c %NOW_BAT_DIR% ::"
%1 mshta vbscript:CreateObject("Shell.Application").ShellExecute("cmd.exe","/c %NOW_BAT_DIR% ::","","runas",1)(window.close)&&exit
cd /d "%~dp0"
rem set PYTHONPATH=Z:\Computer\Program\Program_maker\python3
set PYTHONPATH=%~dp0py_native_package_stubs;%PYTHONPATH%
echo 正在配置环境变量，防止 Transformers 冲突...
set USE_TORCH=1
set USE_TF=0
set TRANSFORMERS_NO_ADVISORY_WARNINGS=1
set TRANSFORMERS_NO_ADVISORY_WARNINGS=1
set HF_HUB_DISABLE_TELEMETRY=1
pyinstaller --onedir --uac-admin -i icon.ico --exclude-module PyTools --collect-all mineru  --collect-all selenium --collect-all ultralytics --collect-all torchvision --collect-binaries torchvision --add-data "PyTools;PyTools" pyd_main.py
rem pyinstaller --onedir --uac-admin -i icon.ico --exclude-module PyTools  --collect-all selenium --collect-all ultralytics --collect-all torchvision --collect-binaries torchvision --add-data "PyTools;PyTools" pyd_main.py
pause
pause
pause