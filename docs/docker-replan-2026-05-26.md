# Docker 模块重规划（AfterClaw 专用 + 热门项目基础支持）

更新时间：2026-05-26

## 1. 目标调整

Docker 能力定位改为两层：

1. `AfterClaw 推荐清单`（主路径）
- 仅维护我们验证过的推荐项目与部署模板。
- 强调稳定、可运维、可回滚。

2. `热门项目基础支持`（兼容路径）
- 对类似 Inkos 这类热门项目提供“基础生命周期操作”。
- 不承诺深度业务适配，只提供统一控制能力。

## 2. 支持边界（统一）

对“热门项目基础支持”仅提供以下动作：

- 检测状态（running / stopped / error）
- 启动 / 关闭 / 重启
- 安装（拉镜像 + 创建容器）
- 卸载（停止并删除容器，可选删除镜像）
- 升级（拉取新镜像并重建容器，保持同名）

不在该层承诺：

- 项目业务 API 解析
- 复杂 compose 拓扑自动修复
- 业务级健康诊断（仅容器/进程级）

## 3. 开关语义（回答“为什么要 Docker 开关”）

当前 `Docker API Module` 开关的意义是：

- `ON`：AfterClaw 暴露 `/api/docker/*` 管理能力。
- `OFF`：AfterClaw 拒绝 Docker API 调用（安全收敛）。

注意：

- 该开关不会停止宿主机 Docker 服务。
- 该开关不会卸载 Docker。
- 它只是 AfterClaw 的“控制面暴露开关”。

## 4. 首页与配置页建议

1. 首页
- 保持轻量：显示 Docker 总览（可用性、容器数量、运行数量）。
- 不在首页堆叠高级编辑动作。

2. 配置页
- “推荐项目”与“基础兼容项目”分区展示：
  - 推荐项目：一键安装模板
  - 兼容项目：按容器名执行基础操作

3. 文案
- 明确写出“AfterClaw API 开关，不是 Docker 服务开关”。

## 5. API 结构建议（向后兼容）

保留现有 `/api/docker/*`，新增一个统一基础动作入口（推荐）：

- `POST /api/docker/basic-op`
  - `action`: `status|start|stop|restart|install|uninstall|upgrade`
  - `target`: 容器名或推荐项 ID
  - `options`: 可选参数（镜像、端口、卷、env、force 等）

旧接口继续可用，前端逐步迁移到 `basic-op`，避免分散控制逻辑。

## 6. Inkos 接入策略

Inkos 归入“热门项目基础支持”，处理方式：

- 自动发现：按容器名/镜像关键字匹配
- 操作限制：仅允许基础生命周期动作
- 若用户提供自定义镜像与参数，走通用 install/uninstall/upgrade 流程

## 7. 分阶段落地

阶段 A（低风险，先做）
- [x] 完成文案校正（开关语义）
- [x] 首页显示 Docker 只读总览
- [x] 补基础操作权限测试

阶段 B（核心）
- [x] 实现 `/api/docker/basic-op`
- [x] 推荐清单与兼容清单双通道（前端说明 + 统一基础动作入口）

阶段 C（增强）
- [x] 升级流程标准化（备份旧容器配置、失败回滚）
- [x] 历史操作审计与操作日志导出

## 8. 验收标准

- 用户可清楚区分“AfterClaw Docker 开关”与“系统 Docker 服务状态”。
- 热门项目（含 Inkos）可完成基础动作闭环。
- 推荐项目路径比兼容路径更稳定、文档更完整。

## 9. 执行记录（本轮）

- [x] 配置页 Docker 开关文案明确为“AfterClaw API 暴露开关”，并声明不影响宿主机 Docker daemon。
- [x] 新增统一基础动作接口：`POST /api/docker/basic-op`（`status|start|stop|restart|install|uninstall|upgrade`）。
- [x] Docker 面板主要操作迁移到 `basic-op`（start/stop/restart/install/uninstall/upgrade/pull）。
- [x] 新增容器级 “Upgrade image + restart” 操作按钮，补齐基础生命周期闭环。
- [x] 补充 `basic-op` 测试覆盖：`status/install/uninstall/upgrade` 关键分支。
- [x] 升级执行从“pull+restart”修正为“snapshot + recreate”，并在创建失败时自动 rename 回滚到原容器（含恢复启动状态）。
- [x] 新增 Docker 操作审计与导出接口：
  - `GET /api/docker/ops/history`（支持 `limit/action/name/ok` 过滤）
  - `GET /api/docker/ops/export`（支持 `format=jsonl|json` 与 `limit`）
  - `POST /api/docker/ops/history/clear`
  - 覆盖 `basic-op` 与兼容旧接口动作（install/uninstall/upgrade/start/stop/restart/pull/image-remove）写审计记录。
- [x] Docker 面板新增 `History` 标签页，支持查看操作历史、刷新、导出 JSONL/JSON、清空审计记录。
- [x] 审计记录持久化到本地 `docker_ops_history.jsonl`（可通过 `DOCKER_OPS_HISTORY_FILE` 覆盖路径），服务重启后历史仍可读取。
