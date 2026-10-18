# WorkBuddy2API-Hub fnos-1.7.13（飞牛原生 fpk）

本次发布对应上游 `v1.7.13`（`ardeyouxipianyi/workbuddy2api-hub`），并额外包含 **v1.7.13 之后
上游 `main` 上仍未发版的 44 个提交**（共 63 个提交 / 69 个文件 / +9626 −492，合并基 `7e5c38d`
→ `fe30fa0`）。包名 `WorkBuddy2API-Hub_1.7.13_all.fpk`，`appname` 仍是 `workbuddy2api` ——
覆盖安装即可，数据目录 `/vol1/@appdata/workbuddy2api`（账号、用量、设置）不变。

发布仍不经 CI：包在维护者机器上用 `scripts/build-fpk.sh` 构建、用 `scripts/gh-release.py`
上传，所以**本 Release 的附件与本机 `dist/` 里的文件逐字节相同**。

## 文件与校验

| 文件 | 字节数 | sha256 |
| --- | --- | --- |
| `WorkBuddy2API-Hub_1.7.13_all.fpk` | `872207` | `7fd2bd2dbb141944dc41db2df1974093344799c9eca758c1c273d535b2e334f8` |
| `WorkBuddy2API-Hub_1.7.13_all.fpk.sha256` | `99` | — |

校验：`sha256sum -c WorkBuddy2API-Hub_1.7.13_all.fpk.sha256`

## 安装 / 升级

1. 应用中心 → 手动安装 → 选择本 Release 的 `.fpk`（覆盖安装即可，端口仍是 8788）。
2. 升级前建议备份 `/vol1/@appdata/workbuddy2api/`（至少 `accounts/` 与 `usage/`）。
3. 卸载默认保留数据目录。

## 本版包含

上游 **v1.7.11 / v1.7.12 / v1.7.13** 三个 release 的要点（每个版本的完整条目与 PR 归属见仓库内
`docs/CHANGELOG.md`）：

- **v1.7.13** 请求结束按上游回包里的 `credit` **立即扣减余额**（#442，低积分护栏不再依赖 30
  分钟一轮的刷新缓存）；便携包补回 `console_tail.py` 与 `pythonw.exe`（#416，修「静默启动一闪
  而过」）；日志按钮改为新窗口打开（#427）；关闭服务用 `/health` 复核、被容器拉起时如实提示
  （#426）；OpenWrt 补 `python3-openssl` / `python3-sqlite3` / `python3-codecs`（#419）。
- **v1.7.12** 用量明细三个维度补齐「消耗积分」列（账号 / 模型 / API Key）；深色模式对比度提到
  4.6~5.2:1（WCAG AA）；账号级「禁用模型」`disabledModels`（精确匹配，空数组=清空）；日志与
  「最近请求」显示发起方 API Key；软限流阶梯纳入 `WB_FAIL_WINDOW`（默认 600s）并把剩余时间改成
  秒级可读；调度巡检账号间随机错峰 2~5 秒；维护脚本归档进 `tools/`。
- **v1.7.11** 国际版 `deepseek-v4.1-flash` 免费额度耗尽后可回退积分版
  `deepseek-v4.1-flash-sg`（开关 `WB_ENABLE_FREE_MODEL_CREDIT_FALLBACK`，默认关；仅当所有启用
  账号都收到带重置时间的 6004 才回退）；通用失败分支现在会打出冷却原因。

以及 v1.7.13 之后、尚未发版的那 44 个提交里比较要紧的：

- `/u/<ref>/v1/...` **按账号定址路由**（#455，歧义 409、不存在 404）；`GET /v1/balance-summary`
  只读积分汇总；`WB_PRESERVE_REQUEST_CONTRACT`（默认 `"0"`）保留 `response_format` / 工具数据。
- 工具 JSON Schema 递归规整，根治上游 `11129` / `11101`（#446/#451）；工具结果前插消息导致的
  `11148` 配对失败（#420）；`tool_result` 图片保留结构化 `image_url`（#452，避免 base64 按文本
  计费）；风控 403（`11140`）默认不再换号连坐并可整池暂停（#448）。
- 后台排程时段可配（`settings.json` 的 `schedule`，默认即旧硬编码）；用量时序桶按**本地午夜/整点**
  对齐（#447）；CLI 身份对齐官方 `2.168.2`、VSCode 扩展对齐 `4.12.39997873`、桌面端 intl
  `5.8.4` / cn `5.6.2`；`wb_quota_scan.py` / `wb_window_probe.py` 额度查询与窗口探针；面板
  「剩余用量估算」新增撞线样本区块（#253）。

飞牛侧（本 fork 相对上游多出来的部分，全部保留并随本版校正）：

- 统一网关免密入口（`--unix-socket` + `--base-path`）、面板主题与移动端适配、账号导入导出与
  cockpit 看板导出。
- **本次修掉的两处上游绝对路径**：眼睛按钮的 `window.open('/dashboard?tab=logs')` 与关闭服务后
  的 `fetch('/health')` 在 `/app/workbuddy2api` 前缀下会 404，已改为走 `wbUrl()`；页面里 6 个
  `fetch()` 调用点全部经前缀包装（有套件钉住）。
- **打包**：v1.7.5 起上游把模型目录存档默认落在只读载荷目录，在 NAS 上会静默失效；本版仍把
  `WB_PROXY_CATALOG_DIR` 指向可写数据目录 `${TRIM_PKGVAR}/catalog`，安装/升级时创建并
  `chmod 700`，`catalog/` 不打进包。
- **打包**：新增的 `wb_quota_scan.py` / `wb_window_probe.py` / `wb_update_request.py` 进入载荷与
  守卫名单（`wb_proxy.py` 顶层 `import wb_update_request`，缺它启动即 ImportError）；`tools/` 与
  `ops/` 不进包。新增的运行时状态都落在 `accounts/`（`quota_scan.json`、`model_windows.json`），
  不需要新目录。
- 阿里云那套 systemd 更新服务（`ops/aliyun/`、`WB_UPDATE_INSTALL_ENABLED`）在飞牛上保持关闭：
  本包没有 systemd path unit，面板的「安装更新」按钮按设计禁用。

## 验证数字

- `python3 tests/run_all.py --jobs 4`：`179 passed, 0 failed, 0 skipped`
- `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.7.13_all.fpk`：`70 passed, 0 failed`
  （1 条 SKIP 属正常：`fnos-<版本>` tag 打在合并提交上，而回填提交在其之后，所以工作树不「在 tag 上」）
- 载荷：45 个文件 + 16 个目录（1.7.10 为 43 个文件），manifest checksum `2f09ba938066ea65d4665ea60fdd7daf`
- 冒烟（发布前，隔离端口 8799，不动设备上的 8788）：面板 `/` 200、`/panel/status` 200、日志无报错；
  `/v1/chat/completions` 非流式与流式都拿到真实模型回复（`usage.credit` 有值）
- 附件的 sha256 与仓库根 `fnpack.json` 里登记的 `1.7.13` 条目一致

## 已知限制

- 上游 v1.7.6 起 `/v1/messages`（Anthropic 原生入口）默认关闭，需显式设
  `WB_ENABLE_ANTHROPIC_MESSAGES=1`；本包保持上游默认，不改这个口径。
- 本包只面向飞牛 fnOS（`all` 平台，含 x86_64 与 arm64 的纯 Python 载荷），Windows/macOS 请用
  仓库里的便携包。
- 升级不会自动迁移旧版 `usage/` 下的历史统计到 SQLite 日志库；日志落库默认关闭。
