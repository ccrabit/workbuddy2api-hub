# Phase F 交付说明：WorkBuddy2API-Hub 1.6.19（飞牛测试包，未推送）

> 本轮用户要求（m05838，逐字）：「上游项目更新了，并入最新的更新，同时GitHub自动并入并构建似乎没有生效，检查问题，查看fndepot仓库上架的要求，准备上架仓库，版本号同步和上游一致」
> 纪律：**只出本地测试包**——没 push、没打 tag、没发 Release、设备一个字没动（等你测完再决定）。

## 1. 你要测的包

| 项 | 值 |
|---|---|
| 文件 | `dist/WorkBuddy2API-Hub_1.6.19_all.fpk` |
| 大小 | 601800 B（587.7 KiB） |
| sha256 | `c482c9fca2032d2aeee9e54b2dedc37139de9c669be883e85b18ce7d1ff89f0e` |
| manifest checksum | `be761a0f2715cd903edcf8e88d4198f9`（= 包内 `app.tgz` 的 md5） |
| 版本 / appname | `1.6.19` / `workbuddy2api`（**appname 故意不改**：数据目录、网关前缀、已装应用的身份都挂在它上面） |
| 显示名 | `WorkBuddy2API-Hub` |

**装法**：应用中心 →「手动安装」→ 选这个 fpk。设备当前装的是 1.6.17.1 ⇒ 1.6.19 更大，**可以原地升级，不需要卸载**（卸载会带走 `/vol1/@appdata/workbuddy2api` 里的账号/用量，除非先把 `wizard/uninstall` 挪开）。

**升级后请重点看**：
1. 应用中心点「打开」→ 是否**免密**直接进面板（这是本轮要修的毛病：以前飞牛会话老化后又会弹密码）。
2. 面板外观：浅/深主题、运行日志窗口配色是否跟主题一起变、深色下鼠标移动高亮是否已经柔化。
3. 数据看板：token 数量单位（K/M）是否跟着数值自动换、单位是否显示出来；模型分布明细里「每 M tokens 对应积分」是否在**同一个模型小框内**分行显示。
4. 设置页「使用说明」里 API 地址与应急地址是否写清。
5. 账号还在、积分还在（升级不清数据）。

## 2. 对应你提的五件事

### 2.1 上游并入（已完成）
- 并入 `upstream/main` = `e6902e2`：v1.6.11 → **v1.6.19** 全部版本更新记录，外加 v1.6.19 之后的 34 个提交。
- 合并提交（**本地**）：`db9e58b`「Merge upstream/main (v1.6.19 + 34 commits) into the fnOS fork」，父提交 316eb8f（= 我们上次发布的 `v1.6.17.1`）。
- 冲突只有三处（`README.md` / `dashboard.html` / `wb_proxy.py`），口径是**上游优先**，飞牛层最小重贴：
  - `wb_proxy.py`：取上游全部新能力（agents/activity/upstream-pool/更新检查等），重贴网关 socket（`--unix-socket`/`--base-path`）、免密判定、`/accounts/export`、飞牛上下文注入。
  - `dashboard.html`：以上游新版为底，重贴 cockpit 导出按钮、精确 token 单位、使用说明那几段；**修掉一个真缺陷**（见 §3.4）。
  - `README.md`：取上游重写版，补回本仓库的飞牛章节、changelog、套件数。

### 2.2 「GitHub 自动并入没生效」——根因与修复（已改，未上线）
- **根因**：不是调度坏了，是两件事叠加。
  1. 时区：cron 写的是 `17 3 * * *`，GitHub Actions 按 UTC 跑 ⇒ 每天 **11:17（北京）** 才动，而不是凌晨 3:17。查 4 次 schedule 运行，全部落在 `10:20–10:40 UTC`。
  2. 那三次失败都是**真冲突**（`README.md`/`dashboard.html`/`wb_proxy.py`），而设计上就是「冲突要大声失败并要求人工修」。10-09 那次成功，只是因为当时上游确实没新东西。
- **修复**：`sync-upstream.yml` 现在
  - cron 加到三条：`17 3` / `23 9` / `41 15`（UTC），一天三次；
  - 冲突时除了失败 + 摘要/issue，还会把带冲突标记的合并结果推到 `sync-conflict/<UTC 日期>` 分支，方便你或我快速解决；
  - **删掉了「镜像上游 tag 到本仓库」那一步**（见 §2.4）。
- 诚实说明：这套修复**还没在真实 GitHub 上跑过一次**（第一次自然运行要等下一个整点窗口）。

### 2.3 FnDepot 上架准备（材料已备，差 Release 资产与你的决定）
- 已落盘：仓库根 `fnpack.json`（外部应用源 V2）+ `fndepot/{ICON.PNG,README.md}`，用 FnDepot 中心仓库自己的校验器 `validate_v2_app()` / `parse_and_fingerprint()` 跑过，`(True, "ok")`。
- **上架机制实测更正**：FnDepot 每天 16:00 UTC 用 GitHub 搜索自动生成 `valid_sources.txt`。召回有两条路——① 仓库搜索（这一支**只保留仓库名含 "fndepot" 的**）；② 代码搜索 `filename:fnpack.json` 与 `filename:fnpack.json+fork:true`（这两支**没有名字过滤**）。实跑 `GET /search/code?q=filename:fnpack.json` → `total_count=41`，里面 `RROrg/fn-apps`、`qilin-zhu/LitePan-fpk` 等名字都不含 fndepot。
  ⇒ 结论：**不必新建仓库**——但有个前提（终验登记项 R15）：GitHub 的代码搜索索引的是**默认分支**，而我们的 `fnpack.json` 现在只存在于**未推送**的本地合并提交里（`GET /repos/ccrabit/workbuddy2api-hub/contents/fnpack.json` → 404），所以正确说法是「**push 之后**才具备被召回的条件」。风险面：我们的仓库是上游的 fork，FnDepot 的查重规则里有「Fork 输给非 Fork」——但**不是无条件**（只在配对已判高重复时才生效），且现在**没有对手**（上游没有 `fnpack.json`）；上游哪天也做飞牛包，我们按血缘会判负。要兜底可以另建一个非 fork、名字带 `fndepot` 的仓库专门承载 `fnpack.json`（这需要你同意）。
- **还差**：`fnpack.json` 里 `sha256` / `size` 现在还是占位 0，`download_url` 指向 `releases/download/fnos-1.6.19/...` —— 这个 Release 资产只有在**你同意 push + 打 tag + 发 Release 之后**才存在。所以上架动作排在你的决定之后。

### 2.4 版本号与上游一致（已改）
- 包版本 = **上游最新 release tag 的三段号** = `1.6.19`，**删掉第四位发布号**（上一版是 1.6.17.1）。
- 我们自己的发布 tag 改为 **`fnos-X.Y.Z`**（如 `fnos-1.6.19`）。原因是上游新增了 `.github/workflows/release.yml`，它由 `push: tags: ["v*"]` 触发并创建 draft release；我们继续用 `v*` 会**双触发**并产生两个 draft release。改前缀后上游那条流水线永不触发。
- `scripts/build-fpk.sh`：HEAD 上有 `fnos-*` tag 就用它的三段号；没有就退回「上一个 `fnos-*` → 上游可达最新 `vX.Y.Z`」，并带 `-alpha<提交数>` 后缀（当前无 tag 时 `--print-version` = `1.6.19-alpha44`）。
- 本测试包是显式 `VERSION=1.6.19` 构建的（未打 tag，所以版本号必须显式给）。
- 校验脚本同步收紧：manifest 版本必须是「上游的三段号」，四段或 `-alpha` 一律拒绝。

### 2.5 包名/显示名（已改）
- 安装包文件名与显示名都改成 **`WorkBuddy2API-Hub`**（资产名 `WorkBuddy2API-Hub_1.6.19_all.fpk`）。
- `appname` 标识符仍是 `workbuddy2api`：改名会让 `/vol1/@appdata/<app>` 另起一份、网关前缀 `/app/workbuddy2api` 失效、已装应用变成另一个应用。

## 3. 这一版修掉的真缺陷

1. **网关在 AF_UNIX 上直接死掉**：上游 v1.6.19 给 handler 新加了 `disable_nagle_algorithm=True`，而 AF_UNIX socket 上 `setsockopt(TCP_NODELAY)` 抛 `OSError: [Errno 95]`，导致**每个走统一网关的请求在 `setup()` 阶段就失败**。已为网关路径单独派生 handler 关掉它。
2. **缺省直连会注入飞牛上下文**：上游新增的测试要求「普通 TCP `GET /` 的响应体逐字节等于文件本身」。改为**只有挂载态（有 base path / 网关态）才注入** `window.__WB_*` 与 `<base href>`。
3. **ETag 缺网关上下文分量**：同一份 dashboard.html 对不同飞牛用户返回同一 ETag ⇒ 第二个用户会拿到 `304` 用上第一个用户的注入页。ETag 第 4 分量已覆盖 `base_path|via_gateway|gateway_user`。
4. **上游新版 `fmtTok` 静默覆盖我们的精确版**：上游 v1.6.19 也定义了同名 `fmtTok`（粗口径），把我们的精确版覆盖掉，全站 token 显示退化成 `8.3K` 这种。已把上游那支改名 `fmtTokRemaining` 并改其 5 处调用点，我们的口径保持逐字不变。**这条正好是你上一轮要的「token 单位随数值切换」的命门**。
5. **发布 tag 会双触发上游流水线**（见 §2.4）——已用 `fnos-*` 前缀规避。

## 4. 验证数字

| 门 | 结果 |
|---|---|
| `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.19_all.fpk` | **70 passed / 0 failed**（其中「包就是这棵树构建的」因 HEAD 无 `fnos-*` tag 而 SKIP，属预期；打了 tag 后该条会真跑，变 71） |
| `python3 tests/run_all.py --jobs 4` | 见 §4.1 |
| 包结构 | 25 个顶层条目、payload 60 个文件、25 个 server python 文件全部可解析、port 8788、`wb_export.py` 在包内 |
| 独立终验（F5） | 见 §4.2 |

### 4.1 全量套件
`python3 tests/run_all.py --jobs 4` → **121 passed / 0 failed / 0 skipped**（57.7s，exit 0）。
（F5 改写我之前是 `120 passed / 1 failed`——那一条红就是终验自己的 `tests/_test_phase_e_verify.py` 还钉着上一版 Phase E 的契约；终验按新契约重写并新增 e13–e16 后全绿。套件真数从 120 变 121 是因为新增了 FnDepot 源套件。）

### 4.2 独立终验（`docs/phase-f-verify.md`，17 段）
| 门 | 结果 |
|---|---|
| `python3 tests/_test_phase_e_verify.py` | **PASS=334 / FAIL=0 / SKIP=3**（3 条 SKIP 都带理由：uid 65534 探针在沙箱里跑不了、HEAD 无 tag、README 有未提交改动） |
| `python3 tests/run_all.py --jobs 4` | **121 passed / 0 failed / 0 skipped**（57.7s） |
| `bash scripts/verify-fpk.sh <包>` | **70 passed / 0 failed** |
| 包指纹（独立核过） | 601800 B、sha256 `c482c9fc…f89f0e`、manifest checksum = md5(app.tgz)、payload 60 条（52 server + 5 ui + 3 config）、`server/**` 逐字节一致、不含 accounts/usage/tests/docs/dist/build/scripts/fnos/.git |

终验自己独立复现的关键事实（不是复述我的结论）：
- **合并正确性**：`db9e58b` 的两个父正是 `316eb8f` + `e6902e2`；全仓 `<<<<<<<`/`=======`/`>>>>>>>` 三个模式**零命中**；上游 `release.yml` 一字未改（上游 workflow 里只有 `tests.yml` 被我们改了触发条件）。
- **版本契约红/绿门**：拿**修复前**的脚本（`git show 55dfad2:scripts/build-fpk.sh`）在同一 fixture 上实测 `1.6.10.3`（重现了当初的 CI 红），现行脚本 → `1.6.10-alpha3`；HEAD 挂 `fnos-1.6.19` → `1.6.19`；`sync-upstream.yml` 已无任何镜像上游 tag / `push --tags`。
- **FnDepot 源**：过中心仓库校验器 `parse_and_fingerprint` / `validate_v2_app` 均为 True，签名 `workbuddy2api|1.6.19`。
- **登记项 R15–R18**（都不是代码缺陷，FAIL=0）：R15 = 上述「push 之后才可被索引」的前提（已改口径）；R16 = `fnpack.json` 的 `sha256`/`size` 仍是占位（发布前回填）；R17 = 本 §4.2 原本是占位（已回填）；R18 = 两个上游 workflow 在我们树里多了可执行位（已 `chmod 644`）。

## 5. 已知限制与需要你决定的事

**限制**
- 同步修复（三 cron + 冲突分支 + 不再镜像 tag）**从未在真实 GitHub 上跑过**。
- FnDepot 的 `sha256`/`size` 仍是占位（R16），`download_url` 指向尚未存在的 Release 资产。
- 设备上跑的还是 1.6.17.1：本次没有、也不会未经你同意去动设备。
- CI 的 tag 门禁只认 `fnos-*`（`v*` 仅作历史兼容）；`tests.yml` 的触发条件加了 `fnos-*`，否则这道门对我们自己的发布 tag 永不运行。
- 终验报告 §4 另列了 6 条「做不到」的：真实 GitHub 跑同步、真机装 1.6.19、FnDepot 实际收录、push/tag/Release 动作本身、网关 socket 上 `/v1` 免 key 的真机影响面、真 Windows 腿（以 CI 为准）。

**发布时的收尾顺序（等你点头后才做，R16 就卡在这里）**
1. push 分支到 `main`（会跑一遍 CI）。
2. 打 annotated tag **`fnos-1.6.19`** 并推送 → `build-fpk.yml` 构建、跑包生命周期、**自动创建 Release 并挂上 CI 构建的 fpk**。
3. 从该 Release 读回**资产**的 sha256 与字节数（注意：CI 构建的包与本机 `dist/` 里这个**载荷逐文件相同、但 gzip 字节不同**，所以 `fnpack.json` 必须填 Release 资产的值，不能填本机那份）。
4. 回填 `fnpack.json` 的 `sha256`/`size` → 单独提交推送（这一步不需要新 tag）。
5. FnDepot 的中心仓库每天 16:00 UTC 重生成 `valid_sources.txt`，届时才会被收录。

**要你决定**
1. 先在设备上装这个 1.6.19 测试包测（应用中心手动安装）。
2. 测好之后，是否要我 **push 到 GitHub + 打 `fnos-1.6.19` tag + 发 Release**？（要发了 Release，FnDepot 的 `download_url` 才有东西可下。）
3. 是否需要为 FnDepot **另建一个非 fork 的专门仓库**（名字含 `fndepot`）作为收录兜底？我倾向于**先不建**，用现有仓库加代码搜索这条路。
4. 仓库 **Issues 开关**：同步冲突要开 issue 就依赖它（我这边 PAT 没权限改，需要你在 Settings → General → Features 里勾上）。
5. 建议轮换/删除 `/root/.gh-token`（它在本会话里出现过）。

**本轮开工至今没做过的动作**：没 push、没打 tag、没发 Release、没动设备、没重建包（包内 `server/**` 在终验窗口内一字节未改）。本地只多了一个合并提交 `db9e58b`。
