@echo off
chcp 65001 >nul
echo ================================================
echo   Claude Code Launcher - Windows 安装
echo ================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    echo 下载：https://www.python.org/downloads/
    pause & exit /b
)

echo [1/2] 安装 Python 依赖（pystray / pillow）...
echo       首次安装需要网络，请稍候...
pip install pystray pillow
if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败，请检查网络后重试
    pause & exit /b
)
echo       依赖安装成功

echo.
echo [2/2] 创建桌面快捷方式...
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_PATH=%SCRIPT_DIR%claude_launcher.py"
set "ICON_PATH=%SCRIPT_DIR%launcher_icon.ico"
set "SHORTCUT=%USERPROFILE%\Desktop\Claude启动器.lnk"

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = 'pythonw.exe'; $s.Arguments = '\"%SCRIPT_PATH%\"'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.IconLocation = '%ICON_PATH%,0'; $s.Description = 'Claude Code 代理启动器'; $s.Save()"

echo.
echo ================================================
echo   安装完成！桌面已生成 Claude启动器 快捷方式
echo   双击运行后在系统托盘找到彩色节点图标
echo ================================================
pause
