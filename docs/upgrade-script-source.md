# Upgrade Hook Script Source (`script_source`)

更新时间：2026-05-26

## 1. 目标

在基础升级（拉取 release + 执行 `install.sh`）完成后，允许按版本/分支执行额外脚本，
用于第三方依赖补丁、客户私有环境适配、或本地集成动作。

## 2. 支持格式

`script_source` 仅支持：

- `github:owner/repo/path`
- `http://...` / `https://...`

不符合格式会在 `POST /api/upgrade/run` 返回 400。

## 3. 触发流程

1. 调用 `POST /api/upgrade/run`，可携带：
   - `branch`: `main` 或 `nightly`
   - `script_source`: 可选
2. AfterClaw 下载 release 包并执行 `install.sh`
3. 若 `script_source` 非空：
   - 拉取候选脚本 URL
   - 写入临时 hook 脚本
   - 在 `APP_ROOT` 下执行 `bash <hook-file>`
4. 状态写入 `upgrade_status.json`

## 4. GitHub 源候选规则

当 `script_source=github:owner/repo/path` 时，会按分支/版本尝试候选：

- `{path}/{tag}.sh`（有 tag 时）
- `{path}/{branch}.sh`
- `{path}/latest.sh`
- `{path}/upgrade.sh`

`{branch}`、`{tag}` 模板占位符会被替换。

## 5. 运行时环境变量

Hook 脚本执行时可读取：

- `AFTERCLAW_UPGRADE_BRANCH`
- `AFTERCLAW_UPGRADE_TARGET_TAG`
- `AFTERCLAW_UPGRADE_SCRIPT_URL`
- 以及基础安装阶段已有的 `APP_ROOT` / `WEB_PORT` / `STORAGE_ROOT` / `PUBLIC_HOST` / `PUBLIC_SCHEME`

## 6. 推荐运维策略（弱网/离线优先）

- 优先把升级脚本托管在内网可达源（HTTP 或镜像 GitHub 内容）。
- 对外网不稳定的客户环境，建议提供本地升级源并设置固定 `script_source`。
- 升级脚本应做到幂等：重复执行不破坏已安装状态。
- 升级脚本中把关键步骤写日志并显式 `exit 1`，便于 UI 反馈故障点。

## 7. 故障排查

先查 `GET /api/upgrade/status`：

- `state`: `running` / `success` / `error`
- `hook_state`: `idle` / `running` / `success` / `error` / `skip`
- `hook_error`: hook 脚本错误摘要

常见问题：

1. `hook_state=skip`
   - 原因：`script_source` 为空，或未匹配到可执行脚本候选
   - 处理：检查 `script_source` 格式与候选文件命名
2. `hook_state=error`
   - 原因：hook 脚本执行失败（非 0）
   - 处理：查看 `hook_error`，修复脚本后重试升级
3. `state=error` 且未进入 hook
   - 原因：基础升级阶段失败（下载/解包/install.sh）
   - 处理：先恢复基础升级，再处理 hook
4. 版本更新成功但效果未体现
   - 原因：运行的是旧安装副本或旧服务实例
   - 处理：确认实际运行路径与服务单元指向是否一致

## 8. 最小请求示例

```json
{
  "branch": "main",
  "script_source": "github:your-org/afterclaw-hooks/hooks"
}
```
