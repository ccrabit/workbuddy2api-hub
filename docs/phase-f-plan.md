# Phase F 方案：并入上游 v1.6.19、修好自动并入、上架 FnDepot、版本号跟上游一致

用户请求（m05838，逐字）：「上游项目更新了，并入最新的更新，同时GitHub自动并入并构建似乎没有生效，检查问题，查看fndepot仓库上架的要求，准备上架仓库，版本号同步和上游一致」

本文件是 Phase F 的权威规格。冲突口径、版本契约、写域纪律以本文件为准。

---

## 1. 取证结论（2026-10-10）

### 1.1 上游状态

| 项 | 值 |
| --- | --- |
| `upstream/main` | `e6902e2`（比 v1.6.19 还多 34 个提交） |
| 上游最新 release tag | `v1.6.19`（`55dbb9e`，2026-10-10 04:26 +0800），是 `upstream/main` 的祖先 |
| 上游前一个 release | `v1.6.18`（`c7e3ac2`，2026-10-09 21:46 +0800） |
| 我们（`phase-e/upstream-sync` = `origin/main`） | `316eb8f`，相对上游 **behind 147 / ahead 11** |
| 合并基 | `dbc6afd`（= v1.6.17 之后那条线） |

### 1.2 合并冲突面（已实测，`git merge --no-commit --no-ff upstream/main`）

- 双方都改过的文件只有 6 个：`.gitignore`、`README.md`、`dashboard.html`、`scripts/probe_max_tokens.py`、`wb_accounts.py`、`wb_proxy.py`。
- 真正冲突 3 个文件、8 段：
  - `README.md` 3 段：:149 套件数行、:357 `### v1.6.17.1` 段、:400-671 我们 changelog ↔ 上游 changelog（上游重写过 README）。
  - `dashboard.html` 3 段：:2833 账号工具栏、:4843 `getJSON`/`GETJSON_INFLIGHT`、:9719 用量渲染。
  - `wb_proxy.py` 2 段：:3565-4019（455 行，用量/统计区）、:11888-11942（55 行，面板渲染 ↔ 我们的 `inject_dashboard_context`）。
- 我们在这些文件上的净改动很小：`README.md` +33、`dashboard.html` +384、`wb_proxy.py` +372。
- 飞牛层（`fnos/**`、`scripts/build-fpk.sh`、`verify-fpk.sh`、`.github/workflows/{build-fpk,sync-upstream,tests}.yml`、`wb_export.py`、Phase E 测试与文档）**两边无交集**，改这些不会冲突。

### 1.3 Phase D 超集功能已按 m04805 丢弃（现状，不再回补）

Phase E 已把任务中心队列 / 模型锁池 / 暂停选号 / 积分 FEFO 明细留在 `phase-d/snapshot`，现树里**没有** `wb_credits.py`、`wb_taskcenter.py`，`dashboard.html` 里也没有 `/credits/summary`、`/tasks/center` 的引用（已实测计数为 0）。唯一保留的是 cockpit 兼容导出（`wb_export.py` + 看板按钮），因为上游只做导入。**Phase F 继续遵守这条，不再把 Phase D 的东西搬回来。**

### 1.4 「自动并入并构建没有生效」的根因（三条，全部有据）

1. **调度本身在跑，只是 GitHub 每天晚 ~7 小时**：`Sync from upstream` 共 4 次 schedule 运行，`created_at` 全是 10:20-10:40 UTC（cron 写的是 `17 3 * * *`）：10-06 10:24:50、10-07 10:20:27、10-08 10:40:13、10-09 10:39:26。今天（10-10 08:05 UTC 取证）**尚未运行**，按历史节奏约 10:20-10:40 UTC 才会跑。cron 行自 `06022a5` 写进文件后从未改过（`git log -S'17 3 * * *'` 只有那一个提交）。
2. **跑成功的那次确实无事可做**：10-09 10:39:26Z 那次 `success`，而上游 `v1.6.18` 是当晚 21:46 +0800 才发，比它晚 3 小时；`v1.6.19` 是今天 04:26 +0800。所以那次不是「失效」，是「当时没有新东西」。
3. **真正会一直红的是冲突**：10-06/07/08 三次失败全部是同一批文件冲突（README/dashboard/wb_proxy，与 §1.2 同源）。设计上「冲突 = 大声失败」，所以自动并入永远不会在两边都改同一批行时自己走完。

### 1.5 合并后会新出现的坑（必须处理）

上游新增了 `.github/workflows/release.yml`，触发条件是 `push: tags: ["v*"]`，会跑 Windows 矩阵并**创建 draft release**（ZIP/ipk/apk）。一旦它进入我们的默认分支：

- 我们的 `v*` 发布 tag 会同时触发 `build-fpk.yml` 和上游的 release.yml → 同一个 tag 两个 draft release 打架；
- `sync-upstream.yml` 现有的「镜像上游 tag 到 origin」步骤会把上游的 `v1.6.18`/`v1.6.19` 推进 origin → 也会触发上游的 release.yml。

**结论：我们的发布 tag 必须离开 `v*` 命名空间**（见 §2.1）。

### 1.6 FnDepot 上架要求（`EWEDLCM/FnDepot`，1032 stars，权威读的是它 README 的「外部应用源 V2 编写说明」）

- **两种被用户添加的方式**：① JSON 直链；② GitHub 仓库根地址 —— **仓库根目录必须有大小写完全正确的 `fnpack.json`**，客户端不探测别的文件名。
- **V2 顶层**：`schema_version` 必须是**字符串 `"2"`**；`source_info.name` / `source_info.author` 必填。
- **应用键名必须与 FPK manifest 的 `appname` 完全一致**（大小写敏感）→ 我们是 `workbuddy2api`。
- 应用必填：`display_name`、`desc`、`platform`（只允许 `all`/`x86`/`arm`）、`categories`（**只能**用固定九类：影音娱乐、系统工具、编程开发、AI赋能、生活服务、智能智控、教育学习、游戏地带、硬件驱动；最多两个，第一个为主分类）、`icon_url`、`run_as`（`package`/`root`）、`install_type`（`""`=存储空间 / `root`=系统空间）、`is_docker`（布尔）、`releases`。
- 可选：`preview_urls`（最多读 8 张）、`readme_url`、`bug_report_url`、`maintainer(_url)`、`distributor(_url)`、`service_port`、`details_url`（拆分模式）。
- `releases.<版本>.packages.{all|x86|arm}` 必填 `download_url`；**强烈建议 `sha256`（64 位十六进制，客户端强制校验）+ `size`（字节整数）**；版本键用可比较的 SemVer。
- URL 只允许 http/https；单源 JSON ≤2MB、单应用 ≤100 版本、单请求 ≤8 张预览图；图标建议 PNG/WebP <500KB。
- **不要冒用官方身份**：`source_info.author` / `maintainer` / `distributor` 不能是 FnDepot 或官方名（`generate_sources.py:is_forbidden_identity`）。
- **「上架」的真实机制**（读 `scripts/generate_sources.py` + `.github/workflows/update-sources.yml` 得到）：中心仓库每天 16:00 UTC 用 GitHub 搜索自动生成 `valid_sources.txt`（现 62 条），召回途径是
  1. 仓库搜索 `fndepot` / `fn depot`（±`fork:true`），**只有这一支**带有脚本内过滤 `if "fndepot" in full_name.lower()`（`generate_sources.py:344`，描述/topic 里含不算）；
  2. 代码搜索 `filename:fnpack.json` 与 `filename:fnpack.json+fork:true`（`generate_sources.py:352-356`）——**这两支没有任何名字过滤**，只取第一页 100 条；
  3. 脚本里硬编码的 `WHITELIST`。
  然后按仓库血缘 + `appname|version` 重叠查重（`process_overlap()`）：**Fork 永远输给非 Fork**（`generate_sources.py:280-300`），同源时后来创建者被剔除。
- **2026-10-10 Lead 更正（实测，推翻先前的过强结论）**：仓库名不含 fndepot 也能被收录——代码搜索这条路的候选**不做名字过滤**。用 PAT 实跑 `GET /search/code?q=filename:fnpack.json` → `total_count=41`，返回里 `RROrg/fn-apps`、`qilin-zhu/LitePan-fpk`、`mg6630/fnos-lxc` 都不叫 FnDepot；`+fork:true` → `total_count=14`，返回里确有 fork（如 `coder23j/FnDepot-arm`、`Soley911/fn`、`tzi-shue/FnDepot-1`）。所以 `ccrabit/workbuddy2api-hub`（上游 fork、根目录放 `fnpack.json`）**本身就可被召回**，不必须新建仓库。两个前提：① 仓库必须**公开**且 `fnpack.json` 在根目录（大小写一致）；② 上游 `ardeyouxipianyi/workbuddy2api-hub` 目前**没有** `fnpack.json`，所以 fork 判负规则现在没有对手——但上游哪天也做了 fnOS 包，我们的 fork 会按血缘判负。
  ⇒ 决策：**先走现有仓库**（用户已确认过不新建仓库就不新建）；把「新建一个非 fork、名字含 fndepot 的仓库（如 `WorkBuddy2API-FnDepot`）」留作风险备选，写进上架说明的建议而不是必做项。中心仓库的 `fnpack.json` 只放作者自己的应用（fntermx/flatcms/flatnas/picoclaw），第三方不进中心源，而是进 `valid_sources.txt`。
- **前提（R15，verifier 复核）**：代码搜索索引的是**默认分支**——`fnpack.json` 现在只存在于**未推送**的合并提交（`GET /repos/ccrabit/workbuddy2api-hub/contents/fnpack.json` → 404、`git ls-tree origin/main` 里没有它、`origin/main` 仍是 `316eb8f`）⇒ 正确口径是「**push 之后**才具备被召回条件」。另外 fork 判负**不是无条件**的：`process_overlap()` 的 `:306-307` 只在配对已判 high-risk（血缘对门槛 `name_rate>=0.50 or sig_rate>=0.30`）时才让 fork 输。
- 相对 URL 是**允许**的（README §8「所有 URL 只能使用 http 或 https，支持绝对 URL 和相对 URL」，相对主 JSON 所在地址解析；`README.md:78` 目录结构不强制）⇒ `icon_url`/`readme_url` 用 `./fndepot/...` 合法。
- 本地可直接复用中心仓库的校验逻辑：`/tmp/fndepot/generate_sources.py` 的 `validate_v2_app()` / `parse_and_fingerprint()` / `is_forbidden_identity()`（只 import，别跑 `main()`）。
- 参考事实副本：`/tmp/fndepot/{README.md,fnpack.json,valid_sources.txt,generate_sources.py,update-sources.yml}`。

### 1.7 设备（只读，禁止改动）

设备 `/vol1/@appcenter/workbuddy2api` 上跑的是 v1.6.17.1 发布件（26 个文件与 Release 资产逐文件 md5 相同），数据目录 `/vol1/@appdata/workbuddy2api/`。Phase F **不动设备**。

---

## 2. 冻结决策

### 2.1 版本与 tag 契约（对应「版本号同步和上游一致」）

1. **包版本（`fnos/manifest` 的 `version`）= 上游最新 release tag 的版本号，严格三段 `X.Y.Z`**（本次 = `1.6.19`）。删掉第四位发布号机制。
2. **我们自己的发布 tag = `fnos-X.Y.Z`**（带 `fnos-` 前缀的 annotated tag，挂在我们合并后的 HEAD 上）。
   理由：① 不落进 `v*`，上游的 `release.yml` 在我们 fork 里永不触发（§1.5）；② 与上游 tag 同名会互相覆盖（本地 `git fetch --tags` 会被 clobber、CI 镜像步骤会 force-update 掉我们的 tag）。
3. **不再把上游 tag 镜像进 origin**（§1.5 第二条）。读上游版本改用 `git ls-remote --tags upstream`（或在 CI 里 `git fetch upstream --tags` 只落到本地临时 ref，不 push）。
4. **只有上游发了新的 release 才发布**：合并后若「上游最新 release 版本」> 「我们最后一次发布版本」，就 tag `fnos-<该版本>` 并构建；相等则只并入、不发版（上游在 release 之后的提交不进我们的版本号）。
5. `scripts/build-fpk.sh`：HEAD 上有 `fnos-X.Y.Z` annotated tag → 版本就是 `X.Y.Z`（第一优先）；没有 tag（本地开发/手动 dispatch）→ 走 `--alpha` 路径（带后缀，不产出可安装版本），fallback 顺序 = 最近的 `fnos-*` tag 版本 → 上游可达的最新 `vX.Y.Z` → `fnos/manifest` 里的版本。
6. `build-fpk.yml`：tag 触发时若 ref 是 `fnos-X.Y.Z`，要求 `--print-version` 等于 `X.Y.Z`（不等则 `::error::` + exit 1），相等才 `export VERSION=…`；`v*` 保留兼容历史 tag。
7. `tests.yml` 的 tag 门禁：接受 `fnos-X.Y.Z`（= 源版本）与历史四段 tag，拒绝其它。
8. 设备升级路径：设备 1.6.17.1 → 新包 1.6.19，按数字比较是升级，可原地升级。
9. FnDepot 源里的版本键与包版本一致（`1.6.19`）。

### 2.2 合并口径

- **上游优先**（m04805 的常设规则）：纯上游代码/文档冲突以 `upstream/main` 为准。
- 我们的飞牛层只做**最小重贴**：网关 socket 免密（`_gateway_trusted()` 按 peer uid 判定）、`window.__WB_BASE__`/`__WB_VIA_GATEWAY__`/`__WB_GATEWAY_USER__` 注入、仅在挂载态注入 `<base href>`、`is_gateway` 才加前缀、看板主题/移动端/使用说明/cockpit 导出/token 单位。
- 上游新增的等价能力（积分获取历史、活动历史、智能体配置、按 Key 归属、增量轮询）**一律保留上游实现**，不与之并行维护两套。
- 冲突解决后必须让 Phase E 的那批断言重新变绿（`tests/_test_gateway.py`、`tests/_test_phase_e_verify.py`、`tests/_test_gateway_ui.js`、`tests/_test_phase_e_ui2.js`、`tests/_test_cockpit_export.py`），否则算没解决。

#### 2.2.1 契约变更：直连不注入上下文（2026-10-10，Lead 裁决）

- 原契约写「`inject_dashboard_context()` 注入 `window.__WB_BASE__`（未挂载为 `""`）」；上游 v1.6.19 新增的 `tests/_test_dashboard_cache_headers.py` 要求普通 TCP `GET /` 的响应体**逐字节等于** `dashboard.html` + 语言替换，两者不可兼得。
- 裁决：**改为缺省（非挂载）直连不注入任何 `window.__WB_*`，也不注入 `<base href>`**；挂载态（`base_path` 非空 / `via_gateway` / 有网关用户）照旧注入。依据：用户本轮规则「上游有的功能和本地版本重复的优先确保上游功能」；且语义不丢——看板 JS 按 `raw == null ? '' : String(raw)` 读全局量，缺省与注入空串等价。
- 连带：`tests/_test_gateway.py` 的直连断言改为负向（不含该两行），`tests/_test_phase_e_verify.py` 由 verifier 在 F5 同步改；ETag 第 4 分量必须覆盖 `base_path|via_gateway|gateway_user`，否则第二个 NAS 用户会拿到 304 + 别人的页面。

### 2.3 自动并入的改法（对应「自动并入并构建似乎没有生效」）

- 保留每日 `17 3 * * *`，**再加两个 cron 槽**（`23 9 * * *`、`41 15 * * *`），降低 GitHub 调度延迟/丢单的影响。
- 冲突时除了（保持现有的）失败 + issue/summary 之外，**再推一个 `sync-conflict/<UTC 日期>` 分支**（含冲突标记的合并结果），这样人来解决时不用重做合并。仍然 abort 主分支、仍然 exit 1。
- 删掉镜像上游 tag 的步骤（§2.1 第 3 条）。
- 自动 tag 改为 `fnos-X.Y.Z`（§2.1 第 4 条），只在版本号前进时打。
- `workflow_dispatch` 手动入口保留。

### 2.4 交付纪律

- 本阶段产出**测试包**（本地构建，不推 origin、不打 tag、不发 Release），交用户人工测试后再提交。
- 上架 FnDepot 的仓库创建/push 需要用户确认（我们的 PAT 是细粒度、无 administration 权限，改 `has_issues` 都是 403；仓库 Issues 也仍需要用户在 Settings → General → Features 里打开）。

---

## 3. 工作包与写域

| WP | 内容 | owner | 写域 | 依赖 |
| --- | --- | --- | --- | --- |
| WP-F1 | 解决 `wb_proxy.py` 两段冲突（上游优先 + 重贴飞牛层） | api-integrator | `wb_proxy.py` | — |
| WP-F2 | 解决 `dashboard.html` 三段冲突（上游新版看板为底 + 重贴我们的主题/移动端/使用说明/cockpit 导出/token 单位） | ui-panel | `dashboard.html` | — |
| WP-F3 | 版本契约落地：`scripts/build-fpk.sh`、`.github/workflows/{build-fpk,sync-upstream,tests}.yml`、`tests/_test_release_pipeline.py`、`docs/`、`fnos/README.md` | packager | `scripts/`、`.github/`、`tests/_test_release_pipeline.py`、`docs/`、`fnos/README.md` | — |
| WP-F4 | FnDepot 上架件：根 `fnpack.json`（V2）、`fndepot/`（图标/预览/README）、校验脚本或测试、上架说明 | credits-engine | `fnpack.json`、`fndepot/**`、`tests/_test_fndepot_source.py` | — |
| WP-F5 | 终验：合并正确性、版本契约红/绿门、FnDepot JSON 用中心仓库校验器验证、全量套件、`verify-fpk.sh` | verifier | `tests/_test_phase_e_verify.py`、`docs/phase-f-verify.md` | F1-F4 |
| WP-F6 | `README.md` 冲突（3 段）并入最终套件数、组装合并提交、跑门、构建 1.6.19 测试包、写交付说明 | Lead | `README.md`、`docs/phase-f-delivery.md`、`docs/phase-f-plan.md` | F1-F4 |

写域纪律（沿用）：一个文件只有一个写者；`wb_proxy.py` 只有 api-integrator 写，`dashboard.html` 只有 ui-panel 写，`README.md` 只有 Lead 写；任何 writer 不许改别人的文件（要改先找 Lead）。

### 3.1 并行执行的物理隔离

每个 writer 用**自己的 git worktree**，互不干扰：

- `/tmp/wb-f1`（api-integrator）：detached，已由 Lead 起好 `git merge --no-commit --no-ff upstream/main`，冲突 2 段都在 `wb_proxy.py`。
- `/tmp/wb-f2`（ui-panel）：同上，冲突 3 段都在 `dashboard.html`。
- `/tmp/wb-f3`（packager）：branch `phase-f/version-policy`，干净树（= 316eb8f，飞牛层文件两边无交集，不会冲突）。
- `/tmp/wb-f4`（credits-engine）：branch `phase-f/fndepot`，干净树。

Lead 在 `/tmp/wb-lead`（branch `phase-f/upstream-1.6.19`）做组装：把 F1 的 `wb_proxy.py`、F2 的 `dashboard.html` 拷进来，自己解决 `README.md`，提交合并，再把 `phase-f/version-policy`、`phase-f/fndepot` 合进来。

---

## 4. 验收标准

1. `git merge-base --is-ancestor upstream/main HEAD` 为真；`git diff --name-only upstream/main HEAD` 只列出我们的飞牛层文件（不含上游源文件被我们单方面改动的项）。
2. `python3 tests/run_all.py --jobs 4` 全绿（套件数按合并后的真实树扫盘，README 里的数字与之一致）。
3. `bash scripts/verify-fpk.sh` 全绿（对 `WorkBuddy2API-Hub_1.6.19_all.fpk`）。
4. `VERSION=1.6.19 bash scripts/build-fpk.sh` 产出 manifest `version = 1.6.19`、`appname = workbuddy2api`、`platform = all`、`service_port = 8788`、`ui/config` 仍是 iframe + `gatewaySocket` 的包；`--print-version` 在有 `fnos-1.6.19` tag 时等于 `1.6.19`。
5. 版本契约有红/绿门：把修复前的脚本放进同一 fixture 必须变红（沿用 `tests/_test_release_pipeline.py` 的做法）。
6. `fnpack.json` 通过中心仓库 `validate_v2_app()`/`parse_and_fingerprint()` 的实现校验；`download_url` 可访问、`size` = 实际字节数、`sha256` 与文件一致。
7. `sync-upstream.yml` 里不再有「推上游 tag 到 origin」的步骤；tag 名形如 `fnos-1.6.19`；冲突路径仍 `exit 1` 且写 issue/summary/推 `sync-conflict/<date>` 分支。
8. 不推 origin、不打 tag、不发 Release、不动设备。

## 5. 明确不做

- 不把 Phase D 的任务中心/模型锁池/暂停选号/积分 FEFO 搬回来（§1.3）。
- 不改上游的 `.github/workflows/release.yml`、`tests.yml` 触发条件（上游文件，改动会在下次合并冲突）。
  **例外（2026-10-10 Lead 裁决 ①）**：`tests.yml` 的 `on.push.tags` 加了 `"fnos-*"`——否则
  「tag 与源码版本一致」这条断言对我们真正的发布 tag 永不运行；详见 `docs/phase-f-version-policy.md` §9。
- 不为了让自动并入「永不出错」而去实现复杂的自动冲突解决；冲突仍然由人决定。
- 不动 `/vol1/@appcenter/workbuddy2api` 与 `/vol1/@appdata/workbuddy2api`。
