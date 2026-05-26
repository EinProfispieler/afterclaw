# AfterClaw 修复与分拆执行计划

更新时间：2026-05-26  
适用仓库：`/Users/randy/afterclaw`

## 1. 目标与原则

目标：
- 先修复会直接影响可用性的 P1 问题。
- 再把 `app.py` 的系统调用、配置模型、业务模块逐步拆分，降低耦合和回归风险。

执行原则：
- 小步提交，阶段化验收，不做大爆炸重构。
- 每阶段都有明确“完成定义（DoD）”。
- API 返回结构优先保持兼容。

## 2. 当前问题清单（输入）

- P1：`process-net` 速率统计键不一致，增量统计失真。
- P1：`web/ui` 依赖的 React/Babel vendor 资产缺失，存在白屏风险。
- P1：重启逻辑硬编码 `systemctl`，与 macOS `launchctl` 路径不一致。
- P2：`fcc` 模块层与 `app.py` 仍是过渡态，职责边界不清。
- P2：`app.py` 与 `fcc.config` 配置模型双轨，存在漂移风险。
- P2：Backup 模块入口、文档、启用状态不一致。

## 3. 主文件集成面盘点（补全分拆范围）

当前 `app.py` 不是单一 HTTP handler，而是“多子系统聚合”：
- 路由与页面渲染：`/`、`/config`、`/terminal`、`/member`、`/process-net`、静态资源。
- 文件服务：目录扫描、文件列表、`/http-files/*` 分片下载、并发下载门控。
- Docker 管控：容器/镜像列表、日志、拉取、创建、删除、动作执行。
- qBittorrent 侧：服务探测、docker 容器探测、配置修复、挂载检查、优化动作。
- DDNS：内置 DDNS 配置、执行、状态整形、ddns-go 代理桥。
- Terminal：会话生命周期、读写、resize、历史、密钥文件。
- Member：登录/注册/资料/密码重置/DDNS 前缀校验。
- Upgrade：版本检查、升级任务调度、状态持久化。
- 命名与字幕：清理预览/应用、字幕上传、字幕对齐预览/应用。
- UI 主题与资源：i18n、主题背景上传、静态资产分发。
- 跨模块控制：服务重启、模块开关、控制面板聚合状态。

结论：要分拆的不只是“docker/service/tools”，而是上述 10+ 子域。

## 4. 目标目录结构（拆分落点）

目标是让 `app.py` 退化为“装配入口 + server 启动”，业务逻辑落到 `fcc` 内：

```text
fcc/
  runtime/
    server.py                 # HTTPServer 启动与生命周期
    router.py                 # 路由注册与分发
    request.py                # 请求解析与通用响应
    authz.py                  # LAN/http-access 访问控制
    adapters/
      service_adapter.py      # systemctl/launchctl 抽象
      docker_adapter.py       # docker CLI 抽象
      process_adapter.py      # ss/proc/netstat 抽象
  api/
    base_api.py
    files_api.py
    docker_api.py
    qbt_api.py
    ddns_api.py
    terminal_api.py
    member_api.py
    upgrade_api.py
    naming_api.py
    subtitles_api.py
    theme_api.py
  domain/
    config_schema.py          # 单一配置真源 + 迁移
    control_status.py         # /api/control/status 聚合逻辑
```

说明：
- `app.py` 最终只保留兼容入口（`python3 app.py`）并委托 `fcc.runtime.server`。
- 模块注册机制继续保留，但逐步从占位升级为真实 API handler。

## 5. 分拆批次（避免漏项）

分拆按“低耦合优先、外部副作用可控优先”执行：

### 批次 A：基础设施层
- A1 路由分发表抽取（不改业务逻辑，只改分发形态）。
- A2 通用请求/响应工具抽取（json/html/error/static）。
- A3 系统调用 adapter 抽取（service/docker/process）。

### 批次 B：读接口优先
- B1 `base/speed/metrics/transfers/process-net`。
- B2 `directories/files/http path scan`。
- B3 `docker read APIs`：containers/logs/images/recommendations。

### 批次 C：写接口分域迁移
- C1 `docker write APIs`：action/image pull/container create/remove/image remove。
- C2 `qbt fix/optimize/discover`。
- C3 `ddns config/run`。
- C4 `terminal start/read/write/resize/history/key-file`。
- C5 `member` 全链路。
- C6 `clean/subtitle` 预览与应用。
- C7 `upgrade` 执行与状态。

### 批次 D：页面与静态
- D1 `/` `/config` `/terminal` `/member` 页面渲染入口。
- D2 静态资源策略（vendor/ui/locales/theme-assets）统一。

### 批次 E：收尾
- E1 Backup 状态统一（完整启用或完整下线）。
- E2 `app.py` 精简到兼容壳层。
- E3 文档同步（README + docs）。

## 6. 分阶段执行

## 阶段 0：基线与护栏

- [x] 0.1 新增回归测试骨架（覆盖本次 P1 修复点）。
- [x] 0.2 固化 smoke 清单（首页、配置页、docker API、重启 API）。
- [x] 0.3 确认现有测试全绿。

DoD：
- `python3 -m pytest -q` 通过。
- 能用测试复现至少一个待修复问题（修复前失败、修复后通过）。

阶段 0 当前基线（2026-05-26）：
- `python3 -m pytest -q` => `30 passed, 2 xfailed`
- `2 xfailed` 为已登记回归骨架（`process-net` 键不一致、UI vendor 资产缺失）。

阶段 1.1 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `31 passed, 1 xfailed`
- 已消除 `process-net` 键不一致回归；剩余 `1 xfailed` 为 UI vendor 资产缺失问题。

阶段 1.2 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `32 passed`
- `web/ui` 依赖资产已本地化（`web/vendor`），并保留缺资产兜底回退逻辑。

阶段 1.3 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `42 passed`
- 重启逻辑已按平台分发：Linux 使用 `systemctl`，macOS 使用 `launchctl`，不支持平台返回明确错误信息。

阶段 1.4 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `37 passed`
- 升级流程新增 `script_source` 机制，可从 GitHub/HTTP 升级源拉取第三方升级脚本（依赖补丁等）并在安装后执行。

阶段 2.1 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `46 passed`
- 已创建 `fcc/runtime/adapters/` 与 `service_adapter.py`、`docker_adapter.py`、`process_adapter.py`，作为后续系统调用迁移落点。

阶段 2.2 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `47 passed`
- `app.py` 中 service/docker 路径的直接 `subprocess.run` 已迁移至 `fcc/runtime/adapters/*`，并新增防回流测试。

阶段 2.3 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `49 passed`
- `app.py` 不再直接调用 `subprocess.run`，系统命令执行下沉到 adapter，主文件仅保留编排和状态流转。

阶段 3.1 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `51 passed`
- 已新增 `fcc/config_schema.py` 作为统一配置 schema 定义（版本、模块键、qB 客户端键、网盘源键及默认块），并被 `app.py` 与 `fcc/config.py` 复用。

阶段 3.2 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `52 passed`
- `default_app_config` 与 `normalize_app_config` 已改为单实现路径：默认配置通过 `normalize_app_config({})` 生成，避免双轨漂移。

阶段 3.3 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `54 passed`
- 已增加配置版本迁移入口（`_migrate_app_config_payload`），并接入 `load/save` 链路，支持旧版配置字段迁移到当前版本。

阶段 4.1.1 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `54 passed`
- Docker 读接口（`containers/logs/recommendations/images`）已从 `app.py` 抽到 `fcc/modules/docker/api.py`，`app.py` 改为统一分发调用。

阶段 4.1.2 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `54 passed`
- smoke 已升级为 Docker 路由契约检查（从 `app.py` + `fcc/modules/docker/api.py` 聚合扫描），避免依赖主文件硬编码分支文本，并持续覆盖写接口存在性。
- Docker 写接口（`action/image pull/container create/remove/image remove`）已迁移到 `fcc/modules/docker/api.py`，`app.py` 通过 `_dispatch_docker_post_api` 统一分发。

阶段 4.1.3 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `62 passed`
- 已新增 `fcc/modules/docker/service.py`，并将 Docker 领域逻辑（状态聚合、镜像查询、容器日志、输入校验、命令构建）从 `app.py` 下沉为服务函数。
- `app.py` 中 Docker 相关方法已改为薄封装委派，主文件不再承载该子域的核心实现细节。

阶段 4.1.4 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `62 passed`
- 新增 Docker 分域测试：`tests/test_docker_service.py` 与 `tests/test_docker_api_dispatch.py`，覆盖读写接口关键路径与错误路径。
- 现有 smoke + 分域单测共同约束 Docker 路由契约与服务行为，降低后续迁移回归风险。

阶段 4.2.1 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `66 passed`
- `/api/control/service` 已从 `app.py` `do_POST` 主流程抽到 `fcc/modules/services/api.py` 分发层。
- `app.py` 通过 `_dispatch_services_post_api` 统一委派，服务控制路由迁移进入模块化通道。

阶段 4.2.2 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `70 passed`
- DDNS `config/run` 读写路由已抽到 `fcc/modules/ddns/api.py`（`dispatch_get` + `dispatch_post`）。
- `app.py` 新增 `_dispatch_ddns_get_api` 与 `_dispatch_ddns_post_api`，并移除主流程内对应 DDNS 路由分支。

阶段 4.2.3 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `74 passed`
- 新增 `fcc/modules/services/service.py` 与 `fcc/modules/ddns/service.py`，将 service/ddns 控制动作与 DDNS 配置执行逻辑下沉到 service 层。
- `fcc/modules/services/api.py` 与 `fcc/modules/ddns/api.py` 仅保留分发与协议层，控制动作改为调用 service 函数。

阶段 4.2.4 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `74 passed`
- 新增 `tests/test_services_api_dispatch.py`、`tests/test_ddns_api_dispatch.py`、`tests/test_service_domain_layers.py`，覆盖 service/ddns 权限拒绝、参数校验、错误路径与关键成功路径回归。

阶段 4.3.1 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `78 passed`
- terminal 会话相关 POST 路由（start/sessions/history/read/write/resize/close/revoke）已迁移到 `fcc/modules/terminal/api.py` 分发层。
- `app.py` 新增 `_dispatch_terminal_post_api` 并移除对应主流程分支，保留 `key-file` 路由待 4.3.3 处理。

阶段 4.3.2 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `81 passed`
- terminal 会话读写/resize/close 等动作已下沉到 `fcc/modules/terminal/service.py` 统一入口（API 层只做协议转换与错误映射）。

阶段 4.3.4 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `81 passed`
- 已新增 `tests/test_terminal_api_dispatch.py` 与 `tests/test_terminal_service_layer.py`，覆盖 terminal 生命周期关键路径与异常路径（含缺少 session_id、写入异常等）。

阶段 4.3.3 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `83 passed`
- `/api/terminal/key-file` 上传与配置写回逻辑已迁移到 `fcc/modules/terminal/api.py` + `fcc/modules/terminal/service.py`。
- `app.py` 不再持有 terminal key-file 路由实现细节。

阶段 4.4.1 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `86 passed`
- member 登录/注册/profile/logout 路由分发已抽到 `fcc/modules/member/api.py`，`app.py` 改为 `_dispatch_member_get_api/_dispatch_member_post_api`。
- 为 4.4.2/4.4.3 预留了 member 路由扩展位，先保持原业务逻辑不变。

阶段 4.4.2 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `86 passed`
- member `email-change/password-reset/ddns-config`（含 `ddns/prefix-check`）路由分发已纳入 `fcc/modules/member/api.py`。
- `app.py` 主流程移除对应 member 分支，改为统一委派 member 路由入口。

阶段 4.4.3 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `94 passed`
- 新增 `fcc/modules/member/service.py`，将 member 鉴权会话、远程调用封装、ddns 前缀校验/变更等逻辑下沉为可复用服务函数。
- `app.py` 中 member 路由处理函数改为薄封装：只负责 LAN gate、错误响应、cookie 头输出。

阶段 4.4.4 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `94 passed`
- 新增 `tests/test_member_service.py`，覆盖 member 核心流程与失败路径（session 缺失、参数缺失、上游会话缺失、prefix 冲突等）。
- 现有 `tests/test_member_api_dispatch.py` 保持路由分发契约覆盖，member API + service 双层回归完成。

阶段 4.5.1 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `101 passed`
- `clean preview/apply` 路由分发已从 `app.py` 主流程抽取到 `fcc/modules/naming/api.py`。

阶段 4.5.2 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `101 passed`
- `subtitles upload/align preview/apply` 路由分发已迁移到 `fcc/modules/naming/api.py`。

阶段 4.5.3 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `101 passed`
- 新增 `fcc/modules/naming/service.py`，承接 naming/subtitles 业务逻辑、参数校验与错误状态映射。
- `app.py` 命名/字幕域改为统一 `_dispatch_naming_post_api` 委派。

阶段 4.5.4 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `101 passed`
- 新增 `tests/test_naming_service.py` 与 `tests/test_naming_api_dispatch.py`，覆盖 naming/subtitles 回归路径（参数错误、分发命中、成功返回）。

阶段 4.6.1 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `107 passed`
- upgrade `status/check-version/run` 路由已抽到 `fcc/modules/upgrade/api.py`，`app.py` 通过 `_dispatch_upgrade_get_api/_dispatch_upgrade_post_api` 委派。

阶段 4.6.2 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `107 passed`
- 新增 `fcc/modules/upgrade/service.py`，封装升级任务调度入口（含 `branch/script_source` 参数校验与错误状态映射）。

阶段 4.6.3 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `107 passed`
- 新增 `tests/test_upgrade_api_dispatch.py` 与 `tests/test_upgrade_service_layer.py`，并与 `tests/test_upgrade_script_source.py` 共同覆盖 upgrade 正常/异常路径。

阶段 4.7.1 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `108 passed`
- 已盘点 Backup 对外暴露面：主页面 Backup tab/panel、Config Backup tab/panel、前端 `/api/backup/*` 调用、`fcc/modules/backup/README.md` 对外接口说明。

阶段 4.7.2 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `108 passed`
- 选择“完整下线”策略并实施：从 `app.py` 前端模板中移除 Backup tab/panel、Config backup panel、相关事件绑定和 `/api/backup/*` 前端调用逻辑。

阶段 4.7.3 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `108 passed`
- 新增 `tests/test_backup_surface_disabled.py`，持续校验 `app.py` 不再暴露 Backup 假入口（tab/panel/api 字符串）。
- 更新 `fcc/modules/backup/README.md` 状态说明：当前 release 默认禁用，仅保留模块内部实现文档。

## 阶段 1：P1 修复

- [x] 1.1 修复 `process_net` socket key 读写不一致问题。
- [x] 1.2 处理 `web/ui` vendor 依赖缺失：
  - 方案 A：补齐本地 vendor 静态资产；
  - 方案 B：改为可控构建产物（不依赖运行时 Babel）。
- [x] 1.3 抽象服务重启分发：
  - Linux 走 `systemctl`；
  - macOS 走 `launchctl`；
  - 不支持平台返回明确错误。
- [x] 1.4 升级系统增强：
  - `/api/upgrade/run` 支持透传 `script_source`；
  - 升级后可按分支/tag 从 GitHub 或 HTTP 升级源拉取并执行第三方脚本；
  - 升级状态记录 hook 执行状态与错误信息（`hook_state/hook_url/hook_message/hook_error`）。

DoD：
- 新增/更新测试覆盖 1.1、1.3。
- 干净环境下 UI 不因 vendor 缺失白屏。
- Linux/macOS 重启 API 行为与安装方式一致。

## 阶段 2：运行时适配层（先薄封装）

- [x] 2.1 新建 `fcc/runtime/adapters/`：
  - `service_adapter.py`
  - `docker_adapter.py`
  - `process_adapter.py`（如需要）
- [x] 2.2 把 `app.py` 中直接 `subprocess` 调用迁到 adapter。
- [x] 2.3 `app.py` 保留编排，不直接拼系统命令。

DoD：
- 核心系统调用均经 adapter。
- 行为不变（接口字段兼容）。

## 阶段 3：配置模型单一真源

- [x] 3.1 抽出统一 schema（建议 `fcc/config_schema.py`）。
- [x] 3.2 `default_app_config` + `normalize_app_config` 合并为单实现。
- [x] 3.3 增加配置版本迁移入口。

DoD：
- `app.py` 与 `fcc.config` 不再维护两套默认配置。
- 同一份配置输入得到一致归一化结果。

## 阶段 4：业务模块逐步迁移

- [x] 4.1 Docker 路由与逻辑迁移
  - [x] 4.1.1 抽取 Docker 读接口分发（containers/logs/recommendations/images）。
  - [x] 4.1.2 抽取 Docker 写接口分发（action/image pull/container create/remove/image remove）。
  - [x] 4.1.3 抽取 Docker 领域逻辑服务层（状态聚合、镜像查询、容器日志）。
  - [x] 4.1.4 为 Docker 路由新增分域测试（读写接口 + 错误路径）。
- [x] 4.2 Service/DDNS 控制逻辑迁移
  - [x] 4.2.1 抽取 `/api/control/service` 分发层。
  - [x] 4.2.2 抽取 DDNS config/run 分发层。
  - [x] 4.2.3 将 service/ddns 控制动作迁到独立模块服务函数。
  - [x] 4.2.4 覆盖 service/ddns 的权限与错误回归测试。
- [x] 4.3 Terminal 路由与会话管理迁移
  - [x] 4.3.1 抽取 terminal GET/POST 路由分发层。
  - [x] 4.3.2 抽取会话读写/resize/close 的服务入口。
  - [x] 4.3.3 抽取 key-file 上传/列举/删除逻辑。
  - [x] 4.3.4 覆盖 terminal 生命周期与异常路径测试。
- [x] 4.4 Member 路由与鉴权会话迁移
  - [x] 4.4.1 抽取 member 登录/注册/profile/logout 路由分发。
  - [x] 4.4.2 抽取 email-change/password-reset/ddns-config 路由分发。
  - [x] 4.4.3 提炼 member 鉴权会话服务接口。
  - [x] 4.4.4 覆盖 member 核心流程与鉴权失败测试。
- [x] 4.5 Naming/Subtitles 路由迁移
  - [x] 4.5.1 抽取 clean preview/apply 路由分发。
  - [x] 4.5.2 抽取 subtitle upload/align preview/apply 路由分发。
  - [x] 4.5.3 提炼 naming/subtitles 处理服务层。
  - [x] 4.5.4 覆盖 naming/subtitles 回归测试。
- [x] 4.6 Upgrade 路由与调度迁移
  - [x] 4.6.1 抽取 upgrade status/check-version/run 路由分发。
  - [x] 4.6.2 提炼升级任务调度服务入口（含 script_source/hook 状态）。
  - [x] 4.6.3 覆盖 upgrade 正常/异常/并发场景测试。
- [x] 4.7 统一 Backup 状态
  - [x] 4.7.1 确认当前 Backup 对外暴露面（UI/API/文档）并形成清单。
  - [x] 4.7.2 选择“完整启用”或“完整下线”策略并实施。
  - [x] 4.7.3 补齐文档与 smoke 检查，消除“假入口”。

DoD：
- 模块启停与页面入口一致，不出现“假入口”。
- `app.py` 体积与职责明显收敛。

## 阶段 5：收尾精简（E 批次落地）

- [x] 5.1 `app.py` 壳层化
  - [x] 5.1.1 统一模块化分发入口（GET/POST dispatchers 聚合为单入口函数）。
  - [x] 5.1.2 将主流程里剩余“单域大块 if-branch”继续外移到 `fcc/modules/*/api.py`。
    - [x] 5.1.2.1 qbt `discover/fix-monitor/optimize-config` 路由迁移到 `fcc/modules/qbt/api.py`。
    - [x] 5.1.2.2 继续迁移 `api/http` 相关剩余块（path-scan/directories/files）。
    - [x] 5.1.2.3 继续迁移 `api/control` 剩余块（http-access/restart）。
  - [x] 5.1.3 `app.py` 仅保留：server 启动、共享状态、兼容入口与最小装配。
    - [x] 5.1.3.1 将 `/api/control/downloads` 迁移到 `fcc/modules/control/api.py`，缩减 `do_POST` 主流程分支。
    - [x] 5.1.3.2 抽取 GET 轻量状态类接口（`/api/base`、`/api/speed`、`/api/metrics/history`、`/api/process-net`、`/api/transfers`、`/api/control/status`）到独立模块分发。
    - [x] 5.1.3.3 抽取 `/api/http/source-ip-pools/sync` 到模块分发（保留现有 merge/replace 行为与错误语义）。
    - [x] 5.1.3.4 抽取 `/api/app-config` GET/POST 到模块分发，`app.py` 仅保留装配与回调桥接。
      - [x] 5.1.3.4.1 迁移 `GET /api/app-config`。
      - [x] 5.1.3.4.2 迁移 `POST /api/app-config`（含模块启停联动与返回结构保持兼容）。
  - [x] 5.1.4 增加“主文件不回流”防回归测试（关键路由关键字不再出现在 `app.py`）。
- [x] 5.2 文档收口
  - [x] 5.2.1 README 架构图/目录说明同步到模块化现状。
  - [x] 5.2.2 为“未来升级源脚本（script_source）”补运维章节与故障排查。
  - [x] 5.2.3 清理过时说明（含 backup 下线状态、旧直连分支描述）。

阶段 5.1.1 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `109 passed`
- `do_GET/do_POST` 的模块路由分发调用已聚合到 `_dispatch_modular_get_apis/_dispatch_modular_post_apis`，减少主流程重复分支噪音。

阶段 5.1.2.1 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `113 passed`
- 新增 `fcc/modules/qbt/api.py`，并将 qbt `discover/fix-monitor/optimize-config` 路由从 `app.py` 主流程迁移到模块分发。
- 新增 `tests/test_qbt_api_dispatch.py` 与 smoke 的 qbt 路由契约检查，防止回流到主文件。

阶段 5.1.2.2 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `118 passed`
- 新增 `fcc/modules/files/api.py`，并将 `GET /api/http/path-scan`、`GET /api/directories`、`GET /api/files` 从 `app.py` 主流程迁移到模块分发。
- 新增 `tests/test_files_api_dispatch.py` 与 smoke 的 files 路由契约检查，防止回流到主文件。

阶段 5.1.2.3 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `123 passed`
- 新增 `fcc/modules/control/api.py`，并将 `/api/control/http-access`、`/api/control/restart` 以及 `/healthz/restart` 从 `app.py` 主流程迁移到模块分发。
- 新增 `tests/test_control_api_dispatch.py` 与 smoke 的 control/restart 路由契约检查，防止回流到主文件。

阶段 5.1.3.1 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `125 passed`
- 将 `/api/control/downloads` 从 `app.py` 主流程迁移到 `fcc/modules/control/api.py`，继续收敛 `do_POST` 主流程分支数量。

阶段 5.1.3.2 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `130 passed`
- 新增 `fcc/modules/status/api.py`，并将 `/api/base`、`/api/speed`、`/api/metrics/history`、`/api/process-net`、`/api/transfers`、`/api/control/status` 从 `app.py` 主流程迁移到模块分发。
- 新增 `tests/test_status_api_dispatch.py` 与 smoke 的 status 路由契约检查，防止回流到主文件。

阶段 5.1.3.3 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `135 passed`
- 新增 `fcc/modules/http/api.py`，并将 `/api/http/source-ip-pools/sync` 从 `app.py` 主流程迁移到模块分发。
- 新增 `tests/test_http_api_dispatch.py` 与 smoke 的 http sync 路由契约检查，防止回流到主文件。

阶段 5.1.3.4 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `140 passed`
- 新增 `fcc/modules/appconfig/api.py`，并将 `GET/POST /api/app-config` 从 `app.py` 主流程迁移到模块分发。
- 新增 `tests/test_appconfig_api_dispatch.py` 与 smoke 的 app-config 路由契约检查，防止回流到主文件。

阶段 5.1.4 完成后基线（2026-05-26）：
- `python3 -m pytest -q` => `141 passed`
- 新增 `tests/test_app_shell_no_route_backflow.py`，约束已迁移路由不得以 `if parsed.path == ...` 回流到 `AppHandler.do_GET/do_POST` 主流程。

阶段 5.2 完成后基线（2026-05-26）：
- `README.md` 同步模块化现状：新增运行时分层与 `fcc/modules/*` 目录结构说明。
- 新增 `docs/upgrade-script-source.md`：补齐 `script_source` 运维使用、候选规则、环境变量与故障排查。
- 更新 `fcc/modules/backup/README.md`：明确 Backup 对外路由默认下线，移除过时“直接访问 /backup”描述。

## 7. 每批验收清单（防漏）

- [x] 路由兼容：原 URL、方法、状态码、返回字段不变。
- [x] 权限兼容：`_require_lan` 与 HTTP access policy 行为不变。
- [x] 操作兼容：Linux/macOS 服务控制行为一致且可观测。
- [x] 错误兼容：错误字段与文案不发生破坏性变化。
- [x] 测试覆盖：新增分域测试后，`python3 -m pytest -q` 全绿。

## 8. 建议工期

- 阶段 0：0.5 天
- 阶段 1：1.5-2 天
- 阶段 2：2-3 天
- 阶段 3：2-3 天
- 阶段 4：5-8 天

## 9. 风险与回滚

- 每阶段单独提交，必要时可按阶段回退。
- 迁移期间禁止同时改动“业务逻辑 + API 结构 + UI 协议”三类高风险面。
- 任一阶段出现大面积回归，先回到上阶段稳定点再继续。

## 10. 协作方式（逐条执行）

按以下格式推进：
- 你发：`执行 0.1` / `执行 1.1` / `执行 A1`
- 我做：实现 + 本地验证 + 结果回报 + 勾选文档任务。
- 然后继续下一条，直到批次完成。

每条任务完成时，我会同步：
- 改了哪些文件；
- 为什么这样改；
- 怎么验证；
- 剩余风险与下一条建议。
