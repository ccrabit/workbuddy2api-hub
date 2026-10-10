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
| `WorkBuddy2API-Hub_1.6.19_all.fpk` | 591004 | `ac11f7f6700902eeef8c9e3342d1d1e9ae3b16b0c257b3964b3488ead6e817c7` |
| `WorkBuddy2API-Hub_1.6.19_all.fpk.sha256` | 99 | — |

校验：`sha256sum -c WorkBuddy2API-Hub_1.6.19_all.fpk.sha256`
包内 `manifest`：`version = 1.6.19`、`display_name = WorkBuddy2API-Hub`、`service_port = 8788`、
`checksum = a3ebd7e23b35f1927f2242934f6a1757`（= 包内 `app.tgz` 的 md5）、39 个载荷文件。

## 安装 / 升级

1. 应用中心 → 手动安装 → 选本 Release 的 `.fpk`（原地升级/覆盖安装，端口仍是 8788）。
2. 升级前建议备份 `/vol1/@appdata/workbuddy2api/`（至少 `accounts/` 与 `usage/`）。
3. **卸载会清掉数据目录**（除非先把 `wizard/uninstall` 挪开），能覆盖安装就不要卸载。
4. 装完点应用中心的「打开」：应该**免密**直接进面板（飞牛已登录用户不再被问面板密码）。

## 本版包含

- **并入上游最新代码**：v1.6.11 → v1.6.19 的全部更新，外加 v1.6.19 之后的 22 个提交
  （面板拆成「账号 / 任务与福利 / 数据看板」三页、Buddy 加油站签到按钮与状态卡片、
  账号工具栏文案统一、上游 `wb_upstream_pool.py`/`wb_agents.py`/`wb_updates.py` 等新模块）。
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

- `python3 tests/run_all.py --jobs 4` → `122 passed / 0 failed / 0 skipped`（53.5s）
- `python3 tests/_test_phase_e_verify.py` → `PASS=348 / FAIL=0 / SKIP=3`
- `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.19_all.fpk` → `71 passed, 0 failed`
  （tag 挂在 HEAD 上时；无 tag 时少 1 条 tag 断言 = 70/0）
- 附件与本机 `dist/` 文件 sha256 一致（`ac11f7f6…`，下载回来复算过）

## 已知限制

- **构建不可复现**：同一棵树两次构建的 `.fpk` 字节不同（载荷文件 mtime 进 tar），
  所以校验请以本 Release 的 sha256 为准，别用「重建一遍再比」。
- 设备上如果装的是更早那次发布的同版本包（Phase F 的 CI 构建），覆盖安装即可；
  它与本包的差别是第二次上游合并涉及的 6 个文件 + 本包不再内嵌 `fnpack.json`。
- 自动同步/自动构建已按维护者要求删除：上游更新需要人工合并后再本地发布。
- 飞牛应用中心的「点击打开」流程与真机移动端观感仍需人工确认。
