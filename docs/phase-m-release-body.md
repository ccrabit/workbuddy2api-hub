# WorkBuddy2API-Hub fnos-1.7.29（飞牛原生 fpk）

本次发布对应上游 `v1.7.29`（`ardeyouxipianyi/workbuddy2api-hub`）。合并基是
`205d8b6`（v1.7.24），所以这一个包覆盖了上游 **v1.7.25 / v1.7.26 / v1.7.27 /
v1.7.28 / v1.7.29** 五个 release：**31 个提交、27 个文件、+4166 −165**。
`v1.7.29` 就是上游 `main` 的头部，因此这棵树不含任何「未发版提交」。

包名 `WorkBuddy2API-Hub_1.7.29_all.fpk`，`appname` 仍是 `workbuddy2api` ——
覆盖安装即可，数据目录 `/vol1/@appdata/workbuddy2api`（账号、用量、设置）不变。

发布不经 CI：包在维护者机器上用 `scripts/build-fpk.sh` 构建、用
`scripts/gh-release.py` 上传，所以**本 Release 的附件与本机 `dist/` 里的文件逐字节相同**。

## 文件与校验

| 文件 | 字节数 | sha256 |
| --- | --- | --- |
| `WorkBuddy2API-Hub_1.7.29_all.fpk` | `976767` | `cbad6b2376b0c430e3646eca54dfcbfcabbeef7443158e0826289aa1d0c65929` |
| `WorkBuddy2API-Hub_1.7.29_all.fpk.sha256` | `99` | — |

校验：`sha256sum -c WorkBuddy2API-Hub_1.7.29_all.fpk.sha256`

## 安装 / 升级

1. 应用中心 → 手动安装 → 选择本 Release 的 `.fpk`（覆盖安装即可，端口仍是 8788）；
   也可以在 FnDepot 里给 `https://github.com/ccrabit/FnDepot` 这个源点更新。
2. 升级前建议备份 `/vol1/@appdata/workbuddy2api/`（至少 `accounts/` 与 `usage/`）。
3. 卸载默认保留数据目录。

## 这一版做了什么

**手机端四处布局修复**：工具栏打卡按钮靠右（#585）、用量统计副行每项一行且图表底边对齐
（#586）、账号卡里出口与权重同行（#587）、窄屏「积分消耗」独占一行（#588）。桌面端
1280 / 1100 / 900 / 700 / 641px 逐属性对照无变化。

**更新与回退**：
- 启动时补一次更新检查（#589）：重启后不再卡在「有新版本但装不了」等满 24 小时；
  仍受每小时预算 6 次约束，稳态一天一次。
- 保留历史版本备份并支持面板「版本回退」（#571）：`updates/backup-<目标版本>/`，
  份数 0–3（默认 1，0 即不备份也不可回退）；`request.json` 增加 `action: install|rollback`，
  回退后校验 `Server: wb-proxy/<版本>`，失败自动恢复到回退前版本。
- 便携更新保留 zip 里的 unix 权限位（#582）：`start-wb-proxy*.sh` 不再从 755 落成 644
  （否则重启那步 `Popen()` 报 EACCES 并回滚）。
- 镜像 / rootfs 部署的 `request.json` 带 `profile: "app"`，只替换应用层（#573）。

**账号与风控**：
- 账号档位改读计费摘要（#505）：`IsPaidUser` / `SubscriptionPackageName` 落成账号上的
  `tier`，失败不写结论（401 / 非 0 code / 网络错误保留旧值），24 小时 TTL。
- uid 不再被手机号脱敏改写（#581）：国内号 uid 里的 `179-97517476` 曾被当成号码，
  面板因此回 `no such account`；`nickname` 的脱敏不变。
- API Key 的账号白名单与并发上限能落盘了（#592）。
- 11-128 继续收口：assistant 历史也清洗、散文里的 `DeepSeek Harness` 缩成 `DeepSeek`
  （#574）、DSH GUI 描述段的句尾语序（#579）。
- 跨出口回退「国际版限流 → 国内版」默认关闭（#564）。
- 账号表排序按「主行 + 紧跟的 `tr.cool-row` 续行」成组（#568）。

## 飞牛侧（本 fork 相对上游多出来的部分，全部保留）

- 统一网关免密入口（`--unix-socket` + `--base-path`）、面板主题与移动端适配、
  账号导入导出与 cockpit 看板导出。
- **流式空闲心跳**（`WB_STREAM_KEEPALIVE_SECONDS`，默认 10 秒，`0` 关闭，上限 300）：
  上游安静超过间隔就补一帧 `: keepalive`，避免反向代理按「没字节」把长回答判死；
  忙流零写入，收尾帧与错误帧都走同一个加锁写出口。
- **打包**：模型目录存档指向可写数据目录 `${TRIM_PKGVAR}/catalog`（上游默认落在只读
  载荷目录，在 NAS 上会静默失效）；`tools/`、`ops/`、`catalog/`、`tests/`、`docs/`、
  `accounts/`、`usage/` 不进包；五个更新相关模块在载荷守卫名单里。
- **面板「安装更新」在飞牛上保持关闭**：`install_enabled()` 的三条判据
  （systemd unit / `WB_UPDATE_INSTALL_ENABLED=1` + 外部执行者 / 便携包
  `release-manifest.json`）在飞牛上都不成立，按钮不会去下「便携 zip」覆盖 fpk 装的
  只读载荷；升级走应用中心或 FnDepot。

## 验证数字

- `python3 tests/run_all.py --jobs 4`：**221 passed, 0 failed, 0 skipped**
  （`_test_phase_e_verify.py` PASS=377 FAIL=0 SKIP=3）
- `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.7.29_all.fpk`：**70 passed, 0 failed**
  （1 条 SKIP 属正常：`fnos-<版本>` tag 打在合并提交上，回填提交在其之后）
- 载荷 **51 个文件 + 16 个目录**，manifest checksum `f0f5c32d61a95bb911c3b614ce4719f7`
- 冒烟（发布前，隔离端口 8799，不动设备上的 8788）：`/health` 200、面板 `/` 200、
  `/v1/models` 18 个模型、非流式回复「连通」且带 usage、日志无 Traceback
- 附件的 sha256 与仓库根 `fnpack.json`、`ccrabit/FnDepot` 源里登记的 `1.7.29` 条目一致

## 已知限制

- 上游 v1.7.6 起 `/v1/messages`（Anthropic 原生入口）默认关闭，需显式设
  `WB_ENABLE_ANTHROPIC_MESSAGES=1`；本包保持上游默认。
- 本包只面向飞牛 fnOS（`all` 平台，纯 Python 载荷），Windows/macOS 请用仓库里的便携包。
- 日志落库（SQLite）默认关闭；升级不会自动迁移历史 `usage/` 统计。
