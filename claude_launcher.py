"""
Claude Code Launcher - Cross Platform
系统托盘工具：自动检测代理端口，带代理启动 VS Code / Claude Desktop

支持：Windows / macOS / Linux
依赖：pip install pystray pillow
"""

import sys
import os
import math
import time
import socket
import threading
import subprocess

import pystray
from PIL import Image, ImageDraw, ImageColor

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


def _make_icon_raw(color: str) -> Image.Image:
    """
    渲染 256×256 RGBA 图标（科技数智风格）：
      · 深蓝黑背景 + 外发光晕
      · 四段分割环（状态颜色，10° 间隙）
      · 四个间隙节点 + 四个斜向内节点
      · 中央粗 C 弧（白色 + 高光条）
      · C 口两端彩色端点
    """
    S  = 256
    cx = cy = S // 2          # 128

    img  = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r, g, b = ImageColor.getrgb(color)

    # ── 1. 外发光晕 ──────────────────────────────────────────
    for i in range(20, 0, -1):
        a   = int(55 * (i / 20) ** 2.0)
        pad = i * 6
        draw.ellipse([pad, pad, S - pad, S - pad],
                     outline=(r, g, b, a), width=5)

    # ── 2. 深蓝黑背景圆 ──────────────────────────────────────
    BG = 8
    draw.ellipse([BG, BG, S - BG, S - BG], fill=(8, 10, 24, 255))

    # ── 3. 中心微辉（内晕） ───────────────────────────────────
    for i in range(7, 0, -1):
        a = int(22 * (1 - (i - 1) / 7))
        p = cx - 20 * i
        if p > BG:
            draw.ellipse([p, p, S - p, S - p], fill=(r, g, b, a))

    # ── 4. 四段分割环（每段 80°，间隙 10°）────────────────────
    RP     = 18                       # 环包围盒 padding
    RW     = 16                       # 环描边宽度
    GAP    = 10                       # 间隙度数
    RING_R = (S - 2 * RP) // 2       # 110：环椭圆半径

    for i in range(4):
        s0 = i * 90 + GAP // 2 - 90  # 旋转 -90° 使首段从顶部开始
        s1 = (i + 1) * 90 - GAP // 2 - 90
        draw.arc([RP, RP, S - RP, S - RP],
                 start=s0, end=s1, fill=(r, g, b, 255), width=RW)

    # 间隙位置的节点（上/右/下/左）
    DS = 11
    for deg in [0, 90, 180, 270]:
        rad = math.radians(deg - 90)          # 0 → 顶部
        dx  = int(cx + RING_R * math.cos(rad))
        dy  = int(cy + RING_R * math.sin(rad))
        draw.ellipse([dx - DS, dy - DS, dx + DS, dy + DS],
                     fill=(r, g, b, 235))

    # ── 5. 四个斜向内节点（45° 方向，电路感） ─────────────────
    NR = 88; NS = 8
    for deg in [45, 135, 225, 315]:
        rad = math.radians(deg)
        nx  = int(cx + NR * math.cos(rad))
        ny  = int(cy + NR * math.sin(rad))
        draw.ellipse([nx - NS, ny - NS, nx + NS, ny + NS],
                     fill=(r, g, b, 120))

    # ── 6. 中央 C 弧 ─────────────────────────────────────────
    CP  = 64                          # 弧包围盒 padding
    CW  = 24                          # 弧描边宽度
    C_R = (S - 2 * CP) // 2          # 64：弧半径

    draw.arc([CP, CP, S - CP, S - CP],
             start=40, end=320, fill="white", width=CW)
    # 内侧蓝白高光条（立体感）
    draw.arc([CP + 5, CP + 5, S - CP - 5, S - CP - 5],
             start=42, end=318,
             fill=(200, 220, 255, 130), width=9)

    # ── 7. C 口端点（彩色圆点，电路端子感）───────────────────
    CAP = 13
    for deg in [40, 320]:
        rad = math.radians(deg)
        ex  = int(cx + C_R * math.cos(rad))
        ey  = int(cy + C_R * math.sin(rad))
        draw.ellipse([ex - CAP, ey - CAP, ex + CAP, ey + CAP],
                     fill=(r, g, b, 255))

    return img


def make_icon(color: str) -> Image.Image:
    """生成 64×64 系统托盘图标。"""
    return _make_icon_raw(color).resize((64, 64), Image.LANCZOS)


def generate_icon_file(path: str) -> None:
    """生成多分辨率 .ico 文件，供 Windows 桌面快捷方式使用。"""
    raw   = _make_icon_raw(COLOR_IDLE)
    sizes = [256, 128, 64, 48, 32, 24, 16]
    imgs  = [raw.resize((s, s), Image.LANCZOS) for s in sizes]
    imgs[0].save(path, format="ICO", append_images=imgs[1:])


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

    # CLI: python claude_launcher.py --generate-icon [path.ico]
    if len(sys.argv) > 1 and sys.argv[1] == "--generate-icon":
        out = sys.argv[2] if len(sys.argv) > 2 else "launcher_icon.ico"
        generate_icon_file(out)
        return

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
