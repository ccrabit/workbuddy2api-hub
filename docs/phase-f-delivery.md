# Phase F 交付说明：WorkBuddy2API-Hub 1.6.19（飞牛包，已发布）

> 本轮用户要求（m05838，逐字）：「上游项目更新了，并入最新的更新，同时GitHub自动并入并构建似乎没有生效，检查问题，查看fndepot仓库上架的要求，准备上架仓库，版本号同步和上游一致」
> 交付纪律（**发布前**的当时事实）：只出本地测试包——没 push、没打 tag、没发 Release、设备一个字没动（等你测完再决定）。
> **发布后状态（2026-10-10，你选了「确认，按完整顺序执行」之后）**：已 push `main`、已打并推送 annotated tag **`fnos-1.6.19`**、已由 CI 构建并发 Release（资产见 §1）、`fnpack.json` 已按**资产**指纹回填并推送。
> 设备状态请你以 §6 为准：**设备当前装的是 1.6.19**，是**你自己**用我在发布前交付的那份本地包装上去的；我方对设备自始至终只做只读核查（没有 install/upgrade/uninstall）。

## 1. 包与已发布资产

| 项 | 值 |
|---|---|
| 文件 | `dist/WorkBuddy2API-Hub_1.6.19_all.fpk` |
| 大小 | 577330 B（563.8 KiB） |
| sha256 | `71edade7833191f189ade8d1ca1938faa12db9d0cd90ec316c3596a86c11ac98` |
| manifest checksum | `27d6795c7ba2a4db89f1e82fabef6ef0`（= 包内 `app.tgz` 的 md5） |
| 载荷 | **40 个文件** = `server/` 35 个（25 个 `*.py` + `LICENSE`/`dashboard.html`/`fnpack.json`/`pricing/pricing.json`/`fndepot/ICON.PNG`/`release/portable.txt` + `wrt/openwrt/workbuddy2api/` 4 个）+ `ui/` 3 个 + `config/` 2 个，`.pyc` 与 `__pycache__` **0 命中** |
| 版本 / appname | `1.6.19` / `workbuddy2api`（**appname 故意不改**：数据目录、网关前缀、已装应用的身份都挂在它上面） |
| 显示名 | `WorkBuddy2API-Hub` |
| **已发布 Release 资产** | tag `fnos-1.6.19` 的 Release（id `408987082`，published `2026-10-10T14:03:36Z`）挂的是 **CI 构建**的 `WorkBuddy2API-Hub_1.6.19_all.fpk`：**577842 B**、sha256 `3d341706c6fec4f7620ad75bba49fd3347b1b7c32c41d51cd8a4238c52f8a34c`、app.tgz md5 `806ce4e9ac0cda75485d34ed04657230`。它与上面这份**载荷逐文件相同、gzip 外壳字节不同**（原因见 §7 R22）⇒ `fnpack.json` 填的是**资产**的值 |

**装法**：应用中心 →「手动安装」→ 选这个 fpk。设备当前装的是 1.6.19 ⇒ 数字上可以原地升级/覆盖安装，**不需要卸载**（卸载会带走 `/vol1/@appdata/workbuddy2api` 里的账号/用量，除非先把 `wizard/uninstall` 挪开）。这份重建包与设备上那份**同版本号**，区别只是它已剔除 R19 那 3 个 `release/__pycache__/*.pyc`（内容其余部分逐字节相同）。

**升级后请重点看**：
1. 应用中心点「打开」→ 是否**免密**直接进面板（这是本轮要修的毛病：以前飞牛会话老化后又会弹密码）。
2. 面板外观：浅/深主题、运行日志窗口配色是否跟主题一起变、深色下鼠标移动高亮是否已经柔化。
3. 数据看板：token 数量单位（K/M）是否跟着数值自动换、单位是否显示出来；模型分布明细里「每 M tokens 对应积分」是否在**同一个模型小框内**分行显示。
4. 设置页「使用说明」里 API 地址与应急地址是否写清。
5. 账号还在、积分还在（升级不清数据）。

## 2. 对应你提的五件事

### 2.1 上游并入（已完成）
- 并入 `upstream/main` = `e6902e2`：v1.6.11 → **v1.6.19** 全部版本更新记录，外加 v1.6.19 之后的 34 个提交。
- 合并提交：`db9e58b`「Merge upstream/main (v1.6.19 + 34 commits) into the fnOS fork」，父提交 316eb8f（= 我们上次发布的 `v1.6.17.1`）。这一版**就是已发布的内容**（tag `fnos-1.6.19` → `26c2bcc`）。
- **发布后上游又走了 22 个提交**（`upstream/main` = `5b5b5c1`，比 `e6902e2` 多 22 个；**上游最新 release tag 仍是 `v1.6.19`**，所以没有新版本号、不触发自动 tag）。已并入**本地**提交 `39a16f6`「Merge upstream/main (5b5b5c1) into the fnOS fork」（父 `3d54173` + `5b5b5c1`，**尚未 push**）：三页拆分（账号/任务与福利/数据看板）+ Buddy 加油站签到按钮与状态卡片 + 账号工具栏文案统一，冲突仍只在 `README.md` / `dashboard.html` 两处，解析口径与上面一致（`dashboard.html` 保留上游三页结构、把我们的「使用说明」整块搬回账号页内；README 套件数按合并后的树扫盘重算为 **122 个（92 py + 30 js）**）。
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
- **修复前真的红过（实证）**：旧版工作流 run `38043106684`（schedule，`2026-10-10T09:55:32Z`）**failure**，失败步骤正是「Mirror upstream tags」——也就是我们删掉的那一步，其后 5–7 步全 skipped。这说明你要我查的「自动并入没生效」属实，而且修复方向对。
- 诚实说明：**修好之后那套工作流仍没在真实 GitHub 上跑过一次**（自然运行要等下一个 cron 窗口；我会在 push 后用 `workflow_dispatch` 手动触发一次证明它绿）。

### 2.3 FnDepot 上架准备（材料已备，差 Release 资产与你的决定）
- 已落盘：仓库根 `fnpack.json`（外部应用源 V2）+ `fndepot/{ICON.PNG,README.md}`，用 FnDepot 中心仓库自己的校验器 `validate_v2_app()` / `parse_and_fingerprint()` 跑过，`(True, "ok")`。
- **上架机制实测更正**：FnDepot 每天 16:00 UTC 用 GitHub 搜索自动生成 `valid_sources.txt`。召回有两条路——① 仓库搜索（这一支**只保留仓库名含 "fndepot" 的**）；② 代码搜索 `filename:fnpack.json` 与 `filename:fnpack.json+fork:true`（这两支**没有名字过滤**）。实跑 `GET /search/code?q=filename:fnpack.json` → `total_count=41`，里面 `RROrg/fn-apps`、`qilin-zhu/LitePan-fpk` 等名字都不含 fndepot。
  ⇒ 结论：**不必新建仓库**——注意前提（终验登记项 R15）：GitHub 的代码搜索索引的是**默认分支**，所以「**push 之后**才具备被召回的条件」。风险面：我们的仓库是上游的 fork，FnDepot 的查重规则里有「Fork 输给非 Fork」——但**不是无条件**（只在配对已判高重复时才生效），且现在**没有对手**（上游没有 `fnpack.json`）；上游哪天也做飞牛包，我们按血缘会判负。要兜底可以另建一个非 fork、名字带 `fndepot` 的仓库专门承载 `fnpack.json`（这需要你同意）。
- **R15 已解除**：`fnpack.json` 与 `fndepot/ICON.PNG` 现在都在 `origin/main` 上，匿名查 `GET /repos/ccrabit/workbuddy2api-hub/contents/{fnpack.json,fndepot/ICON.PNG}` 均 **HTTP 200**、raw 可读，字段正确。
- **`sha256` / `size` 已回填**（不再是占位 0）：按**已发布 Release 资产**的值填 —— `sha256 = 3d341706c6fec4f7620ad75bba49fd3347b1b7c32c41d51cd8a4238c52f8a34c`、`size = 577842`、`updated_at = 2026-10-10T22:03:36+08:00`，提交 `3d54173` 已 push。`download_url` 指向 `releases/download/fnos-1.6.19/WorkBuddy2API-Hub_1.6.19_all.fpk`，该资产已存在。
- **实际收录还没发生**：实测 FnDepot 中心仓库的 `valid_sources.txt`（`:.../contents/valid_sources.txt`）当前 **62 行、不含我们**；GitHub 代码搜索 `filename:fnpack.json+fork:true` 的 `total_count = 14` 里也没有我们（跨页只取首页 100 条，索引是否追上要看它每天 16:00 UTC 的重生成）。已设提醒复检。

### 2.4 版本号与上游一致（已改）
- 包版本 = **上游最新 release tag 的三段号** = `1.6.19`，**删掉第四位发布号**（上一版是 1.6.17.1）。
- 我们自己的发布 tag 改为 **`fnos-X.Y.Z`**（如 `fnos-1.6.19`）。原因是上游新增了 `.github/workflows/release.yml`，它由 `push: tags: ["v*"]` 触发并创建 draft release；我们继续用 `v*` 会**双触发**并产生两个 draft release。改前缀后上游那条流水线永不触发。
- `scripts/build-fpk.sh`：HEAD 上有 `fnos-*` tag 就用它的三段号；没有就退回「上一个 `fnos-*` → 上游可达最新 `vX.Y.Z`」，并带 `-alpha<提交数>` 后缀。发布时 tag `fnos-1.6.19` 正挂在 `26c2bcc`，因此 `build-fpk.yml` 里「tag 名 vs `--print-version`」那道门一次通过；现在主树已领先该 tag 24 个提交，`--print-version` = `1.6.19-alpha24`。
- 本测试包是显式 `VERSION=1.6.19` 构建的；`build-fpk.yml` 的 `TAG_REF` 只认 `fnos-*`（`v*` 仅作历史兼容），不匹配时 `::error::` 并拒绝发布。
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
| `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.19_all.fpk` | **71 passed / 0 failed**（在 tag 提交 `fnos-1.6.19` 的工作树里跑：「包就是这棵树构建的」真跑并通过）。**从主树跑是 69 passed / 1 failed**——唯一失败名 `every packaged file is byte-identical to the tree`，因为主树已领先该 tag 24 个提交（第二次上游合并动了 6 个载荷文件），属「发布后稳态」，不是包的问题 |
| `bash scripts/verify-fpk.sh <已发布资产>` | **71 passed / 0 failed**（把 Release 资产下载回来跑） |
| `python3 tests/run_all.py --jobs 4` | 见 §4.1 / §4.3 |
| 包结构 | 40 个载荷文件（`server/` 35 + `ui/` 3 + `config/` 2）、25 个 server `*.py` 全部可解析、`__pycache__`/`*.pyc` 零命中、port 8788、`wb_export.py` 在包内 |
| 独立终验（F5/F9） | 见 §4.2 / §4.3 |

### 4.1 全量套件（发布时）
`python3 tests/run_all.py --jobs 4` → **121 passed / 0 failed / 0 skipped**（57.7s，exit 0）。
（F5 改写我之前是 `120 passed / 1 failed`——那一条红就是终验自己的 `tests/_test_phase_e_verify.py` 还钉着上一版 Phase E 的契约；终验按新契约重写并新增 e13–e16 后全绿。套件真数从 120 变 121 是因为新增了 FnDepot 源套件。）

### 4.2 独立终验（`docs/phase-f-verify.md`，17 段）
| 门 | 结果 |
|---|---|
| `python3 tests/_test_phase_e_verify.py` | **PASS=334 / FAIL=0 / SKIP=3**（3 条 SKIP 都带理由：uid 65534 探针在沙箱里跑不了、HEAD 无 tag、README 有未提交改动） |
| `python3 tests/run_all.py --jobs 4` | **121 passed / 0 failed / 0 skipped**（57.7s） |
| `bash scripts/verify-fpk.sh <包>` | **70 passed / 0 failed**（发布前那份 601800 B 的包；发布后重建的 577330 B 那份在 tag 工作树里是 71/0） |
| 包指纹（独立核过） | 40 个载荷文件、`server/**` 逐字节一致、不含 accounts/usage/tests/docs/dist/build/scripts/fnos/.git |

终验自己独立复现的关键事实（不是复述我的结论）：
- **合并正确性**：`db9e58b` 的两个父正是 `316eb8f` + `e6902e2`；全仓 `<<<<<<<`/`=======`/`>>>>>>>` 三个模式**零命中**；上游 `release.yml` 一字未改（上游 workflow 里只有 `tests.yml` 被我们改了触发条件）。
- **版本契约红/绿门**：拿**修复前**的脚本（`git show 55dfad2:scripts/build-fpk.sh`）在同一 fixture 上实测 `1.6.10.3`（重现了当初的 CI 红），现行脚本 → `1.6.10-alpha3`；HEAD 挂 `fnos-1.6.19` → `1.6.19`；`sync-upstream.yml` 已无任何镜像上游 tag / `push --tags`。
- **FnDepot 源**：过中心仓库校验器 `parse_and_fingerprint` / `validate_v2_app` 均为 True，签名 `workbuddy2api|1.6.19`。
- **登记项 R15–R18**（都不是代码缺陷，FAIL=0）：R15 = 上述「push 之后才可被索引」的前提（**已解除**）；R16 = `fnpack.json` 的 `sha256`/`size` 曾为占位（**已按 Release 资产回填**）；R17 = 本 §4.2 原本是占位（已回填）；R18 = 两个上游 workflow 在我们树里多了可执行位（已 `chmod 644`）。

### 4.3 第二次上游合并之后（F9 终验，`docs/phase-f-verify.md`）
- 合并 `39a16f6`（父 `3d54173` + `upstream/main` = `5b5b5c1`）落盘后，终验套件按新契约重写（把写死的历史 SHA 与「HEAD 上的 tag」全部改成状态感知）：
  - `python3 tests/_test_phase_e_verify.py` → **PASS=351 / FAIL=0 / SKIP=3**（17 段：e1 10、e2 14、e2b 4/0/1、e3 33、e4 26、e5 60、e6 7、e7 10、e8 15/0/2、e9 35、e10 8、e11 11、e12 13、e13 37、e14 31、e15 22、e16 15）。
  - `python3 tests/run_all.py --jobs 4` → **122 passed / 0 failed / 0 skipped**（122 = 92 个 Python + 30 个 JS，与 README 的套件数一致）。
  - **depth-1 浅克隆**：`PASS=253 / FAIL=0 / SKIP=15`，exit 0（这是 CI 的检出形态）；**Windows 形状**（删掉 `socket.AF_UNIX` / `socketserver.Unix*` / `os.geteuid` 的整棵进程树）整套 `run_all` 也 FAIL=0。
- 这三条敏感性证明（**改坏必红**，原始输出在 `docs/phase-f-verify.md` §2.13）：包副本里 `server/wb_export.py` 翻一位 → e5 变 `58/2`；已发布资产副本尾部多 1 字节 → e14 变 `30/1`；删掉发布流水线套件里一个 `cwd=` 调用点 → e13 变 `35/2`。
- 这次合并顺带暴露验收套件的一个**真实脆弱点**（R20）：它原来把历史对象（`db9e58b`）和「HEAD 上的 tag 是 v1.6.17.1」写死，于是 ①`push` 后 CI 的 depth-1 检出里根本没有 `db9e58b`、②发布后 HEAD 上的 tag 变成 `fnos-1.6.19`，两处都会让它在 **CI 三平台全红**（tests run `38058101228` / `38058324670`）。现已改成「先探对象在不在，不在就按项目名 SKIP 并给理由」，「能给出答案的不许退化成 SKIP」。

## 5. 真机状态（只读核查，我方未改设备）
- `/var/apps/workbuddy2api/manifest`：`version = 1.6.19`、`display_name = WorkBuddy2API-Hub`、`distributor = ccrabit`、`checksum = be761a0f2715cd903edcf8e88d4198f9`。
- **这个 checksum 就是「你自装的那份本地包」**（重建前的 601800 B 版，留证 `/tmp/wb-r19-old-dist-1.6.19.fpk`）——也就是我在发布前 `present` 给你的那份。时间线一致：`server/**` mtime 20:18、服务进程 20:19 起。⇒ **设备升级是你做的，我方只做只读核查**。
- 所以设备载荷 = 已发布资产载荷（40 个文件，逐字节相同）**+ 3 个额外的 `server/release/__pycache__/*.cpython-311.pyc`**（R19 的痕迹，对运行无影响；§6 已根治）。
- 真机端到端（socket 上**不带** `X-Trim-Username`）：`/panel/status` → `{authenticated: true, via_gateway: true, panel_password_required: true, direct_port: 8788}`；`GET /app/workbuddy2api/` → 200，且带 `<base href="/app/workbuddy2api/">`、`window.__WB_BASE__="/app/workbuddy2api"`、`window.__WB_VIA_GATEWAY__=true`；banner 版本 `1.6.19`。⇒ **免密口径与挂载前缀契约在真机实装件上成立**（只剩「应用中心点击打开 / 安装过程 UI」没验）。
- 另记：设备面板仍是默认密码（`panel_password_is_default: true`），建议改掉。

## 6. 残余登记（都不影响这一版可用性）
| 编号 | 是什么 | 状态 |
|---|---|---|
| R19 | 本地构建比 CI 多 3 个 `release/__pycache__/*.pyc`（`--exclude='./__pycache__'` 只排仓根） | **已修**：`scripts/build-fpk.sh` 加 `--exclude='__pycache__'` / `--exclude='*.pyc'`，并加两条「红→绿」回归用例（修前必红：`[] != ['server/release/loose.pyc', …]`） |
| R20 | 验收套件在 CI 上从未绿过：写死历史 SHA + 写死「HEAD 上的 tag」 | **已修**（F9 重写，三环境 FAIL=0） |
| R21 | 排除式与 `.gitignore` 漂移（`logs/`、`suite-logs/`、`python/`、`.sdk-cache/`、`wrt/ipk/`、`wrt/apk/`、`.pytest_cache/`、`*.zip`、`*.pyo`…）；根治方向 = 暂存源改用 `git ls-files` | 本阶段**不修**（当前无实际污染），登记在 `docs/phase-f-version-policy.md` §10 |
| R22 | 同一提交两次构建的 `app.tgz` md5 不同（tar 成员目录 mtime + gzip 外壳）⇒ 只能比**载荷内容**或**已发布资产 sha256**；方向 `--mtime=@<提交时间> --sort=name --owner=0 --group=0 --numeric-owner` + `gzip -n` | 本阶段**不修**，登记在 `docs/phase-f-version-policy.md` §10 |
| R23 | 本文档原先把设备版本写成 1.6.17.1，与设备实况（1.6.19，你自装）不符 | **已修**（§1 / §5） |

## 7. 还没做 / 需要你决定

**没做**
- 修好后的同步工作流**仍未在真实 GitHub 上跑过**（push 之后我会用 `workflow_dispatch` 手动触发一次证明它绿）。
- FnDepot **尚未实际收录我们**（中心仓库 `valid_sources.txt` 实测 62 行、不含我们；GitHub 代码搜索索引也没追上）。
- 应用中心「点击打开」的安装后 UI 流程、真机移动端自适配，需要你在浏览器里看一眼。
- 终验报告 §5 另列 6 条「做不到」的：真实 GitHub 跑同步、真机装包、FnDepot 实际收录、push/tag/Release 动作本身、网关 socket 上 `/v1` 免 key 的真机影响面、真 Windows 腿（以 CI 为准）。

**发布收尾（2026-10-10 你批准「按完整顺序执行」后已完成）**
1. ✅ push `main`：`316eb8f → 26c2bcc`。
2. ✅ 打并推送 annotated tag **`fnos-1.6.19`** → `build-fpk.yml` 跑通、**自动创建 Release**（id `408987082`）并挂上 CI 构建的包。
3. ✅ 从 Release 读回**资产**的 sha256 与字节数（注意：CI 构建的包与本机 `dist/` 那份**载荷逐文件相同、gzip 字节不同**，所以 `fnpack.json` 填的是资产的值）。
4. ✅ 回填 `fnpack.json` 的 `sha256`/`size` 并单独提交推送（`3d54173`，不需要新 tag）。
5. ⏳ FnDepot 中心仓库每天 16:00 UTC 重生成 `valid_sources.txt` —— 等它收录。

**需要你决定 / 动手**
1. GitHub 仓库 **Issues 开关**：同步冲突时「开 issue」依赖它（我的 PAT 没有 administration 权限，要你到 Settings → General → Features 勾上）。
2. 是否要为 FnDepot **另建一个非 fork、名字含 `fndepot` 的仓库**做收录兜底？我倾向**先不建**，用现有仓库加代码搜索这条路。
3. 建议轮换/删除 `/root/.gh-token`（它在本会话里出现过）。
4. 设备面板还是默认密码，建议改掉。
