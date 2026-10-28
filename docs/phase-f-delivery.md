# Phase F 交付说明：WorkBuddy2API-Hub 1.8.0（飞牛包，看板样式已修）

> **Phase Q 热修（2026-10-27，11128 渠道校验；包版本 `1.8.0.1`）**：上游 10-27 下午起对 Web 凭证加大渠道校验，
> 返回 HTTP 400 `code=11128 Illegal API invocation from an unapproved channel`；实测为**抽样判定**
> （同一会话 `msgs=95` 在 22:28:39 被拒、22:28:40 立刻成功），而旧版 `open_upstream()` 对 400
> 一律原样透传、不换号，于是一次抽样就打死整轮。改动：`wb_proxy.py` 的 400 分支先解析
> `upstream_error_code`，命中 `WAF_TRANSIENT_ERROR_CODES = frozenset((11128,))` 且预算未用完时
> 换号重试（默认 2 次，`WB_WAF_RETRY_ATTEMPTS` 可调，0 = 关），被拒账号**不记账、不冷却**；
> 新增套件 `tests/_test_waf_channel_retry.py`。
>
> **Phase R 热修（2026-10-28，修 Phase Q 自己；包版本 `1.8.0.2`）**：1.8.0.1 装到设备后，08:52 两次
> 真实 11128 仍然原样透传 400，日志里**一条换号记录都没有**（`grep -a "channel check) for\|rotating
> to another account"` 全日志 0 命中）。根因：`upstream_error_code()` 用 `json.loads` 解析
> `http_error_detail(exc)` 的正文，而后者只留 **600 字节**；上游错误信封自带 `displayMsg` +
> `displayTips`（en / zh / zh-hant）再加 `actions` —— 实测同款 `11101` 正文就是 **684 字节**，
> 11128 一样超长。600 字节截断后丢掉收尾的 `"}`，`json.loads` 必然失败 → code = `None` →
> `WAF_TRANSIENT_ERROR_CODES` 永远不命中 → 直接 `raise`。修法：`upstream_error_code()` 在 JSON
> 解析失败时按头部正则 `_UPSTREAM_CODE_RE`（只扫前 512 字符）兜底 —— code 永远是信封第一个字段，
> 403 的 `restriction_is_account_level` 早就这么做了；同一个兜底也让 5xx 的模型级错误、11140 的
> 账号级限制在长正文上不再漏判。套件 5 → **9 项**（真实现场长度的 11128 仍换号、半截 UTF-8/半截
> JSON 仍算 11128、截断正文下预算依旧有界、`upstream_error_code` 的直接断言）。用真实信封形状
> （691 B，取自上游 `11101` 正文、只换 code/msg）复现：**修前** `upstream_calls=1 raised=HTTPError`，
> **修后** `upstream_calls=2`、请求在第二个账号上成功。
>
> **Phase S 热修（2026-10-28，1.8.0.2 装机后仍 400；包版本 `1.8.0.3`）**：1.8.0.2 装到设备后换号日志
> 终于出现了（`09:22:56 upstream 400 (code 11128, channel check) ... rotating to another account (attempt
> 1/2)`、`09:22:57 ... (2/2)`），但**三个账号依次拒绝同一条正文**，客户端拿到的还是 400。反证数据：
> `usage.jsonl` 里 27–28 日 1829 条请求中 `n_msgs>=100` 的请求绝大多数 completed（最高 550 条消息 /
> 521k tokens），所以「体积 / 消息条数」不是触发条件；同时 `open_upstream()` 的 `tried.add(account.uid)`
> 保证换号真的换了不同账号 —— 判定随**内容**走、不随账号走，而 1.8.0.2 的换号在 **1.3 秒**内就把预算
> 打光，判定器连采样点都没换。改三处：① `WAF_RETRY_ATTEMPTS_DEFAULT` **2 → 3**；② 每次换号前按
> `WAF_RETRY_DELAYS = (0.5, 1.5, 3.5)` 等待（`waf_retry_delay()`），不再一秒内连打三次；③ 预算用完
> 仍被拒时，若提示模式是 `passthrough` / `append`（非用户自定义），触发 `PROMPT_DEGRADE` 换成中性系统
> 提示再试一次 —— 这是 403 内容审查早就验证过的兜底，且只试一次。诊断：每次被拒把请求形状
> （`system` 提示头 8 KB + 尾 2 KB、逐条消息长度、正文 sha256、账号/`realm`/`product`/模型/流式）落到
> `/tmp/wb-waf-dumps/`（**不写数据目录**，`WB_WAF_DUMP_DIR` 可覆盖，最多留 24 份），下次现场直接比对，
> 不必再靠猜指纹。套件 9 → **13 项**（换号等待逐次拉长、预算耗尽降级重试、降级只试一次、dump 形状）。
>
> **Phase T 修正（2026-10-28，1.8.0.3 当场抓到的现场；包版本 `1.8.0.4`）**：1.8.0.3 装上去不到十分钟
> 就抓到一次真实 11128 —— `10:33:43 chat ... msgs=83`（并发还有一条 `msgs=2` 的旁路请求）→
> `10:33:44 / 45 / 47` 三次换号（间隔 0.5 / 1.5 / 3.5 秒）**全被拒** → `10:33:51 survived 3 rotation(s)
> -> degraded prompt retry` → **`10:33:56 POST /v1/chat/completions 200`**，`chat done ... 14770ms
> tokens=207568 (in=207259 out=309)`。也就是说 1.8.0.3 的兜底确实把这一轮救了回来（换号 + 中性提示
> 重试 + 退避），用户侧的请求不再以 400 结束。但那次实现有个副作用必须收掉：它触发的是**进程级**
> 降级窗口（照抄 403 内容审查的语义，到次日 00:00 CST 才复位），于是当天其余 passthrough/append
> 请求的系统提示全被换成 28 字的中性提示 —— 对一个靠系统提示干活的编码 agent 来说这是悄无声息的
> 降级。1.8.0.4 把它改成**只借这一条请求**：`PROMPT_DEGRADE.trigger()` → `build_upstream_body()` →
> 立刻 `reset()`（若进这条分支之前窗口本来就是活的，则不动它，保住 403 那条保护），自定义提示模式
> 依旧永不降级。同时把「dump 写不进去」的隐患钉掉：应用以 `workbuddy2api`（uid 946）运行，而
> `/tmp/wb-waf-dumps` 早先是 root 建的 0755 目录 → 应用写不进、异常被吞、真机现场一条 dump 都没有
> （`grep -ac "channel check dump"` = 0）；现在套件自己在临时目录里跑（`P.WAF_DUMP_DIR` 在 setUp 里
> 指到 `mkdtemp`），`/tmp/wb-waf-dumps` 只留真机现场，宿主机上已把它改成 1777 供应用写入。
> 套件仍是 **13 项**（把「降级必须记进进程窗口」改成「只借一条请求：窗口必须复位，且最后一次正文
> 里不能再有客户端的 SYSTEM 哨兵」）。
>
> **已发布（2026-10-28 11:12 CST）**：`refs/heads/main` 已从 `3e99cec`（`fnos-1.8.0`）快进到 Phase T 的**双亲合并提交**
> （`main` 与 tag 同一提交，`git describe --tags` 就在 `fnos-1.8.0.4` 上）；annotated tag `fnos-1.8.0.1` / `.2` / `.3` / `.4` 全部推到
> `origin`，**只有 `.4` 建了 Release**（Release id `426222546`，非草稿，
> <https://github.com/ccrabit/workbuddy2api-hub/releases/tag/fnos-1.8.0.4>），两资产 `uploaded`：
> `WorkBuddy2API-Hub_1.8.0.4_all.fpk`（`1028481` B，sha256 `e61959d7…`）+ `.sha256`（`100` B）；
> `fnpack.json` 里那条 `download_url` 实测 **HTTP 200**，与 `dist/` 同一字节。前三个号故意不发
> Release：`1.8.0.1` 在真机上是死代码、`1.8.0.2` 换号救不回、`1.8.0.3` 的兜底会把当天的系统提示
> 换掉，公开列出来只会让人装错版本 —— 它们的 tag 留着当历史锚点。
> 本机 HTTP 侧推不上去（`/root/.ssh/wb2api_push` 这把临时部署密钥已被 GitHub 吊销，`gh` 也没装），
> 实际走的是 `/root/.gh-token`（93 字符，`push: true`）+ `GIT_ASKPASS` 助手，token 不落 argv、
> 不写进 git config。
>
> **版本口径（Phase Q/R 的有意偏离，用户明确要求）**：用户原话「版本号不更新，应用中心无法安装，
> 为了区别上游版本，这个版本号按照 `1.8.0.1` 这样的方式命名」。所以 1.8.0 的「包版本 ≡ 上游最新
> 三段 tag」政策**本轮显式豁免**：`manifest` 的 `version`、`wb_proxy.py` 的 `server_version` /
> `/overview` 版本串、发布 tag（`fnos-1.8.0.2`）与 `fnpack.json` 的版本键统一为 **`1.8.0.2`**
> （`1.8.0.1` 是同一套第四段热修计数，已被 1.8.0.2 取代）。理由纯粹是机械的：应用中心只按版本号
> 判断升级，同版本新字节装不进去。它**不是** Phase E 那个「上游 1.6.10 + 我们第 N 次发布」的
> ordinal 机制（那个仍然删除，`build-fpk.sh` 里没有 `next_release_ordinal`），只是热修计数；上游
> 下一个 release（`v1.8.1`）回到三段号。`scripts/build-fpk.sh` / `scripts/verify-fpk.sh` 的版本
> 正则因此放宽为「三段 + 可选第四段」（`(\.[0-9]+){2,3}`），`tests/_test_phase_e_verify.py` 里
> 「包版本 = 上游最新 tag」的断言与 `tests/_test_fndepot_source.py` 的 SemVer 断言同步放宽，均登记
> 为本轮的有意偏离。
>
> **本包指纹（本轮实测）**：`dist/WorkBuddy2API-Hub_1.8.0.4_all.fpk` = **`1028481` B** /
> sha256 `e61959d7df9a53703dccfa12e54c74f851f37bf0dbc9b1432141e8ad7fcaa6b0`，包内 `app.tgz`
> 的 md5（即 manifest 的 `checksum`）= `5439b5a1e11228f4de384223df87566f`。上一版 `1.8.0.3`
> 是 `1020748` B / sha256 `406a62ce…` / app.tgz `54431bcc…`（Phase S）。
> `fnpack.json` 已按此回填；**Release 尚未发布**（推送 `ccrabit/FnDepot` 之前必须先上传资产，
> 否则源里的 `download_url` 会 404）。
>
> **装机路线（踩坑记录，1.8.0.2 就是这样装上去的）**：`trim-cli app install-fpk` 对**已安装**的应用
> 永远返回 `{"code":10236}` —— 后端 `install` 分支的守卫是「app already installed」
> （`/var/log/trim_app_center/error.log` 里 `msg="app already installed"`），`trim-cli app update`
> 又写死必须先走云下载任务（`POST /app-center/v1/download/task` → `10030`），`appcenter-cli
> install-fpk` 只打印一句 `Application [workbuddy2api] is installed.` 就返回 0、不升级。**可用路线**
> 是 app-center 自己的本地 RPC：① `trim-cli app install-fpk <fpk> --yes --dry-run` 把包上传并解包到
> `/vol1/appcenter-downloads/<app>-<ver>-tpk`（`--dry-run` 不触发安装）；②
> `curl --unix-socket /var/run/com.trim.app.center.sock -X POST -H 'Content-Type: application/json'
> -d '{"appName":"workbuddy2api","updateVersion":"<ver>","packageType":"local"}'
> http://unix/rpc/v1/update/task` 返回 `taskId`；③ `appcenter-cli list` / `trim-cli app status`
> 轮询到新版本 `running`。该 socket 无鉴权（web sock `/var/run/com.trim.app.center.web.sock` 才 401
> 鉴权）；我方只走应用中心的升级接口，没有手工 `cmd/main start|stop`。

> 本轮：并入上游 `upstream/main` = `4f7ae6f`（`release: v1.8.0`，tag 就是上游 `main` 的头），
> 合并基 `47775c5`（v1.7.33）→ **5 个提交、16 个文件、+823 −60**，全部是修 bug；合并提交
> `62af384`。随后用户在 1.7.33 上反馈「数据看板显示不全」，定位到**本仓库自 1.7.30 起带进来的
> 样式缺陷**并修掉，所以 `1.8.0` 这个包**重打包了一次**（同一版本号、新字节，Phase G 先例）。
> 发布走本地流程：构建 → `verify-fpk.sh` → `run_all` → 上传两资产 → 回填 `fnpack.json` → 推送
> `ccrabit/FnDepot`。**本轮没有动设备**。
>
> **看板缺陷与修法**：上游 v1.7.30 在统计条上新增的 `@media (max-width: 860px)` 与本层同位置的
> 移动端兜底规则合并时少了一个收尾的 `}`，于是它把**后面全部规则**（整个 `#pageAnalytics` 看板
> 设计、`.wb-help` 使用说明）都吞进了「窄屏才生效」的分支——浏览器不报错，只是宽屏下全部失效
> （KPI 卡片一张一行、行高巨大、没有六列栅格）。`fnos-1.7.24` 的样式表是 `670/670` 配平，
> `fnos-1.7.30` 起变成 `722/721`，所以 1.7.30 / 1.7.33 两个包都带着它。修法：补回那个 `}`，
> 让 `#pageAnalytics` / `.wb-help` / `#cockpitRealm` / `#cards` 回到嵌套深度 0；新增
> `tests/_test_dashboard_css.py`（4 项）钉死「括号等量 + 关键字面规则在深度 0 + 深度大于 0 的
> 规则只能待在 `@media`/`@keyframes`/`@supports` 里」——这类缺陷不会让任何断言变红（字符串还在，
> 只是位置错了），必须单独钉一层。
>
> **版本口径**：1.8.0 按「包版本 = 上游最新三段 release tag（`v1.8.0`）」发布，套件里 `PKG_VERSION`
> 也按 `newest_upstream_release()` 解析；Phase Q/R/S/T 热修按用户要求改用第四段 `1.8.0.4`（见顶部
> 「版本口径」段），跑门禁时用 `WB_PKG_VERSION=1.8.0.4` 覆盖该解析值。同一版本号换资产的代价是「已经装过
> 旧 1.8.0 的机器不会自动收到更新」——这正是本轮必须换号的原因：应用中心只按版本号判断升级。
> **已发布（本轮实测）**：tag `fnos-1.8.0` 指向**双亲合并提交**「Merge upstream/main (v1.8.0) into the fnOS fork」（两个父 `dce80d2` + `4f7ae6f`），且 `refs/heads/main` 与它同一个提交（发布态：`git describe --tags` 就在 `fnos-1.8.0` 上）；Release **423127766**（<https://github.com/ccrabit/workbuddy2api-hub/releases/tag/fnos-1.8.0>）非草稿、标题已改为「数据看板已修」，两资产 `uploaded`（`1027104` B / `98` B），从资产端点下载回本地与 `dist/` **逐字节相同**（sha256 `3f98610c…`）。`bash scripts/verify-fpk.sh` = **71 passed / 0 failed**（tag 在 HEAD 上，那条 SKIP 消失）。
> **发布后实测**：`python3 tests/run_all.py --jobs 4` = **237 passed / 0 failed / 0 skipped**（`_test_phase_e_verify.py` PASS=359 FAIL=0）。
> **FnDepot 源已更新**：`ccrabit/FnDepot` 提交 `6922063`「WorkBuddy2API-Hub 1.8.0 应用源（重打包：看板样式修复）」，单键 `1.8.0`、`updated_at 2026-10-25T17:44:35+08:00`；`download_url` 实测 HTTP 200 / `1027104` B / sha256 一致；`tests/_test_fndepot_source.py` = PASS=77 FAIL=0 SKIP=0 NOTES=3（用临时克隆的中心仓库 `generate_sources.py` 当校验器）。
> **两处踩坑记录**：① 发布 tag 必须指向**双亲合并提交**且标题写明并入 `upstream/main`，否则 E13/E16 立刻红——本轮先把 tag 指到修复提交（单亲）被套件拦下，改成「用 `git commit-tree <tree> -p <旧 main> -p <upstream head>` 造一个树与构建态一致的双亲合并」才通过；② 这台机器上 **`/tmp` 在每次 bash 调用之间不保留**，`.stage` 之类的中间态要放到 `/vol2/1000/AgentWork/2api/.stage/`（FnDepot 暂存源与中心仓库校验器都放那里）。
> **设备现状（2026-10-28 10:45 实测，已装 1.8.0.4）**：设备 = 本机，`appcenter-cli list` /
> `trim-cli app status` 都是 `workbuddy2api │ WorkBuddy2API-Hub │ 1.8.0.4 │ running`；
> `/var/apps/workbuddy2api/manifest` 的 `version = 1.8.0.4`、`checksum =
> 5439b5a1e11228f4de384223df87566f`（= 本包 `app.tgz` 的 md5）；`/vol1/@appcenter/workbuddy2api/server/wb_proxy.py`
> 与本仓库工作树 `diff` **IDENTICAL**，banner 为 `wb-proxy/1.8.0.4`、内含 `_UPSTREAM_CODE_RE`、
> `WAF_RETRY_DELAYS` 与一次性 `waf_dump_request`。
> 升级路径：1.8.0（用户自己从 FnDepot 装的）→ 1.8.0.1（Phase Q）→ 1.8.0.2（Phase R）→
> 1.8.0.3（Phase S）→ **1.8.0.4（Phase T，本轮）**，四次都由我方经应用中心的 `update/task` RPC 完成
> （见顶部「装机路线」，没有手工 start/stop）。
> **装机后验收（1.8.0.4 实测）**：`curl /health` → `{"ok": true, "realm": "cn", "accounts": 9,
> "accounts_ready": 7, "api_key_required": true}`；非流式 `deepseek-v4.1-flash` max_tokens 32 →
> **200**，内容「收到」，usage `prompt 41 / completion 2 / total 43`。
> **真机 11128 首次被救回（Phase S 装的 1.8.0.3 现场）**：`10:33:43` 的 `msgs=83` 请求三次换号全拒
> 后，`10:33:51` 中性提示重试 → `10:33:56` **200**、`tokens=207568`。
> 数据目录 `/vol1/@appdata/workbuddy2api/`（accounts/、usage/）在四次升级里都原样保留。
> **tag 与已发布元数据**：tag `fnos-1.8.0` 指向「本轮最终提交」（含样式修复与回填），所以那棵树里的
> `fnpack.json` 与已发布资产一致，`verify-fpk.sh` 的那条 SKIP 不再出现。
> 历史内容（Phase F/G/H/I/J/K/L/M/N/O/P）保留在下方原章节，仅 §1 指纹已按本轮覆盖。

## 1. 包与已发布资产（1.8.0，本轮重打包）

| 项 | 值 |
|---|---|
| 文件 | `dist/WorkBuddy2API-Hub_1.8.0_all.fpk` |
| 大小 | 1027104 B |
| sha256 | `3f98610c77d0375c909be14d15972c9752f98846c5f27aeb8dd1de63580d329f` |
| manifest checksum | `d3739a61a5faa8e4b7651499d83957e5`（= 包内 `app.tgz` 的 md5） |
| 载荷 | **51 个文件 + 15 个目录**；与上一次 1.8.0 打包相比唯一差异是 `server/dashboard.html`（补回 `}`，样式表 `722/722` 配平） |
| 版本 / appname | `1.8.0` / `workbuddy2api`（appname 故意不改） |
| 冲突解决 | 本轮合并只有 `README.md` 一个冲突文件（套件数按合并后的树重算为 **237 = 176 Python + 61 JS**，上游侧那 11 行历史数字继续作废）；`wb_proxy.py` / `wb_accounts.py` / `dashboard.html` 全部自动合并 |
| 打包侧 | 无需改动（本轮没有新顶层模块） |

# 以下为 Phase F/G 历史记录（1.6.19）

> 本轮用户要求（m05838，逐字）：「上游项目更新了，并入最新的更新，同时GitHub自动并入并构建似乎没有生效，检查问题，查看fndepot仓库上架的要求，准备上架仓库，版本号同步和上游一致」
> 交付纪律（**发布前**的当时事实）：只出本地测试包——没 push、没打 tag、没发 Release、设备一个字没动（等你测完再决定）。
> **发布后状态（2026-10-10，你选了「确认，按完整顺序执行」之后）**：已 push `main`、已打并推送 annotated tag **`fnos-1.6.19`**、已由 CI 构建并发 Release（资产见 §1）、`fnpack.json` 已按**资产**指纹回填并推送。
> 设备状态请以 §6 为准：**那一轮设备装的是 1.6.19**，是**你自己**用我在发布前交付的那份本地包装上去的；我方对设备自始至终只做只读核查（没有 install/upgrade/uninstall）。

## 1. 包与已发布资产

> **Phase G 状态（2026-10-10 深夜 → 10-11 凌晨，你选了「以后本地发布 + 上架 FnDepot」之后）**：GitHub 上**所有自建 workflow 已删除**（只剩上游自带、只在 `v*` 触发的 `release.yml`），发布改为本地流程；`fnos-1.6.19` 的 Release 资产已**本地重建并覆盖两次**（同一版本号：第一次含第二次上游合并 + R19/R25/R26，第二次含第三次上游合并），tag 每次重指到当轮最终提交（现指向合并提交 `a88589e`）。详细 runbook 见 `docs/phase-g-local-release.md`，方案见 `docs/phase-g-plan.md`。
>
> **因此：§1 的指纹以本轮为准，§2.2 的第 1 条（同步工作流）在 Phase G 已被删除而作废（保留为历史记录）。**

## 1. 包与已发布资产

| 项 | 值 |
|---|---|
| 文件 | `dist/WorkBuddy2API-Hub_1.6.19_all.fpk` |
| 大小 | 626248 B |
| sha256 | `e65dcb844df7ede523e990c33e3e661e27d6c73e0a9770592d76e006d610505d` |
| manifest checksum | `ff0742cf816e35077f5ce51f54de27f5`（= 包内 `app.tgz` 的 md5） |
| 载荷 | **39 个文件** = `server/` 34 个（25 个 `*.py` + `LICENSE`/`dashboard.html`/`pricing/pricing.json`/`fndepot/ICON.PNG`/`release/portable.txt` + `wrt/openwrt/workbuddy2api/` 4 个）+ `ui/` 3 个 + `config/` 2 个，`.pyc` 与 `__pycache__` **0 命中**；根 `fnpack.json` **不入包**（自指清单，见 `docs/phase-g-local-release.md` §6/§8） |
| 版本 / appname | `1.6.19` / `workbuddy2api`（**appname 故意不改**：数据目录、网关前缀、已装应用的身份都挂在它上面） |
| 显示名 | `WorkBuddy2API-Hub` |
| **已发布 Release 资产（2026-10-11 第二次覆盖重建，含第三次上游合并）** | tag `fnos-1.6.19`（tag object 已重指到 `a88589e`）的 Release（id `408987082`）现在挂的**就是上面这一个字节**：**626248 B**、sha256 `e65dcb844df7ede523e990c33e3e661e27d6c73e0a9770592d76e006d610505d`、app.tgz md5 `ff0742cf816e35077f5ce51f54de27f5`（本地构建 → 本地上传，不再经 CI，所以「本地包 == 资产」逐字节成立；上传后又从 Release URL 下载回来复算，**与本机 `dist/` 逐字节相同**）。 |

**历史指纹（均已被上面的覆盖，留档）**：Phase F 的本机构建 `577330 B` / `71edade7833191f189ade8d1ca1938faa12db9d0cd90ec316c3596a86c11ac98`；Phase F 由 CI 构建并首发的资产 `577842 B` / `3d341706c6fec4f7620ad75bba49fd3347b1b7c32c41d51cd8a4238c52f8a34c`（app.tgz md5 `806ce4e9ac0cda75485d34ed04657230`）。两者与设备的载荷逐文件相同。

**装法**：应用中心 →「手动安装」→ 选这个 fpk。设备当时装的是 1.6.19 ⇒ 当时数字上可以原地升级/覆盖安装，**不需要卸载**（卸载会带走 `/vol1/@appdata/workbuddy2api` 里的账号/用量，除非先把 `wizard/uninstall` 挪开）。**注意**：设备上那份是 Phase F 的旧资产（载荷 40 个文件），与本包的差别**实测只有 7 项**：内容不同的 6 个 = `server/dashboard.html`（最大，两轮上游面板改造）、`server/wb_proxy.py`、`server/wb_accounts.py`、`server/wb_scheduler.py`、`server/wb_tasks.py`、`server/wb_settings.py`；另有 `server/fnpack.json` 只在旧包里（本包不再内嵌，见 `docs/phase-g-local-release.md` §6/§8）。其余 33 个载荷文件逐字节相同。同版本号能否覆盖安装**未在真机验证**（应用中心一般在「待装版本 ≥ 已装版本」时接受，本包与设备同为 1.6.19）；若被拒，就按上面的卸载口径处理。

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
- **第三次并入上游（Phase G，2026-10-11）**：`upstream/main` 已推进到 `6cd1bc0`（在 `5b5b5c1` 之后又 **25 个提交**：#255–#268 一批——账号页可选独立成菜单 + 签到与活跃记录看板、所有数据表支持点表头排序、顶部页签可收起、更新检查设置卡、剩余用量优先调度（默认关）与超限页内轮转暖号回退、剩余用量估算第二/三批、若干 UI 修复与测试）。合并后仍然**只有 `README.md` 与 `dashboard.html` 两处冲突**（`wb_proxy.py`/`wb_accounts.py`/`wb_settings.py` 自动合并，我们的网关/免密/导出代码逐条保住：`_gateway_trusted`、`GATEWAY_HEADER_USER`、`inject_dashboard_context`、`GatewayUnixHTTPServer`、`_apply_base_path`、`--unix-socket`、`disable_nagle_algorithm` 派生 handler、`import wb_export`）。`dashboard.html` 这次是**结构性**冲突：上游把面板改成「每页一个 `main-page`」并在网关页里留了一个 `#accountsSectionsAnchor` 锚点（`insertBeforeAnchor` 在账号页不独立时把账号区块搬回来），我们那版还是把账号区块内联在网关页里 ⇒ 取上游结构、把我们的飞牛层（`#wbHelp` 使用说明、cockpit 导出按钮、精确 token 单位、免密门控）重新贴到新结构里。
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
| `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.19_all.fpk`（Phase G，本包，含第三次合并） | **71 passed / 0 failed**（tag `fnos-1.6.19` 现在就在 HEAD 上，所以那条 `the tag on HEAD names this version` 真跑；构建时 HEAD 还没有 tag，那时是 70/0。R19 的 `.pyc` 与 R22 的自指 `fnpack.json` 都已在 Phase G 修掉，不再有「发布后稳态漂移」那条 69/1） |
| `bash scripts/verify-fpk.sh <已发布资产>`（从 Release URL 下载回来那份） | **71 passed / 0 failed**（本轮与上一轮都实测过；文件名必须保持 `WorkBuddy2API-Hub_1.6.19_all.fpk`，改名会让两条文件名断言变红） |
| `python3 tests/run_all.py --jobs 4` | 见 §4.1 / §4.3 / §4.5 |
| 包结构 | 39 个载荷文件（`server/` 34 + `ui/` 3 + `config/` 2）、25 个 server `*.py` 全部可解析、`__pycache__`/`*.pyc` 零命中、port 8788、`wb_export.py` 在包内 |
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

### 4.4 Phase G（本地发布 + 删掉 CI）之后的门
- `python3 tests/run_all.py --jobs 4` → **122 passed / 0 failed / 0 skipped**（53.5s，exit 0）。删除 5 个自建 workflow 曾一度让 29 条断言变红（`118 passed / 4 failed`），已由 F10 的 task-35 改成「钉在保留能力上」，并做了有牙证明（把旧 workflow 恢复进副本 `/tmp/wb-g-teeth`：三个发布套件各恰好 1 条红，无连带）。
- `python3 tests/_test_phase_e_verify.py` → **PASS=349 / FAIL=0 / SKIP=3**（run_all 内 341/0/3）。
- `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.19_all.fpk` → **70 passed / 0 failed**；tag 打回 HEAD 后 71/0。
- `du -sh .` 由 24M 降到 21M（`build/`、`__pycache__/`、`.pytest_cache/`、`suite-logs/` 全部清掉；`dist/` 1.6M 保留）。
- 独立性：F10 的报告 `docs/phase-g-verify.md`，登记项 R27–R30。

### 4.5 第三次上游合并之后（Phase G 收尾，2026-10-11 凌晨）
- 合并提交 `a88589e`（两个父 = `ffebb4b` 与 `upstream/main` `6cd1bc0`），落盘后重建包并**覆盖**同一 tag 的 Release 资产（tag object 重指到 `a88589e`）。
- `python3 tests/run_all.py --jobs 4` → **121 passed / 7 failed / 0 skipped**（51.3s）。读懂这 7 条很重要——**没有一条是本仓库引入的**：
  - 6 条在**纯 upstream/main（`/tmp/up-pristine`，未合并任何本仓库改动）上逐条复现同样的红**：`_test_activity_history.js`（`ReferenceError: loadActivityToday is not defined`）、`_test_page_nav.js`、`_test_settings_load.js`（`TypeError: Cannot read properties of undefined (reading 'checked')`）、`_test_settings_update_ui.js`、`_test_model_cooldowns.js`（断言失败）、`_test_run_all_encoding.py`（它拿 `_test_settings_load.js` 当「已知必绿」的夹具，于是被上面那条带红——3 条断言全红，纯上游树上一模一样）。即**上游这一版自己就带着 6 个红套件**（它们的 CI 触发条件也已被我们删掉，不再有 CI 帮我们确认这件事）。
  - 1 条是我们自己的静态验收套件 `tests/_test_phase_e_verify.py`：它按设计把「已发布资产 == 树」「HEAD 上的 tag」「设备 / 包一致性」钉成断言，每次合并+重发布后都需要按新契约更新一轮（F5/F9/F10 都是这么做的；已派 task-34 给 verifier）。
- 本轮 Lead 侧的独立复核（不依赖 ui-panel 自述）：全仓 `<<<<<<<`/`>>>>>>>` 零命中；`#wbHelp` 确实在 `#pageGateway`（2787 < 2921 < 2940）内；cockpit 的 `#btnExportCockpit`/`#cockpitRealm` 各 1 份且都在 `#pageAccounts`（2942–3048）工具栏里；`colspan="7"` 0 命中、`colspan="6"` 3 命中；`fmtTok`/`fmtTokRemaining`/`fmtPerM`/`creditPerM`/`wbUrl`/`__WB_BASE__`/`__WB_VIA_GATEWAY__`/`panelGate`/`gatewayGateOff` 全在；三段内联脚本 `node --check` 全过；`wb_proxy.py` 的飞牛标记全在（`_gateway_trusted` 6 处、`GATEWAY_HEADER_USER` 3、`inject_dashboard_context` 2、`GatewayUnixHTTPServer` 4、`_apply_base_path` 2、`--unix-socket` 2、`disable_nagle_algorithm` 3、`import wb_export` 6）；`python3 -m compileall wb_*.py` rc=0 且 10 个模块逐个 import ok。
- 套件总数 **128 = 94 个 Python + 34 个 JS**（`README.md` 的套件数行按树实算）。

## 5. 真机状态（只读核查，我方未改设备）
- `/var/apps/workbuddy2api/manifest`：`version = 1.6.19`、`display_name = WorkBuddy2API-Hub`、`distributor = ccrabit`、`checksum = be761a0f2715cd903edcf8e88d4198f9`。
- **这个 checksum 就是「你自装的那份本地包」**（重建前的 601800 B 版，留证 `/tmp/wb-r19-old-dist-1.6.19.fpk`）——也就是我在发布前 `present` 给你的那份。时间线一致：`server/**` mtime 20:18、服务进程 20:19 起。⇒ **设备升级是你做的，我方只做只读核查**。
- 所以设备载荷 = 已发布资产载荷（40 个文件，逐字节相同）**+ 3 个额外的 `server/release/__pycache__/*.cpython-311.pyc`**（R19 的痕迹，对运行无影响；§6 已根治）。
- 真机端到端（socket 上**不带** `X-Trim-Username`）：`/panel/status` → `{authenticated: true, via_gateway: true, panel_password_required: true, direct_port: 8788}`；`GET /app/workbuddy2api/` → 200，且带 `<base href="/app/workbuddy2api/">`、`window.__WB_BASE__="/app/workbuddy2api"`、`window.__WB_VIA_GATEWAY__=true`；banner 版本 `1.6.19`。⇒ **免密口径与挂载前缀契约在真机实装件上成立**（只剩「应用中心点击打开 / 安装过程 UI」没验）。
- 另记：设备面板仍是默认密码（`panel_password_is_default: true`），建议改掉。
- **Phase G 复核（只读，2026-10-11）**：设备仍未被动过；设备上的 `server/**` 与 Phase F 那版**已发布资产**（`/tmp/rel-old.fpk`，40 个载荷文件）逐字节相同，本包相对它只改了第二次上游合并涉及的那 6 个文件、且不再内嵌 `fnpack.json`。设备 manifest 的 `checksum` 与那一版资产的 `app.tgz` md5 不同（`be761a0f…` vs `806ce4e9…`），因为设备是从我们在发布前 `present` 给用户的那次本地构建装的——**换行/mtime 会让同一棵树两次构建的外壳字节不同（R22），所以「设备 = 哪个包」只能按载荷逐文件比对**。

## 6. 残余登记（都不影响这一版可用性）
| 编号 | 是什么 | 状态 |
|---|---|---|
| R19 | 本地构建比 CI 多 3 个 `release/__pycache__/*.pyc`（`--exclude='./__pycache__'` 只排仓根） | **已修**：`scripts/build-fpk.sh` 加 `--exclude='__pycache__'` / `--exclude='*.pyc'`，并加两条「红→绿」回归用例（修前必红：`[] != ['server/release/loose.pyc', …]`） |
| R20 | 验收套件在 CI 上从未绿过：写死历史 SHA + 写死「HEAD 上的 tag」 | **已修**（F9 重写，三环境 FAIL=0） |
| R21 | 排除式与 `.gitignore` 漂移（`logs/`、`suite-logs/`、`python/`、`.sdk-cache/`、`wrt/ipk/`、`wrt/apk/`、`.pytest_cache/`、`*.zip`、`*.pyo`…）；根治方向 = 暂存源改用 `git ls-files` | 本阶段**不修**（当前无实际污染），登记在 `docs/phase-f-version-policy.md` §10 |
| R22 | 同一提交两次构建的 `app.tgz` md5 不同（tar 成员目录 mtime + gzip 外壳）⇒ 只能比**载荷内容**或**已发布资产 sha256**；方向 `--mtime=@<提交时间> --sort=name --owner=0 --group=0 --numeric-owner` + `gzip -n` | 本阶段**不修**，登记在 `docs/phase-f-version-policy.md` §10 |
| R23 | 本文档原先把设备版本写成 1.6.17.1，与设备实况（1.6.19，你自装）不符 | **已修**（§1 / §5） |
| R24 | 被 `run_all.py` 拉起的验收套件自己又嵌套跑一整轮 run_all（Linux 只占一半额度，Windows 会撞 300s 上限） | **已修**（`WB_RUN_ALL=1` 时改为跑 harness 冒烟 `_test_lifecycle.py`；被拉起 26.8s → 独立运行行为一字未变） |
| R25 | 套件用**文本模式**读 `dashboard.html` 再逐字节比对响应，Windows 检出的 CRLF 被通用换行吃掉 ⇒ CI 上 `473324 != 463136` | **已修**（改二进制读后解码；CRLF 检出上修前 32/1 → 修后 33/0，已用 `git -c core.autocrlf=true clone` 双向坐实） |
| R26 | 同上 R24 的动机更正（CI 停用后「Windows 超时」不再是动机，但去重本身成立） | 已随 F10 报告登记 |
| R27 | `dist/` 里那份是「新树的候选包」，不等于任何一次已发布资产 | **已修**（Phase G 把候选包本身变成发布件：本地构建 → 本地上传，同一字节） |
| R28 | 交付说明 §1 的本机构建指纹被新一轮重建取代 | **已修**（本表已回填最终指纹 626248 / `e65dcb84…` / `ff0742cf…`） |
| R29 | 设备锚点原来取 `dist/` 里那一版（已不是发布件） | **已修**（设备锚点改取发布件副本 `/tmp/wb-published`；Phase G 后改取实时下载的资产） |
| R30 | Phase G 的删除尚未进 HEAD，e16 的状态感知 | **已修**（e16 已按状态判断；Phase G 提交后为终态） |
| R31 | 第三次合并后 `run_all` 有 7 条红，其中 **6 条是上游自带**（`_test_activity_history.js`、`_test_page_nav.js`、`_test_settings_load.js`、`_test_settings_update_ui.js`、`_test_model_cooldowns.js`、`_test_run_all_encoding.py`），第 7 条是本仓库的静态验收套件 | **不是本仓库的回归**（6 条在纯 `upstream/main` 上逐条复现同样的红，见 §4.5；CI 已删，所以上游也不会有人替我们确认这件事）。第 7 条按惯例交 verifier 更新（task-34）。**不去改上游那 6 个套件**：改了下次并入必冲突，也违背「上游优先」口径 |

## 7. 还没做 / 需要你决定

**没做**
- ~~修好后的同步工作流仍未在真实 GitHub 上跑过~~ → **Phase G 已按你的要求把这个工作流连同其余 4 个自建 workflow 一起删除**（`workflow_dispatch` 也从来跑不了：PAT 没有 Actions 写权限，实测 403）。以后发版是**本地流程**（`scripts/build-fpk.sh` + `scripts/gh-release.py`，runbook `docs/phase-g-local-release.md`），没有 CI 可等。
- FnDepot：**专门的源仓库已经建好并推上去了**——`ccrabit/FnDepot`（非 fork、公开，2026-10-10T16:54:17Z 创建，commit `a8dcecf`），根目录 `fnpack.json` + `ICON.PNG` + `README.md`；线上那份过中心仓库校验器 `validate_v2_app` → `(True,'ok')`，`download_url`/`sha256`(`e65dcb84…`)/`size`(626248) 与 Release 资产一致。飞牛客户端现在就能把 `https://github.com/ccrabit/FnDepot` 当外部源添加试用。**自动收录还没发生**：中心仓库每天 16:00 UTC 重生成 `valid_sources.txt`，下一次（2026-10-12 00:00 +08 之后）才有机会带上我们，已设提醒复检。附带风险：主仓库（fork）根的 `fnpack.json` 仍在，若它哪天被索引出来与我们同签名撞车导致新仓库被剔除，预案是删掉主仓库根那份（`tests/_test_fndepot_source.py` 有 77 条断言钉着它，删时要同步改测试）。
- 应用中心「点击打开」的安装后 UI 流程、真机移动端自适配，需要你在浏览器里看一眼。
- 终验报告 §5 另列 6 条「做不到」的：真实 GitHub 跑同步、真机装包、FnDepot 实际收录、push/tag/Release 动作本身、网关 socket 上 `/v1` 免 key 的真机影响面、真 Windows 腿（以 CI 为准）。

**发布收尾（Phase F，2026-10-10 你批准「按完整顺序执行」后完成；机制已被 Phase G 取代，留档）**
1. ✅ push `main`：`316eb8f → 26c2bcc`。
2. ✅ 打并推送 annotated tag **`fnos-1.6.19`** → `build-fpk.yml` 跑通、**自动创建 Release**（id `408987082`）并挂上 CI 构建的包。
3. ✅ 从 Release 读回**资产**的 sha256 与字节数（注意：CI 构建的包与本机 `dist/` 那份**载荷逐文件相同、gzip 字节不同**，所以 `fnpack.json` 填的是资产的值）。
4. ✅ 回填 `fnpack.json` 的 `sha256`/`size` 并单独提交推送（`3d54173`，不需要新 tag）。

**Phase G 发布收尾（2026-10-11，本地流程）**
1. ✅ 提交 Phase G 全部改动（删 5 个 workflow、`scripts/gh-release.py`、runbook、`fnpack.json` 不入包、验收套件对齐）。
2. ✅ `git tag -f -a fnos-1.6.19` 重指到该提交，push `main` 与 tag（tag 决定 `--print-version`，也决定设备看到的应用版本）。
3. ✅ `python3 scripts/gh-release.py release-upload` 覆盖上传本机构建的 `626248 B` 包 + `.sha256`（clobber）——**资产就是本机 `dist/` 这一个字节**，不再有「CI 包 vs 本机包」两套。
4. ✅ Release 正文换成 Phase G 说明（`docs/phase-g-release-body.example.md` 打底，附最终指纹）。
5. ✅ 按**资产**指纹回填根 `fnpack.json` 的 `sha256 = e65dcb844df7ede523e990c33e3e661e27d6c73e0a9770592d76e006d610505d` / `size = 626248` / `updated_at`，单独提交推送。
6. ⏳ FnDepot 中心仓库每天 16:00 UTC 重生成 `valid_sources.txt` —— 等它收录（配合新建的 `ccrabit/FnDepot` 源仓库）。

**需要你决定 / 动手**
1. GitHub 仓库 **Issues 开关**：同步冲突时「开 issue」依赖它（我的 PAT 没有 administration 权限，要你到 Settings → General → Features 勾上）。
2. ~~是否要为 FnDepot 另建一个非 fork、名字含 `fndepot` 的仓库？~~ → **你已拍板：建**（Phase G）。理由：中心仓库的召回有一支只保留名字含 `fndepot` 的仓库，而本仓库是上游 fork 且名字不含它，`valid_sources.txt` 里 62 条有 61 条名字含 `fndepot`；新建后由它承载 `fnpack.json`（FPK 仍用绝对 URL 指向本仓库的 Release 资产）。**需要一个能建仓的 classic token**（细粒度 token 建仓实测 403，见 §7 第 5 条）。
3. 建议轮换/删除 `/root/.gh-token`（它在本会话里出现过）。
4. 设备面板还是默认密码，建议改掉。
5. **`/root/.gh-token-classic` 还不存在**：你在 m07049 只发了 `chmod 600 /root/.gh-token-classic` 这一行命令，但那个文件还没建（`ls` 报 No such file or directory）。请把 classic token 写进去再回话：
   `printf '%s' 'ghp_你的token' > /root/.gh-token-classic && chmod 600 /root/.gh-token-classic`（`wc -c` 应约 40，不要有多余换行）。我会先只读验证再建 `ccrabit/FnDepot`。
