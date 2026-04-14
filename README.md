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
4. 右键 → **启动 VS Code + Claude Desktop**

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

---

### 自定义配置

用文本编辑器打开 `claude_launcher.py`，修改顶部配置区：

```python
# VS Code 路径（通常自动检测，无需修改）
VSCODE_PATH = _default_vscode()

# Claude Desktop 路径
CLAUDE_DESKTOP_PATH = _default_claude_desktop()

# 默认打开的项目目录（留空则不指定）
DEFAULT_PROJECT_DIR = ""

# 候选代理端口扫描列表
CANDIDATE_PORTS = [7890, 7891, 7892, 7893, 10809, 10808, 1080, 8080, 8118]
```

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
4. Right-click → **Launch VS Code + Claude Desktop**

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

---

### License

MIT © 2026 Su NanNan
