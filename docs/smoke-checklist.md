# AfterClaw Smoke Checklist (Phase 0.2)

更新时间：2026-05-26

用途：
- 在“修复 + 分拆”期间，快速确认核心操作面仍然存在。
- 这是最小契约检查，不替代完整集成测试。

## 1. 页面入口

- [ ] `GET /`（首页入口）
- [ ] `GET /config`（配置页）
- [ ] `GET /terminal`（终端页）
- [ ] `GET /member`（会员页）

## 2. Docker 关键接口

- [ ] `GET /api/docker/containers`
- [ ] `GET /api/docker/logs`
- [ ] `GET /api/docker/images`
- [ ] `POST /api/docker/action`

## 3. 重启关键接口

- [ ] `POST /api/control/restart`
- [ ] `POST /healthz/restart`

## 4. 每次改动后的执行建议

最小自动化：

```bash
python3 -m pytest -q tests/test_smoke_surface_contract.py
```

完整基线：

```bash
python3 -m pytest -q
```

## 5. 判定标准

- 关键路由定义仍在（未被误删、误改路径、误改方法）。
- `AppHandler` 核心入口仍在（`do_GET` / `do_POST`）。
- Docker 读取与动作接口都保留。
- 重启接口至少保留一条控制链路。

