# Claude Code Launcher

> 系统托盘小工具：自动检测本地代理端口，带代理环境变量启动 VS Code 和 Claude Desktop。
> 彻底解决中国大陆使用 Claude Code 时的 403 报错。

**支持平台：Windows / macOS / Linux**

[English](#english) | [中文](#中文)

---

## 中文

### 为什么需要这个工具

Claude Code 的 API 请求走 `api.anthropic.com`，和浏览器访问 `claude.ai` 是**两个不同端点**。

VS Code 和 Claude Desktop **默认不继承系统代理设置**，导致在国内直连被拒，报错：

```
403 {"type":"forbidden","message":"Request not allowed"}
```

本工具自动检测本地代理端口，注入正确的代理环境变量，再启动 VS Code / Claude Desktop，一步解决。

---

### 安装

#### 前置条件

1. **Python 3.10+**（没有请先到 [python.org](https://www.python.org/downloads/) 下载安装）
2. **安装 Python 依赖**（必须先执行，否则启动后托盘没有图标）：

```bash
pip install pystray pillow
```

#### 获取项目

```bash
git clone https://github.com/your-username/claude-code-launcher.git
cd claude-code-launcher
```

#### 创建桌面快捷方式

| 平台 | 命令 |
|------|------|
| Windows | 双击 `install_windows.bat` |
| macOS | `bash install_unix.sh` |
| Linux | `bash install_unix.sh` |

---

### 使用

1. 开启科学上网工具
2. 双击桌面快捷方式（或运行 `python3 claude_launcher.py`）
3. 系统托盘出现**节点光环图标**（深色背景 + 彩色分割环）
4. 右键 → 选择启动项（菜单内容随已安装的应用自动变化，见下表）

#### 托盘菜单按已安装应用动态调整

工具会检测三个目标：**VS Code**、**Claude Desktop**（含新版 MSIX / 老版 Squirrel）、**VS Code 里的 Claude Code 扩展**（`anthropic.claude-code-*`），按下表呈现菜单：

| 已安装组合 | 菜单项（★ 为默认双击项） |
|---|---|
| 仅 VS Code | ★ 🚀 启动 VS Code |
| 仅 Claude Desktop | ★ 🚀 启动 Claude Desktop |
| VS Code + Claude Desktop（无扩展） | ★ 🚀 启动 VS Code + Claude Desktop ／ 启动 VS Code（仅）／ 启动 Claude Desktop（仅） |
| VS Code + Claude Code 扩展 | ★ 🚀 启动 VS Code + Claude Code |
| 全部齐全 | ★ 🚀 启动 VS Code + Claude Code + Claude Desktop ／ 启动 VS Code + Claude Code（仅）／ 启动 Claude Desktop（仅） |
| 都没装 | ⚠️ 提示文字（不可点） |

### 托盘图标颜色含义

| 颜色 | 状态 |
|------|------|
| 🟣 紫色 | 待机就绪 |
| 🟡 黄色 | 正在检测代理端口 |
| 🟢 绿色 | 成功，应用已启动 |
| 🔴 红色 | 未检测到代理，请先开启科学上网 |

---

### 代理检测逻辑

1. **Windows**：读注册表 `HKCU\...\Internet Settings` 的 `ProxyServer`
2. **macOS**：读 `HTTP_PROXY` 环境变量，再查 `networksetup -getwebproxy`
3. **Linux**：读 `HTTP_PROXY` 环境变量，再查 `gsettings`
4. 以上都没有：扫描候选端口 `7890 / 7892 / 10809 / 1080 / 8080 ...`

**真实性校验**：候选端口仅"在监听"还不够——工具会再通过该端口对 `api.anthropic.com:443` 发一次 HTTP CONNECT 隧道，确认上游真的可达。绕过 Clash 的 fake-ip / 规则伪造，确保端口能用才设为代理。

---

### Windows Claude Desktop 路径自动识别

Anthropic 已切换到 **MSIX / AppX 应用商店格式**分发 Claude Desktop，安装路径形如：

```
C:\Program Files\WindowsApps\Claude_<version>_x64__pzs8sxrjxfjjc\app\Claude.exe
```

工具用 `Get-AppxPackage -Name Claude` 动态查询安装位置，无需手动配置。同时兼容老版 Squirrel 路径（`%LOCALAPPDATA%\AnthropicClaude\app-*\claude.exe`）。

> **注意**：通过 `shell:AppsFolder\...` 协议或开始菜单激活 AppX 应用时，**Windows AppX broker 会重置环境变量**，导致代理 env 丢失。本工具采用直接 `Popen` 绝对路径的方式，主进程及 renderer 子进程能完整继承代理 env。所以**必须从托盘启动 Claude Desktop**才有代理；直接点开始菜单的 Claude 图标不会带代理。

---

### 自定义配置

在脚本同目录创建 `launcher_config.json` 即可覆盖所有自动检测值（无需修改 `claude_launcher.py`）：

```json
{
  "vscode_path": "D:\\Tools\\VSCode\\Code.exe",
  "claude_desktop_path": "",
  "default_project_dir": "D:\\projects",
  "candidate_ports": [7892]
}
```

- 任一字段留空或省略，回退到自动检测
- `candidate_ports` 写成单元素数组可**锁定代理端口**，避免回退扫描时被其他端口误选
- 此文件已被 `.gitignore` 忽略（机器特定，不入仓）

---

### 常见代理工具端口

| 工具 | HTTP 端口 |
|------|----------|
| Clash / Clash Verge | 7890 |
| V2rayN | 10809 |
| Shadowsocks | 1080 |
| Surge | 6152 |

---

### Linux 额外说明

- 官方 Claude Desktop 暂无 Linux 版本，Linux 用户建议使用 VS Code + Claude Code 插件
- 托盘图标需要 `libappindicator`：
  ```bash
  # Ubuntu / Debian
  sudo apt install gir1.2-appindicator3-0.1
  # Fedora
  sudo dnf install libappindicator-gtk3
  ```

---

### 贡献

欢迎提 Issue 和 PR，特别欢迎：
- 更多代理工具的自动识别
- 开机自启支持

---

## English

### What this does

Claude Code's API calls go to `api.anthropic.com` — a different endpoint from `claude.ai`. In mainland China, VS Code and Claude Desktop **do not inherit system proxy settings**, resulting in:

```
403 {"type":"forbidden","message":"Request not allowed"}
```

This tray tool auto-detects your local proxy port, injects `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY`, and launches VS Code / Claude Desktop with those variables set.

---

### Install

**Requires Python 3.10+**

```bash
git clone https://github.com/your-username/claude-code-launcher.git
cd claude-code-launcher
```

| Platform | Command |
|----------|---------|
| Windows  | Double-click `install_windows.bat` |
| macOS    | `bash install_unix.sh` |
| Linux    | `bash install_unix.sh` |

---

### Usage

1. Start your proxy tool
2. Launch the app from your desktop shortcut (or `python3 claude_launcher.py`)
3. Find the **node-ring icon** (dark background with colored segmented ring) in your system tray
4. Right-click → pick a launch item (menu adapts to what's installed, see below)

#### Tray menu adapts to installed apps

The launcher detects three targets: **VS Code**, **Claude Desktop** (new MSIX *and* legacy Squirrel format), and the **Claude Code extension** inside VS Code (`anthropic.claude-code-*`). The menu is built accordingly:

| Installed | Menu items (★ = default) |
|---|---|
| VS Code only | ★ 🚀 Launch VS Code |
| Claude Desktop only | ★ 🚀 Launch Claude Desktop |
| VS Code + Claude Desktop (no extension) | ★ 🚀 Launch VS Code + Claude Desktop ／ Launch VS Code only ／ Launch Claude Desktop only |
| VS Code + Claude Code extension | ★ 🚀 Launch VS Code + Claude Code |
| All three | ★ 🚀 Launch VS Code + Claude Code + Claude Desktop ／ Launch VS Code + Claude Code only ／ Launch Claude Desktop only |
| Nothing detected | ⚠️ Disabled message |

### Icon colors

| Color | Meaning |
|-------|---------|
| 🟣 Purple | Idle |
| 🟡 Yellow | Detecting proxy port |
| 🟢 Green  | Success |
| 🔴 Red    | No proxy found — start your proxy tool first |

---

### Proxy detection

1. **Windows** — reads registry `ProxyServer` value
2. **macOS** — checks `HTTP_PROXY` env var, then `networksetup -getwebproxy`
3. **Linux** — checks `HTTP_PROXY` env var, then `gsettings`
4. Fallback — scans `CANDIDATE_PORTS` list with a 300ms socket timeout

**Liveness check**: a listening port isn't enough — the launcher opens an HTTP CONNECT tunnel to `api.anthropic.com:443` through each candidate to confirm the upstream is actually reachable. This avoids being fooled by Clash fake-ip / rule-based local responders.

---

### Windows: Claude Desktop path auto-detection

Anthropic now ships Claude Desktop as an **MSIX / AppX Store package**:

```
C:\Program Files\WindowsApps\Claude_<version>_x64__pzs8sxrjxfjjc\app\Claude.exe
```

The launcher resolves the install location dynamically via `Get-AppxPackage -Name Claude` — no manual config needed. The legacy Squirrel path (`%LOCALAPPDATA%\AnthropicClaude\app-*\claude.exe`) is also still supported.

> **Caveat**: activating an AppX app through `shell:AppsFolder\...` or the Start menu causes Windows to **reset environment variables** in the new process — proxy env is lost. The launcher works around this by launching the absolute Claude.exe path directly with `Popen`, so the main process and renderers inherit proxy env correctly. This means **you must launch Claude Desktop from the tray** to get proxy injection; double-clicking the Start menu icon will not.

---

### Custom config

Drop a `launcher_config.json` next to the script to override any auto-detected value (no need to edit `claude_launcher.py`):

```json
{
  "vscode_path": "D:\\Tools\\VSCode\\Code.exe",
  "claude_desktop_path": "",
  "default_project_dir": "D:\\projects",
  "candidate_ports": [7892]
}
```

- Any empty/missing field falls back to auto-detection
- A single-element `candidate_ports` array **locks the proxy port**, preventing the fallback scan from picking up a different one
- The file is in `.gitignore` (machine-specific, not committed)

---

### License

MIT © 2026 Su NanNan
