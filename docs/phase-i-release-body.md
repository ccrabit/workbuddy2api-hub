# WorkBuddy2API-Hub fnos-1.7.10（飞牛原生 fpk）

本次发布对应上游 `v1.7.10`（`ardeyouxipianyi/workbuddy2api-hub`，上游发布提交 `7e5c38d`），
包名 `WorkBuddy2API-Hub_1.7.10_all.fpk`，`appname` 仍是 `workbuddy2api` —— 覆盖安装即可，
数据目录 `/vol1/@appdata/workbuddy2api`（账号、用量、设置）不变。

这一版把上游 **v1.7.4 ~ v1.7.10 七个版本**一次性并入（含全部分支上的修复），
发布仍不经 CI：包在维护者机器上用 `scripts/build-fpk.sh` 构建、用 `scripts/gh-release.py`
上传，所以**本 Release 的附件与本机 `dist/` 里的文件逐字节相同**。

## 文件与校验

| 文件 | 字节数 | sha256 |
| --- | --- | --- |
| `WorkBuddy2API-Hub_1.7.10_all.fpk` | `800307` | `7d8cc1d800f4482e4f573587c5cbbe69ee4c61b988fc710317833f96562d4809` |
| `WorkBuddy2API-Hub_1.7.10_all.fpk.sha256` | `99` | — |

校验：`sha256sum -c WorkBuddy2API-Hub_1.7.10_all.fpk.sha256`

## 安装 / 升级

1. 应用中心 → 手动安装 → 选择本 Release 的 `.fpk`（覆盖安装即可，端口仍是 8788）。
2. 升级前建议备份 `/vol1/@appdata/workbuddy2api/`（至少 `accounts/` 与 `usage/`）。
3. 卸载默认保留数据目录。

## 本版包含

上游 v1.7.4 ~ v1.7.10 的要点（每个版本的完整条目与 PR 归属见仓库内 `docs/CHANGELOG.md`）：

- **v1.7.4** 可选 SQLite 日志落库（默认关闭，按天/周/月三维轮转，写 `usage/logs.sqlite3`）；
  macOS/Linux keyblob 导入；一键配置文件 0600；checkpoint 误判修复（首屏 2~3s → ~10ms）；
  账号页可切版本；隐藏无倍率模型；`glm-5.3-flash` 强制纯文本。
- **v1.7.5** 数据看板 Bento 重构 + Claude 暖色主题；`POST /catalog/refresh`（30s 防抖 +
  24h 自动补拉，绿/黄来源横幅，模型表 8 列）；首页卡片改真实积分消耗。
- **v1.7.6** 后台模型原子重定向（`WB_BACKGROUND_MODEL_TARGET`，默认 `deepseek-v4.1-flash`）；
  `/v1/messages` 默认返回 HTTP 400（要开启需 `WB_ENABLE_ANTHROPIC_MESSAGES=1`）。
- **v1.7.7** 熔断时间窗 `WB_FAIL_WINDOW=600`；断网时不再记账号；账号池「一键测试」与未活跃
  账号一键打卡；禁用总览区分 6004/429；网页通道重试（默认 3 次）；国际版 5.8.4 身份头族；
  413 响应带 `gateway_hint`；GPT 模型 `max_tokens<16` 自动夹取。
- **v1.7.8** 打卡模型冷却感知回退；透传 `usage.prompt_tokens_details.cached_tokens`。
- **v1.7.9** 6004 之后可按开关回退 `deepseek-v4.1-flash-sg`（默认关）；每个 API Key 独立并发
  上限（超限回 429）；DSH 默认 `supportsVision`；修流式 `finish_reason=error` 记账。
- **v1.7.10** 正文与 v1.7.9 相同，另修并发辅助函数的类内缩进（提到模块级）。
- 新模块 `wb_logstore.py`（可选日志落库）；`catalog/` 目录存档新增；若干测试套件随上游并入。

飞牛侧（本 fork 相对上游多出来的部分，全部保留并随本版校正）：

- 统一网关免密入口（`--unix-socket` + `--base-path`）、面板主题与移动端适配、
  账号导入导出与 cockpit 看板导出。
- **打包修复**：v1.7.5 起上游把模型目录存档默认落在只读载荷目录里，在 NAS 上会静默失效；
  本版把 `CATALOG_DIR`（`WB_PROXY_CATALOG_DIR`）指向可写数据目录 `${TRIM_PKGVAR}/catalog`，
  安装/升级时创建并 `chmod 700`；`catalog/` 不打进包。
- **打包修复**：新增模块 `wb_logstore.py` 进入载荷与校验名单（日志库落在可写的
  `${TRIM_PKGVAR}/usage`，无需额外目录）。

## 验证数字

- `python3 tests/run_all.py --jobs 4`：`166 passed, 0 failed, 0 skipped`
- `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.7.10_all.fpk`：`70 passed, 0 failed`
  （1 条 SKIP 属正常：`fnos-<版本>` tag 打在合并提交上，而回填提交在其之后，所以工作树不「在 tag 上」）
- 载荷：43 个文件（1.7.3 为 42，新增 `wb_logstore.py`），manifest checksum `4ce9d4ccc06bef178fa5af1726551c33`
- 附件的 sha256 与仓库根 `fnpack.json` 里登记的 `1.7.10` 条目一致

## 已知限制

- 上游 v1.7.6 起 `/v1/messages`（Anthropic 原生入口）默认关闭，需显式设
  `WB_ENABLE_ANTHROPIC_MESSAGES=1`；本包保持上游默认，不改这个口径。
- 本包只面向飞牛 fnOS（`all` 平台，含 x86_64 与 arm64 的纯 Python 载荷），
  Windows/macOS 请用仓库里的便携包。
- 升级不会自动迁移旧版 `usage/` 下的历史统计到新的 SQLite 日志库；日志落库默认关闭。
