# File Control Center — 开源扩展规划

## Context

file-control-center 是一个 Python 单进程家庭服务器中控台（端口 1288），目前功能包括文件浏览/HTTP分发、下载监控、服务控制、DDNS、ShareClip剪贴板、SSH Terminal、目录清理。

项目目标：**开源到 GitHub**，支持 Ubuntu / Linux Mint / macOS 自动安装，让淘汰笔记本和放弃 OpenClaw 的 Mac Mini 发挥剩余价值。用户希望**一步到位重构**后再开源，并逐步加入系统监控、Docker 管理、多节点联动等功能。

---

## Phase 0: 一步到位重构（核心，所有后续工作的基础）

### 目标结构

```
file-control-center/
├── fcc/                          # 主包（File Control Center）
│   ├── __init__.py               # 版本号、包元信息
│   ├── __main__.py               # python3 -m fcc 入口
│   ├── server.py                 # HTTPServer + 请求分发器（替代 app.py 的 AppHandler）
│   ├── config.py                 # 统一配置系统（合并 env vars + app_config.json）
│   ├── platform.py               # 平台检测（OS、init system、包管理器）
│   ├── security.py               # _require_lan()、path traversal 等安全逻辑
│   │
│   ├── modules/                  # 功能模块（每个可独立 enable/disable）
│   │   ├── __init__.py           # 模块注册表 + enable/disable 机制
│   │   ├── files/                # 文件浏览 + HTTP 分发
│   │   │   ├── __init__.py
│   │   │   ├── routes.py         # 路由处理
│   │   │   ├── service.py        # 业务逻辑（流式传输、Range、速度统计）
│   │   │   └── templates.py      # HTML 生成
│   │   ├── downloads/            # 下载控制（统一开关语义）
│   │   │   ├── __init__.py
│   │   │   ├── routes.py
│   │   │   └── service.py        # 统一的下载开关：单一 enabled 状态 + cut epoch
│   │   ├── services/             # 服务控制（qBittorrent/DDNS/self）
│   │   │   ├── __init__.py
│   │   │   ├── routes.py
│   │   │   └── service.py
│   │   ├── ddns/                 # 现有 ddns/ 整合进来
│   │   │   └── ...（保持现有结构）
│   │   ├── shareclip/            # 现有 shareclip/ 整合
│   │   │   └── ...
│   │   ├── terminal/             # SSH Terminal
│   │   │   ├── __init__.py
│   │   │   ├── routes.py
│   │   │   └── pty_session.py    # PTY 逻辑，带平台检测
│   │   ├── naming/               # 目录清理/重命名
│   │   │   └── ...
│   │   ├── monitor/              # [新] 系统监控
│   │   ├── docker/               # [新] Docker 管理
│   │   └── nodes/                # [新] 多节点联动
│   │
│   └── web/                      # 前端资源
│       ├── templates/            # HTML 模板（从 app.py 内联字符串提取）
│       │   ├── base.html
│       │   ├── dashboard.html
│       │   ├── config.html
│       │   ├── terminal.html
│       │   └── ddns.html
│       ├── static/
│       │   ├── css/dashboard.css
│       │   ├── js/               # 从内联 JS 提取
│       │   └── vendor/xterm/
│       └── renderer.py           # 模板渲染（简单字符串格式化，不引入 Jinja）
│
├── install.sh                    # 跨平台安装入口
├── scripts/
│   ├── detect_platform.sh        # OS/init-system 检测
│   ├── install_ubuntu.sh         # Ubuntu/Debian 安装
│   ├── install_mint.sh           # Mint 安装（基于 Ubuntu，微调）
│   ├── install_macos.sh          # macOS 安装（brew + launchd）
│   └── uninstall.sh              # 卸载脚本
├── tests/                        # 测试套件
│   ├── test_security.py
│   ├── test_config.py
│   ├── test_files.py
│   ├── test_downloads.py
│   └── ...
├── requirements.txt
├── pyproject.toml                # 现代 Python 打包
├── LICENSE
├── README.md                     # 英文为主，中文跟随
├── DEPLOY.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── .github/
│   └── workflows/
│       ├── test.yml              # 多平台 CI
│       └── release.yml
└── .env.example
```

### 下载开关语义统一

**当前问题**：`modules.http`（模块级）和 `downloads_enabled`（运行态）两个开关含义重叠。

**统一方案**：
- 保留 `modules.http` 作为"HTTP 文件服务模块总开关"（关闭 = 整个 `/http-files/` 不可用，同时触发 cut epoch 断开活跃连接）
- `downloads_enabled` 改名为 `http_accepting_new`，语义明确为"是否接受新下载请求"（不影响已有连接）
- UI 上只暴露一个主开关（模块开关），高级用户可通过 API 单独控制 `http_accepting_new`

### 模块注册机制

```python
# fcc/modules/__init__.py
class Module:
    name: str
    routes: list          # (method, path_pattern, handler)
    enabled: bool         # 从 config 读取
    platforms: list       # ['linux', 'darwin', 'all']

REGISTRY: dict[str, Module] = {}

def register(module: Module):
    REGISTRY[module.name] = module
```

每个模块的 `__init__.py` 调用 `register()` 注册自己。`server.py` 启动时遍历 REGISTRY 构建路由表。

### 关键文件

- `app.py` → 拆分为 `fcc/server.py`（路由分发）+ 各 `modules/*/routes.py`（具体处理）
- 内联 HTML/CSS/JS → 提取到 `fcc/web/templates/` 和 `fcc/web/static/`
- 保留 `app.py` 作为兼容入口（`from fcc.__main__ import main; main()`）

---

## Phase 1: 跨平台安装系统

### 平台检测

`install.sh` 作为统一入口：

```bash
#!/usr/bin/env bash
# 检测平台 → 分发到对应安装脚本
OS="$(uname -s)"
case "$OS" in
  Linux)
    if [ -f /etc/os-release ]; then
      . /etc/os-release
      case "$ID" in
        ubuntu|debian) bash scripts/install_ubuntu.sh "$@" ;;
        linuxmint)     bash scripts/install_mint.sh "$@" ;;
        *)             echo "不支持的 Linux 发行版: $ID"; exit 1 ;;
      esac
    fi ;;
  Darwin)
    bash scripts/install_macos.sh "$@" ;;
  *)
    echo "不支持的操作系统: $OS"; exit 1 ;;
esac
```

### macOS 安装（launchd）

`scripts/install_macos.sh`:
- 用 `brew install python3` 或检测系统 Python3
- pip install 依赖
- 写入 `~/Library/LaunchAgents/com.fcc.file-control-center.plist`
- `launchctl load` 启动服务
- 数据目录默认 `~/fcc-data/`（macOS 没有 `/srv`）

### 平台差异抽象

在 `fcc/platform.py` 中：

| 功能 | Linux | macOS |
|------|-------|-------|
| 服务管理 | `systemctl` | `launchctl` |
| 默认存储 | `/srv/Storage` | `~/fcc-data/Storage` |
| 应用目录 | `/opt/storage-http-link-web` | `/usr/local/opt/fcc` |
| 包管理 | `apt` | `brew` |
| Docker socket | `/var/run/docker.sock` | `~/.docker/run/docker.sock` |
| 温度传感器 | `/sys/class/thermal/` | `powermetrics` / IOKit |

### qBittorrent-nox 安装支持

在安装脚本中可选安装 qBittorrent-nox：
- Ubuntu/Mint: `apt install qbittorrent-nox` + 创建 systemd service
- macOS: `brew install qbittorrent-nox`
- 安装后自动配置 WebUI 凭据到 `.env`

---

## Phase 2: 系统监控模块

### 依赖

新增 `psutil`（跨平台系统信息库，支持 Linux/macOS/Windows）

### 功能

```
fcc/modules/monitor/
├── __init__.py
├── routes.py           # GET /api/monitor/stats, /api/monitor/history
├── service.py          # 采集逻辑
└── collectors/
    ├── cpu.py          # CPU 使用率、频率、核心数
    ├── memory.py       # 内存/Swap 使用
    ├── disk.py         # 磁盘使用率、IO 速率
    ├── network.py      # 网络接口流量
    └── temperature.py  # CPU/GPU 温度（平台适配）
```

### API

- `GET /api/monitor/stats` — 当前快照（CPU%、内存%、磁盘、网络速率、温度）
- `GET /api/monitor/history?minutes=60` — 最近 N 分钟的时序数据
- `GET /api/monitor/disks` — 挂载点列表 + 用量

### 数据存储

内存环形缓冲区（最近 24 小时，每 5 秒采样），不持久化。重启后从零开始。

---

## Phase 3: Docker 管理模块

### 依赖

`docker` Python SDK（或直接调用 Docker CLI — 考虑到轻量需求，优先用 CLI `subprocess`）

### 功能

```
fcc/modules/docker/
├── __init__.py
├── routes.py
├── service.py          # Docker CLI 封装
└── compose.py          # docker compose 操作
```

### API

- `GET /api/docker/containers` — 容器列表（状态、端口、资源占用）
- `POST /api/docker/containers/<id>/start|stop|restart`
- `GET /api/docker/containers/<id>/logs?tail=100`
- `GET /api/docker/images` — 镜像列表
- `GET /api/docker/compose/services` — compose 项目状态
- `POST /api/docker/compose/<project>/up|down`

### 平台适配

- Linux: `docker` CLI 直接可用
- macOS: 需检测 Docker Desktop 或 colima

---

## Phase 4: 多节点联动

### 架构

采用 **星型拓扑**：一个节点作为"主控"，其他为"受控节点"。

```
fcc/modules/nodes/
├── __init__.py
├── routes.py           # 主控面板 API
├── agent.py            # 受控节点上报 agent
├── discovery.py        # mDNS/手动注册
└── sync.py             # 配置/状态同步
```

### 通信协议

- 受控节点定期向主控 HTTP POST 上报状态（系统信息、服务状态、在线状态）
- 主控可通过 HTTP API 下发指令到受控节点
- 使用共享密钥（`FCC_CLUSTER_SECRET` 环境变量）签名请求
- 发现机制：手动配置节点地址列表 或 mDNS 自动发现（`zeroconf` 库）

### 主控面板

- 统一 dashboard 显示所有节点状态
- 聚合监控数据（各节点 CPU/内存/磁盘）
- 跨节点文件浏览（通过 API 代理）
- 批量服务控制

---

## Phase 5: 开源准备

### 仓库规范

- **License**: MIT（最宽松，鼓励使用和二次开发）
- **README.md**: 双语（English 为主，中文 section）
  - Feature overview + screenshots
  - One-command install for each platform
  - Configuration reference
  - Architecture diagram
- **CONTRIBUTING.md**: 开发环境搭建、提交规范、PR 流程
- **CHANGELOG.md**: Keep a Changelog 格式

### CI/CD（GitHub Actions）

```yaml
# .github/workflows/test.yml
- 矩阵测试: ubuntu-22.04, ubuntu-24.04, macos-13 (Intel), macos-14 (ARM)
- Python 3.9, 3.10, 3.11, 3.12
- 运行 pytest 测试套件
- 代码风格检查 (ruff)
```

```yaml
# .github/workflows/release.yml
- tag 触发
- 生成 release notes
- 构建 tarball
```

### 版本策略

- SemVer: `MAJOR.MINOR.PATCH`
- v1.0.0 = Phase 0 + Phase 1 完成（重构 + 跨平台安装）
- v1.1.0 = 系统监控
- v1.2.0 = Docker 管理
- v2.0.0 = 多节点联动

---

## 执行顺序与里程碑

| 阶段 | 内容 | 验收标准 |
|------|------|----------|
| **Phase 0** | 一步到位重构 | app.py 拆分完成；所有现有功能正常；模块注册机制工作；单一下载开关语义；基本测试通过 |
| **Phase 1** | 跨平台安装 | Ubuntu/Mint/macOS 一键安装成功；launchd plist 工作；qBittorrent-nox 可选安装 |
| **Phase 5a** | 开源基础 | README/LICENSE/CONTRIBUTING 就位；GitHub Actions CI 绿色；首次 tag v1.0.0 |
| **Phase 2** | 系统监控 | 监控面板显示 CPU/内存/磁盘/温度；Ubuntu 和 macOS 数据正确 |
| **Phase 3** | Docker 管理 | 容器列表/启停/日志可用；compose 支持 |
| **Phase 4** | 多节点联动 | 两台设备互联成功；主控面板显示全部节点状态 |

### 每个 Phase 的验证方式

- **Phase 0**: 在 macOS 开发环境 `python3 -m fcc` 启动，访问所有页面和 API，对比现有 `app.py` 功能
- **Phase 1**: 在 Ubuntu VM + macOS 分别执行 `bash install.sh`，验证服务启动和功能
- **Phase 2-4**: 各自的 API 端点测试 + UI 交互验证
- **持续**: `pytest tests/` 覆盖安全边界和核心逻辑

---

## 新增依赖（全计划）

| 依赖 | 用途 | 阶段 |
|------|------|------|
| `psutil` | 系统监控 | Phase 2 |
| `zeroconf`（可选） | mDNS 节点发现 | Phase 4 |

保持最小依赖原则。主框架继续用 stdlib `http.server`，不引入 FastAPI/Django 等重框架。
