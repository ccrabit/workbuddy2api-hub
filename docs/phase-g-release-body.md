# WorkBuddy2API-Hub 1.6.19（飞牛原生 fpk）

本次发布对应上游 `v1.6.19`（并含其后的上游提交，上游没有发新版本号）。包名
`WorkBuddy2API-Hub_1.6.19_all.fpk`，`appname` 仍是 `workbuddy2api` —— 覆盖安装即可，
数据目录 `/vol1/@appdata/workbuddy2api`（账号、用量、设置）不变。

**这版开始，发布不再经 CI**：包是在维护者机器上用 `scripts/build-fpk.sh` 构建、
用 `scripts/gh-release.py` 上传的，所以**下面这个附件与本机 `dist/` 里的文件逐字节相同**
（下载回来比过 sha256）。GitHub 上不再有任何自动构建/自动同步工作流。

## 文件与校验

| 文件 | 字节数 | sha256 |
| --- | --- | --- |
| `WorkBuddy2API-Hub_1.6.19_all.fpk` | 626248 | `e65dcb844df7ede523e990c33e3e661e27d6c73e0a9770592d76e006d610505d` |
| `WorkBuddy2API-Hub_1.6.19_all.fpk.sha256` | 99 | — |

校验：`sha256sum -c WorkBuddy2API-Hub_1.6.19_all.fpk.sha256`
包内 `manifest`：`version = 1.6.19`、`display_name = WorkBuddy2API-Hub`、`service_port = 8788`、
`checksum = ff0742cf816e35077f5ce51f54de27f5`（= 包内 `app.tgz` 的 md5）、39 个载荷文件。

## 安装 / 升级

1. 应用中心 → 手动安装 → 选本 Release 的 `.fpk`（原地升级/覆盖安装，端口仍是 8788）。
2. 升级前建议备份 `/vol1/@appdata/workbuddy2api/`（至少 `accounts/` 与 `usage/`）。
3. **卸载会清掉数据目录**（除非先把 `wizard/uninstall` 挪开），能覆盖安装就不要卸载。
4. 装完点应用中心的「打开」：应该**免密**直接进面板（飞牛已登录用户不再被问面板密码）。

## 本版包含

- **并入上游最新代码**：v1.6.11 → v1.6.19 的全部更新，外加 v1.6.19 之后的 **79 个提交**
  （面板拆成「账号 / 任务与福利 / 数据看板」三页、Buddy 加油站签到按钮与状态卡片、
  上游 `wb_upstream_pool.py`/`wb_agents.py`/`wb_updates.py` 等新模块；本轮又并进 25 个：
  账号页可独立成一个页签并新增签到与活跃记录看板、所有数据表支持点表头排序、
  顶部页签可收起、更新检查设置卡、剩余用量优先调度（默认关）与超限页内轮转暖号回退、
  剩余用量估算第二/三批与限额联动）。
- **保留并重贴飞牛层**：统一网关免密入口（socket peer 校验通过即登录，不再要求网关注入
  用户头，解决「飞牛里开着开着又要密码」）、`--unix-socket`/`--base-path` 挂载前缀、
  仅挂载态注入 `<base href>` 与 `window.__WB_*`、cockpit 兼容导出、主题/移动端、看板 token
  单位自动切换与「每 M tokens 积分」列、设置页「使用说明」。
- **修掉的真缺陷**：AF_UNIX 上 `TCP_NODELAY` 让网关路径每个请求都失败；缺省直连被注入
  飞牛上下文（上游要求逐字节一致）；ETag 缺网关上下文分量（换用户会拿到 304 用上别人的注入页）；
  上游新 `fmtTok` 静默覆盖我们的精确 token 单位；包内嵌自指 `fnpack.json` 导致校验永久 1 条红。
- **发布机制**：GitHub 上删掉全部自建工作流（只剩上游自带、只在 `v*` 触发的 `release.yml`），
  改成本地 `scripts/build-fpk.sh` + `scripts/gh-release.py`（runbook：`docs/phase-g-local-release.md`）。

## 验证数字

- `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.19_all.fpk` → **71 passed, 0 failed**
  （tag 挂在 HEAD 上时；构建那一刻 HEAD 还没 tag，那时是 70/0）
- `python3 tests/run_all.py --jobs 4` → **121 passed / 7 failed / 0 skipped**。这 7 条红**没有一条是本仓库引入的**：
  - **6 条在纯上游 `upstream/main`（不含本仓库任何改动）上可逐条复现**——
    `_test_activity_history.js`（`loadActivityToday is not defined`）、`_test_page_nav.js`、
    `_test_settings_load.js`、`_test_settings_update_ui.js`、`_test_model_cooldowns.js`、
    `_test_run_all_encoding.py`（它拿 `_test_settings_load.js` 当「已知必绿」的夹具，被上一条带红）。
    即**上游这一版自己就带着 6 个红套件**。本仓库不修上游的测试文件——改了下次并入必冲突。
  - 第 7 条是本仓库的静态验收套件 `tests/_test_phase_e_verify.py`：它按设计把「已发布资产 == 树」
    「HEAD 上的 tag」「设备 / 包一致性」钉成断言，每次合并并重发布后都要按新契约重钉一轮。
- 附件与本机 `dist/` 文件 sha256 一致（`e65dcb84…`，下载回来复算过）

## 已知限制

- **构建不可复现**：同一棵树两次构建的 `.fpk` 字节不同（载荷文件 mtime 进 tar），
  所以校验请以本 Release 的 sha256 为准，别用「重建一遍再比」。
- 设备上如果装的是更早那次发布的同版本包（Phase F 的 CI 构建），覆盖安装即可；
  实测差别只有 7 项：内容不同的 6 个载荷文件（`dashboard.html`、`wb_proxy.py`、`wb_accounts.py`、
  `wb_scheduler.py`、`wb_tasks.py`、`wb_settings.py`）＋旧包里多一个 `server/fnpack.json`
  （本包不再内嵌，它是自指的发布清单）。其余 33 个载荷文件逐字节相同。
- 自动同步/自动构建已按维护者要求删除：上游更新需要人工合并后再本地发布。
- 飞牛应用中心的「点击打开」流程与真机移动端观感仍需人工确认。
