# WorkBuddy2API-Hub fnos-1.7.33（飞牛原生 fpk）

对应上游 `v1.7.33`（`ardeyouxipianyi/workbuddy2api-hub`，该 tag 就是上游 `main` 的头部）。
包名 `WorkBuddy2API-Hub_1.7.33_all.fpk`，`appname` 仍是 `workbuddy2api` —— 覆盖安装即可，
数据目录 `/vol1/@appdata/workbuddy2api`（账号、用量、设置）不变。

发布不经 CI：包在维护者机器上用 `scripts/build-fpk.sh` 构建、`scripts/gh-release.py` 上传，
所以**本 Release 的附件与本机 `dist/` 里的文件逐字节相同**。

## 文件与校验

| 文件 | 字节数 | sha256 |
| --- | --- | --- |
| `WorkBuddy2API-Hub_1.7.33_all.fpk` | `1023096` | `fe4193de2156585ac93b946714b1b2c5a4ab29e5821ab02353b5763501a60c74` |
| `WorkBuddy2API-Hub_1.7.33_all.fpk.sha256` | `99` | — |

校验：`sha256sum -c WorkBuddy2API-Hub_1.7.33_all.fpk.sha256`

## 安装 / 升级

1. 应用中心 → 手动安装 → 选择本 Release 的 `.fpk`（覆盖安装即可，端口仍是 8788）；
   或者用 FnDepot 客户端（源 `https://github.com/ccrabit/FnDepot`）点更新。
2. 升级前建议备份 `/vol1/@appdata/workbuddy2api/`（至少 `accounts/` 与 `usage/`）。
3. 卸载默认保留数据目录。

## 本版包含

上游 **v1.7.31 / v1.7.32 / v1.7.33** 三个 release（完整条目与 PR 归属见仓库内 `docs/CHANGELOG.md`）：

- **v1.7.33**（`#630 / #632 / #635 / #638`，本版起进入低频维护）：每日活跃重构为「一个预算 + 一个
  候选序列」，失败收尾登记保留并把旧配置迁移过来（`#638`）；登记表与被放弃的线程都加上界，内存不再
  随失败次数增长；网页会话收尾不再依赖那条卡住的线程；模型级 429 冷却窗口在重启后能恢复、成功请求
  会解除凭证失效标记；`/v1/responses` 补发工具调用首段参数增量；面板校正调色对比度并提示 HTTP 入口。
- **v1.7.33 的心跳（本仓库曾经的自己人）**：网关现在**自己**会在上游静默时补 SSE 注释心跳
  （`SSEHeartbeat`，默认 15 秒，`#578`）。飞牛这一层因此改用上游实现，只保留
  `WB_STREAM_KEEPALIVE_SECONDS` 作为覆盖默认值的旋钮（`0` 关闭、上限 300 秒）。
- **v1.7.32**：`minimax-` 前缀不再是「整个模型家族 CN 专属」的误判（`#618`），并给 OpenCode 写入
  真实上下文上限（`#625`）。

## 飞牛侧（本 fork 相对上游多出来的部分，全部保留）

- 统一网关免密入口（`--unix-socket` + `--base-path`）、面板主题与移动端适配、账号导入导出与
  cockpit 看板导出；页面里每个 `fetch()` 都经 `wbUrl()` 前缀包装（有套件钉住）。
- 可写模型目录存档：`WB_PROXY_CATALOG_DIR` 指向 `${TRIM_PKGVAR}/catalog`，安装/升级时创建并
  `chmod 700`；`catalog/` 不打进包（上游默认落在只读载荷目录，在 NAS 上会静默失效）。
- 打包：`wb_quota_scan.py` / `wb_window_probe.py` / `wb_update_request.py` / `wb_tiers.py` /
  `wb_webprompts.py` / `wb_update_portable.py` / `wb_update_apply.py` / `wb_update_external.py`
  都在载荷守卫名单里（`wb_proxy.py` 顶层 import，缺一个就是装完启动即 ImportError）；`tools/`、
  `ops/`、`catalog/`、`logs/`、`tests/`、`docs/` 一律不入包。
- 面板「安装更新」在飞牛上保持关闭：`install_enabled()` 的三条判据（systemd unit、外部执行者、
  便携包 `release-manifest.json`）在这里都不成立，不会去下便携 zip 覆盖只读载荷。升级走应用中心
  或 FnDepot，**不要**在命令行手工替载荷再手工起服务 —— 那会让应用中心记录的运行态与真实进程不一致。

## 验证数字

- `python3 tests/run_all.py --jobs 4`：`235 passed, 0 failed, 0 skipped`
- `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.7.33_all.fpk`：`70 passed, 0 failed`
- 载荷：51 个文件 + 15 个目录，manifest checksum `ce408dc0d1abbba88eeb9220321ad7b7`；
  `logs/` / `tools/` / `ops/` / `catalog/` 在包内 0 命中
- 附件的 sha256 与仓库根 `fnpack.json` 登记的 `1.7.33` 条目一致

## 已知限制

- 上游 v1.7.6 起 `/v1/messages`（Anthropic 原生入口）默认关闭，需显式设
  `WB_ENABLE_ANTHROPIC_MESSAGES=1`；本包保持上游默认。
- 本包只面向飞牛 fnOS（`all` 平台，纯 Python 载荷），Windows/macOS 请用仓库里的便携包。
- 升级不会自动迁移旧版 `usage/` 下的历史统计到 SQLite 日志库；日志落库默认关闭。
