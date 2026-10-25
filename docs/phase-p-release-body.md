# WorkBuddy2API-Hub fnos-1.8.0（飞牛原生 fpk）

对应上游 `v1.8.0`（`ardeyouxipianyi/workbuddy2api-hub`，该 tag 就是上游 `main` 的头部）。
包名 `WorkBuddy2API-Hub_1.8.0_all.fpk`，`appname` 仍是 `workbuddy2api` —— 覆盖安装即可，
数据目录 `/vol1/@appdata/workbuddy2api`（账号、用量、设置）不变。

发布不经 CI：包在维护者机器上用 `scripts/build-fpk.sh` 构建、`scripts/gh-release.py` 上传，
所以**本 Release 的附件与本机 `dist/` 里的文件逐字节相同**。

## 文件与校验

| 文件 | 字节数 | sha256 |
| --- | --- | --- |
| `WorkBuddy2API-Hub_1.8.0_all.fpk` | `1024941` | `cc19a71fa6b80c6f8695c3cb22602aca323d2e9f8e6412c554f9a93faf31bbe9` |
| `WorkBuddy2API-Hub_1.8.0_all.fpk.sha256` | `99` | — |

校验：`sha256sum -c WorkBuddy2API-Hub_1.8.0_all.fpk.sha256`

## 安装 / 升级

1. 应用中心 → 手动安装 → 选择本 Release 的 `.fpk`（覆盖安装即可，端口仍是 8788）；
   或者用 FnDepot 客户端（源 `https://github.com/ccrabit/FnDepot`）点更新。
2. 升级前建议备份 `/vol1/@appdata/workbuddy2api/`（至少 `accounts/` 与 `usage/`）。
3. 卸载默认保留数据目录。

## 本版包含

上游 **v1.8.0**（从 `1.7.33` 直接跳到 `1.8.0`，没有 `1.7.34`）。这一版**全部是修 bug**，
没有新功能、没有新顶层模块：

- **`#647` 国际版沙箱证书失败时降级到活跃上报**：网页会话拿不到沙箱证书时不再整批失败，
  而是退回「活跃上报」这条路继续算当日活跃，避免整段日常任务因为一个证书问题全灭。
- **`#644` `stderr` 日志通道不再阻塞请求线程**：日志管道写不动时（下游没人读、管道满），
  原来会卡住请求线程；现在日志写入与请求路径解耦，写失败也不会拖住整条请求。
- **`#643` 桌面 chat 可选协议一致性**：出站身份里桌面 chat 的可选协议字段与客户端实际行为对齐。
- **`#640` 更新检查超时放宽到 10 秒**：弱网/代理链路上不再频繁把检查判成超时。

上一版（v1.7.33）那批内容也都在这条线上：每日活跃「一个预算 + 一个候选序列」、失败收尾登记
保留并迁移旧配置、登记表与被放弃线程加上界、模型级 429 冷却窗口重启可恢复、`responses` 补发
工具调用首段参数增量、面板对比度校正，以及**上游自己实现的流式 SSE 心跳**（`SSEHeartbeat`，
默认 15 秒）。

## 飞牛侧（本 fork 相对上游多出来的部分，全部保留）

- 统一网关免密入口（`--unix-socket` + `--base-path`）、面板主题与移动端适配、账号导入导出与
  cockpit 看板导出；页面里每个 `fetch()` 都经 `wbUrl()` 前缀包装（有套件钉住）。
- 流式心跳仍可用 `WB_STREAM_KEEPALIVE_SECONDS` 覆盖上游默认的 15 秒（`0` 关闭、上限 300 秒）——
  实现是上游的 `SSEHeartbeat`，本层只留这个旋钮。
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

- `python3 tests/run_all.py --jobs 4`：`236 passed, 0 failed, 0 skipped`
- `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.8.0_all.fpk`：`70 passed, 0 failed`
- 载荷：51 个文件 + 15 个目录，manifest checksum `20a84d687ca21e7b812f392cd1a95f8a`；
  `logs/` / `tools/` / `ops/` / `catalog/` 在包内 0 命中
- 附件的 sha256 与仓库根 `fnpack.json` 登记的 `1.8.0` 条目一致

## 已知限制

- 上游 v1.7.6 起 `/v1/messages`（Anthropic 原生入口）默认关闭，需显式设
  `WB_ENABLE_ANTHROPIC_MESSAGES=1`；本包保持上游默认。
- 本包只面向飞牛 fnOS（`all` 平台，纯 Python 载荷），Windows/macOS 请用仓库里的便携包。
- 升级不会自动迁移旧版 `usage/` 下的历史统计到 SQLite 日志库；日志落库默认关闭。
