"""
Claude Code Launcher - Cross Platform
系统托盘工具：自动检测代理端口，带代理启动 VS Code / Claude Desktop

支持：Windows / macOS / Linux
依赖：pip install pystray pillow
"""

import sys
import os
import time
import socket
import threading
import subprocess

import pystray
from PIL import Image, ImageDraw

# ─────────────────────────────────────────
# 平台检测
# ─────────────────────────────────────────

IS_WIN   = sys.platform == "win32"
IS_MAC   = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# ─────────────────────────────────────────
# 各平台默认路径
# ─────────────────────────────────────────

def _default_vscode() -> str:
    if IS_WIN:
        return os.path.expandvars(
            r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"
        )
    if IS_MAC:
        return "/Applications/Visual Studio Code.app/Contents/MacOS/Electron"
    # Linux: 通常在 PATH 里，直接用命令名
    return "code"


def _default_claude_desktop() -> str:
    if IS_WIN:
        return os.path.expandvars(r"%LOCALAPPDATA%\AnthropicClaude\claude.exe")
    if IS_MAC:
        return "/Applications/Claude.app/Contents/MacOS/Claude"
    # Linux 暂无官方 Claude Desktop
    return ""


# ─────────────────────────────────────────
# 用户配置区
# ─────────────────────────────────────────

VSCODE_PATH         = _default_vscode()
CLAUDE_DESKTOP_PATH = _default_claude_desktop()

# 默认打开的项目目录，留空则不指定
DEFAULT_PROJECT_DIR = ""

# 候选代理端口（按顺序探测）
CANDIDATE_PORTS = [7890, 7891, 7892, 7893, 10809, 10808, 1080, 8080, 8118]

# ─────────────────────────────────────────
# 代理检测
# ─────────────────────────────────────────

def is_port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            return False


def _get_system_proxy_port_windows() -> int | None:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
        enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
        if enabled:
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
            if ":" in server and "=" not in server:
                return int(server.split(":")[-1])
    except Exception:
        pass
    return None


def _get_system_proxy_port_macos() -> int | None:
    """
    macOS: 用 networksetup 读 Wi-Fi / Ethernet 的 HTTP 代理端口
    也检查环境变量 HTTP_PROXY / http_proxy
    """
    # 先查环境变量（适用于终端启动场景）
    for key in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"):
        val = os.environ.get(key, "")
        if val:
            try:
                return int(val.rstrip("/").split(":")[-1])
            except ValueError:
                pass

    # 再查 networksetup（适用于系统代理）
    interfaces = ["Wi-Fi", "Ethernet", "USB 10/100/1000 LAN"]
    for iface in interfaces:
        try:
            out = subprocess.check_output(
                ["networksetup", "-getwebproxy", iface],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            enabled = any(
                "yes" in line.lower()
                for line in out.splitlines()
                if "enabled" in line.lower()
            )
            if enabled:
                for line in out.splitlines():
                    if line.lower().startswith("port"):
                        port = int(line.split(":")[-1].strip())
                        if port:
                            return port
        except Exception:
            pass
    return None


def _get_system_proxy_port_linux() -> int | None:
    """
    Linux: 查环境变量，再尝试 gsettings
    """
    for key in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"):
        val = os.environ.get(key, "")
        if val:
            try:
                return int(val.rstrip("/").split(":")[-1])
            except ValueError:
                pass

    try:
        out = subprocess.check_output(
            ["gsettings", "get", "org.gnome.system.proxy.http", "port"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        port = int(out)
        if port:
            return port
    except Exception:
        pass
    return None


def detect_proxy_port() -> int | None:
    # 1. 读系统代理设置
    if IS_WIN:
        sys_port = _get_system_proxy_port_windows()
    elif IS_MAC:
        sys_port = _get_system_proxy_port_macos()
    else:
        sys_port = _get_system_proxy_port_linux()

    if sys_port and is_port_listening(sys_port):
        return sys_port

    # 2. 扫描候选端口
    for port in CANDIDATE_PORTS:
        if is_port_listening(port):
            return port

    return None


def set_proxy_env(port: int):
    proxy_http  = f"http://127.0.0.1:{port}"
    proxy_socks = f"socks5://127.0.0.1:{port}"
    os.environ["HTTP_PROXY"]  = proxy_http
    os.environ["HTTPS_PROXY"] = proxy_http
    os.environ["ALL_PROXY"]   = proxy_socks


# ─────────────────────────────────────────
# 启动应用
# ─────────────────────────────────────────

def launch_vscode():
    env = os.environ.copy()

    if IS_LINUX and VSCODE_PATH == "code":
        # Linux 上 code 在 PATH 里，直接调用
        args = ["code"]
        if DEFAULT_PROJECT_DIR and os.path.isdir(DEFAULT_PROJECT_DIR):
            args.append(DEFAULT_PROJECT_DIR)
        subprocess.Popen(args, env=env)
        return

    if not os.path.exists(VSCODE_PATH):
        notify("VS Code 未找到", f"路径不存在：\n{VSCODE_PATH}")
        return

    if IS_MAC:
        # macOS 用 open -a 更稳定
        args = ["open", "-a", "Visual Studio Code"]
        if DEFAULT_PROJECT_DIR and os.path.isdir(DEFAULT_PROJECT_DIR):
            args += ["--args", DEFAULT_PROJECT_DIR]
        subprocess.Popen(args, env=env)
    else:
        args = [VSCODE_PATH]
        if DEFAULT_PROJECT_DIR and os.path.isdir(DEFAULT_PROJECT_DIR):
            args.append(DEFAULT_PROJECT_DIR)
        subprocess.Popen(args, env=env)


def launch_claude_desktop():
    env = os.environ.copy()

    if not CLAUDE_DESKTOP_PATH:
        notify("Claude Desktop", "Linux 暂无官方 Claude Desktop\n可使用 VS Code + Claude Code 插件")
        return

    if not os.path.exists(CLAUDE_DESKTOP_PATH):
        notify("Claude Desktop 未找到", f"路径不存在：\n{CLAUDE_DESKTOP_PATH}")
        return

    if IS_MAC:
        subprocess.Popen(["open", "-a", "Claude"], env=env)
    else:
        subprocess.Popen([CLAUDE_DESKTOP_PATH], env=env)


# ─────────────────────────────────────────
# 托盘图标
# ─────────────────────────────────────────

COLOR_IDLE    = "#6366F1"  # 紫：待机
COLOR_WORKING = "#F59E0B"  # 黄：检测中
COLOR_OK      = "#10B981"  # 绿：成功
COLOR_ERROR   = "#EF4444"  # 红：失败

_icon = None


def make_icon(color: str) -> Image.Image:
    size = 64
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, size - 2, size - 2], fill=color)
    draw.arc([14, 14, size - 14, size - 14], start=40, end=320, fill="white", width=7)
    return img


def notify(title: str, message: str):
    if _icon:
        _icon.notify(message, title)


# ─────────────────────────────────────────
# 菜单动作
# ─────────────────────────────────────────

def _do_launch(fns: list, label: str):
    """通用启动流程"""
    _icon.icon = make_icon(COLOR_WORKING)
    notify("Claude 启动器", "正在检测代理端口...")

    port = detect_proxy_port()
    if port is None:
        _icon.icon = make_icon(COLOR_ERROR)
        notify("⚠️ 未检测到代理", "请先开启科学上网工具，再重试")
        time.sleep(3)
        _icon.icon = make_icon(COLOR_IDLE)
        return

    set_proxy_env(port)
    notify(f"✅ 端口 {port} 就绪", f"正在启动 {label}...")

    for fn in fns:
        fn()
        time.sleep(1)

    _icon.icon = make_icon(COLOR_OK)
    time.sleep(3)
    _icon.icon = make_icon(COLOR_IDLE)


def action_launch_all(icon, item):
    threading.Thread(
        target=_do_launch,
        args=([launch_vscode, launch_claude_desktop], "VS Code + Claude Desktop"),
        daemon=True,
    ).start()


def action_launch_vscode(icon, item):
    threading.Thread(
        target=_do_launch,
        args=([launch_vscode], "VS Code"),
        daemon=True,
    ).start()


def action_launch_claude(icon, item):
    threading.Thread(
        target=_do_launch,
        args=([launch_claude_desktop], "Claude Desktop"),
        daemon=True,
    ).start()


def action_check_proxy(icon, item):
    def _run():
        port = detect_proxy_port()
        if port:
            notify("代理状态", f"✅ 端口 {port} 正在监听")
        else:
            notify("代理状态", "❌ 未检测到可用代理端口")
    threading.Thread(target=_run, daemon=True).start()


def action_quit(icon, item):
    icon.stop()


# ─────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────

def main():
    global _icon

    # Linux 上 pystray 需要 AppIndicator，给个友好提示
    if IS_LINUX:
        try:
            import gi
        except ImportError:
            print("Linux 提示：如托盘图标不显示，请安装 gir1.2-appindicator3-0.1")
            print("  Ubuntu/Debian: sudo apt install gir1.2-appindicator3-0.1")

    menu = pystray.Menu(
        pystray.MenuItem("🚀 启动 VS Code + Claude Desktop", action_launch_all, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("启动 VS Code（仅）", action_launch_vscode),
        pystray.MenuItem("启动 Claude Desktop（仅）", action_launch_claude),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("检测代理状态", action_check_proxy),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", action_quit),
    )

    _icon = pystray.Icon(
        "claude_launcher",
        make_icon(COLOR_IDLE),
        "Claude Code Launcher",
        menu,
    )
    _icon.run()


if __name__ == "__main__":
    main()
