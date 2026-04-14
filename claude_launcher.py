"""
Claude Code Launcher - Cross Platform
系统托盘工具：自动检测代理端口，带代理启动 VS Code / Claude Desktop

支持：Windows / macOS / Linux
依赖：pip install pystray pillow
"""

import sys
import os
import glob
import json
import math
import time
import shutil
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
# 各平台默认路径（多候选 + 注册表 + PATH 搜索）
# ─────────────────────────────────────────

def _first_existing(paths):
    """返回列表中第一个真实存在的路径，都不存在则返回 None。"""
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def _win_app_path(exe_name: str):
    """
    从 Windows 注册表 App Paths 读已注册程序的完整路径。
    安装器通常会在这里写入自己，最可靠。
    """
    if not IS_WIN:
        return None
    try:
        import winreg
    except ImportError:
        return None
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(
                root,
                rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}",
            ) as key:
                path, _ = winreg.QueryValueEx(key, None)
                if path and os.path.exists(path):
                    return path
        except OSError:
            continue
    return None


def _default_vscode() -> str:
    """自动检测 VS Code 路径；找不到返回空字符串。"""
    if IS_WIN:
        candidates = [
            _win_app_path("Code.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft VS Code\Code.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft VS Code\Code.exe"),
            shutil.which("code"),
        ]
        return _first_existing(candidates) or ""
    if IS_MAC:
        candidates = [
            "/Applications/Visual Studio Code.app/Contents/MacOS/Electron",
            os.path.expanduser("~/Applications/Visual Studio Code.app/Contents/MacOS/Electron"),
        ]
        return _first_existing(candidates) or ""
    # Linux
    return shutil.which("code") or ""


def _default_claude_desktop() -> str:
    """自动检测 Claude Desktop 路径；找不到返回空字符串。"""
    if IS_WIN:
        base = os.path.expandvars(r"%LOCALAPPDATA%\AnthropicClaude")
        # Squirrel 版本化子目录（app-X.Y.Z\claude.exe），按版本倒序取最新
        app_versions = sorted(
            glob.glob(os.path.join(base, "app-*", "claude.exe")) +
            glob.glob(os.path.join(base, "app-*", "Claude.exe")),
            reverse=True,
        )
        candidates = [
            _win_app_path("claude.exe"),
            os.path.join(base, "claude.exe"),
            os.path.join(base, "Claude.exe"),
            *app_versions,
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\claude-desktop\claude.exe"),
            shutil.which("claude"),
        ]
        return _first_existing(candidates) or ""
    if IS_MAC:
        p = "/Applications/Claude.app/Contents/MacOS/Claude"
        return p if os.path.exists(p) else ""
    # Linux 暂无官方 Claude Desktop
    return ""


# ─────────────────────────────────────────
# 用户配置加载（launcher_config.json 可覆盖所有默认值）
# ─────────────────────────────────────────

def _config_path() -> str:
    """配置文件路径：与脚本同目录的 launcher_config.json。"""
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "launcher_config.json",
    )


def _load_config() -> dict:
    """
    读取用户配置。文件不存在则返回空 dict，读失败时打印警告。

    示例 launcher_config.json：
      {
        "vscode_path": "D:\\Tools\\VSCode\\Code.exe",
        "claude_desktop_path": "",
        "default_project_dir": "D:\\projects",
        "candidate_ports": [7890, 7892, 10809]
      }
    """
    path = _config_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[配置] 读取 {path} 失败：{e}")
        return {}


_cfg = _load_config()

# 用户可在 JSON 里覆盖；未填则使用自动检测
VSCODE_PATH         = _cfg.get("vscode_path")         or _default_vscode()
CLAUDE_DESKTOP_PATH = _cfg.get("claude_desktop_path") or _default_claude_desktop()
DEFAULT_PROJECT_DIR = _cfg.get("default_project_dir", "")
CANDIDATE_PORTS     = _cfg.get(
    "candidate_ports",
    [7890, 7891, 7892, 7893, 10809, 10808, 1080, 8080, 8118],
)

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


def _verify_proxy(port: int, timeout: float = 3.0) -> bool:
    """
    通过代理对 api.anthropic.com:443 发起 HTTP CONNECT 隧道请求，
    验证代理上游是否真正可达。

    为什么不用 urllib + HTTP：
      · HTTP 请求可能被 Clash 本地伪造成功（缓存 / fake-ip / 规则返回）
      · api.anthropic.com 正是 Claude Code 的真实目标端点
      · CONNECT 隧道无法被代理凭空伪造，上游断线会返回 502/504 或超时
    """
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(
                b"CONNECT api.anthropic.com:443 HTTP/1.1\r\n"
                b"Host: api.anthropic.com:443\r\n"
                b"\r\n"
            )
            # 代理返回形如 "HTTP/1.1 200 Connection established\r\n..."
            resp = sock.recv(64)
            return resp.startswith(b"HTTP/1.") and b" 200 " in resp
    except Exception:
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

    if sys_port and is_port_listening(sys_port) and _verify_proxy(sys_port):
        return sys_port

    # 2. 扫描候选端口（必须先监听 + 真实请求能通）
    for port in CANDIDATE_PORTS:
        if is_port_listening(port) and _verify_proxy(port):
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

def _is_installed(path: str) -> bool:
    """应用是否真实存在（空字符串 / 路径不存在都视为未安装）。"""
    return bool(path) and os.path.exists(path)


def launch_vscode():
    env = os.environ.copy()

    if not _is_installed(VSCODE_PATH):
        notify(
            "VS Code 未安装",
            "未检测到 VS Code。\n"
            "请安装后重试，或在 launcher_config.json 中手动指定 vscode_path。",
        )
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

    if not _is_installed(CLAUDE_DESKTOP_PATH):
        notify(
            "Claude Desktop 未安装",
            "未检测到 Claude Desktop。\n"
            "可使用 VS Code + Claude Code 扩展，\n"
            "或在 launcher_config.json 中配置 claude_desktop_path。",
        )
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
    try:
        notify("Claude 启动器", "正在检测代理端口...")

        port = detect_proxy_port()
        if port is None:
            _icon.icon = make_icon(COLOR_ERROR)
            notify("⚠️ 未检测到代理", "请先开启科学上网工具，再重试")
            time.sleep(3)
            return

        set_proxy_env(port)
        notify(f"✅ 端口 {port} 就绪", f"正在启动 {label}...")

        for fn in fns:
            fn()
            time.sleep(1)

        _icon.icon = make_icon(COLOR_OK)
        time.sleep(3)
    finally:
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
        _icon.icon = make_icon(COLOR_WORKING)
        try:
            port = detect_proxy_port()
            if port:
                _icon.icon = make_icon(COLOR_OK)
                notify("代理状态", f"✅ 端口 {port} 正在监听")
            else:
                _icon.icon = make_icon(COLOR_ERROR)
                notify("代理状态", "❌ 未检测到可用代理端口")
            time.sleep(3)
        finally:
            _icon.icon = make_icon(COLOR_IDLE)
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

    # 按已安装的应用动态构建菜单
    has_vscode = _is_installed(VSCODE_PATH)
    has_claude = _is_installed(CLAUDE_DESKTOP_PATH)

    print(f"[启动] VS Code:        {VSCODE_PATH or '未检测到'}")
    print(f"[启动] Claude Desktop: {CLAUDE_DESKTOP_PATH or '未检测到'}")

    items = []
    if has_vscode and has_claude:
        items += [
            pystray.MenuItem("🚀 启动 VS Code + Claude Desktop",
                             action_launch_all, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("启动 VS Code（仅）",      action_launch_vscode),
            pystray.MenuItem("启动 Claude Desktop（仅）", action_launch_claude),
        ]
    elif has_vscode:
        items += [
            pystray.MenuItem("🚀 启动 VS Code", action_launch_vscode, default=True),
        ]
    elif has_claude:
        items += [
            pystray.MenuItem("🚀 启动 Claude Desktop", action_launch_claude, default=True),
        ]
    else:
        items += [
            pystray.MenuItem("⚠️ 未检测到 VS Code / Claude Desktop",
                             None, enabled=False),
            pystray.MenuItem("请安装后重启，或编辑 launcher_config.json",
                             None, enabled=False),
        ]

    items += [
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("检测代理状态", action_check_proxy),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", action_quit),
    ]

    menu = pystray.Menu(*items)

    _icon = pystray.Icon(
        "claude_launcher",
        make_icon(COLOR_IDLE),
        "Claude Code Launcher",
        menu,
    )
    _icon.run()


if __name__ == "__main__":
    main()
