# Nightly Development Policy

本项目采用 **Nightly 先行、Main 后发布** 的流程。

## 目标

- 所有新功能先进入 `nightly`，先验证稳定性和体验。
- 只有在你明确确认“可发布”后，才允许合入 `main`。
- `main` 保持正式版稳定，不承载实验性入口。

## 分支与环境规则

1. 默认开发分支：`nightly`
2. 正式发布分支：`main`
3. 建议运行环境：
- Nightly: `http://<host>:1299`
- Stable(Main): `http://<host>:1288`

## 强制发布门禁

从 `nightly` 推到 `main` 前，必须满足：

1. 你已确认 nightly 版本功能与交互达标。
2. 已完成关键路径自测（主页、Config、HTTP/qB/Terminal/DDNS、多语言切换）。
3. 已移除所有 nightly 专属功能（见下条）。

## Nightly 专属功能（仅 nightly 允许）

以下功能只能在 nightly 出现：

1. `测试进度条展示` 按钮
2. `切换到1288正式版` 按钮

`main` 中禁止出现以上两个入口。任何合并到 `main` 的提交必须去除/关闭这两个功能。

## 交付约定

- 开发顺序：先 nightly 完整实现 -> 你验收 -> 再整理进入 main。
- 如需对外发布，发布基线永远来自 `main`，不直接从 nightly 打正式包。

## 版本命名规则（强制）

1. `main`（正式版）必须使用 `MAJOR.MINOR.PATCH`，例如：`0.9.6`
2. `nightly`（开发版）必须使用 `MAJOR.MINOR.NEXT_PATCH.devYYYYMMDD`，例如：`0.9.7.dev20260501`
3. 正式版禁止使用 `.dev*` 后缀
4. `nightly` 未验收完成前，不得将其版本推进到 `main`
