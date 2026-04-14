#!/bin/bash
set -e

echo "================================================"
echo "  Claude Code Launcher - macOS / Linux 安装"
echo "================================================"
echo ""

# 检查 Python
if ! command -v python3 &>/dev/null; then
    echo "[错误] 未检测到 python3，请先安装 Python 3.10+"
    echo "  macOS:  brew install python"
    echo "  Ubuntu: sudo apt install python3 python3-pip"
    exit 1
fi

echo "[1/3] 安装 Python 依赖..."
pip3 install -r requirements.txt -q

# Linux 额外依赖提示
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo ""
    echo "[2/3] Linux 托盘支持..."
    echo "  如托盘图标不显示，请运行："
    echo "  Ubuntu/Debian: sudo apt install gir1.2-appindicator3-0.1"
    echo "  Fedora:        sudo dnf install libappindicator-gtk3"
else
    echo "[2/3] macOS 无需额外依赖 ✅"
fi

# 创建启动脚本
echo "[3/3] 创建启动脚本..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCHER="$SCRIPT_DIR/claude_launcher.py"

# macOS：创建 .app 包装
if [[ "$OSTYPE" == "darwin"* ]]; then
    APP_PATH="$HOME/Applications/ClaudeLauncher.app"
    mkdir -p "$APP_PATH/Contents/MacOS"
    cat > "$APP_PATH/Contents/MacOS/ClaudeLauncher" <<EOF
#!/bin/bash
cd "$SCRIPT_DIR"
python3 "$LAUNCHER"
EOF
    chmod +x "$APP_PATH/Contents/MacOS/ClaudeLauncher"

    cat > "$APP_PATH/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>ClaudeLauncher</string>
    <key>CFBundleName</key>
    <string>Claude Launcher</string>
    <key>CFBundleIdentifier</key>
    <string>com.claudelauncher.app</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
EOF
    echo ""
    echo "================================================"
    echo "  安装完成！"
    echo "  已创建：~/Applications/ClaudeLauncher.app"
    echo "  双击运行，或将其拖入 Dock"
    echo "================================================"

# Linux：创建 .desktop 文件
else
    DESKTOP_FILE="$HOME/.local/share/applications/claude-launcher.desktop"
    mkdir -p "$HOME/.local/share/applications"
    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=Claude Launcher
Comment=Claude Code 代理启动器
Exec=python3 $LAUNCHER
Icon=utilities-terminal
Terminal=false
Type=Application
Categories=Development;
EOF
    chmod +x "$DESKTOP_FILE"
    echo ""
    echo "================================================"
    echo "  安装完成！"
    echo "  已创建应用菜单项：Claude Launcher"
    echo "  也可直接运行：python3 $LAUNCHER"
    echo "================================================"
fi
