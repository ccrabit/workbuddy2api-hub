# Phase E — 上游 v1.6.17 整合与飞牛分支重建（权威规格）

用户请求（m04805 逐字）：「/ponytail 拉取上游最新版本，整合进来，记得读取1.6.11-1.6.17版本更新记录，
上游有的功能和本地版本重复的优先确保上游功能；记得我们的版本是飞牛专用，安装包的名字正式和上游同步
改为 WorkBuddy2API-Hub，还是采用飞牛原生安装包及统一网关（注意近期使用发现，在飞牛网页中打开，时间
长了会要求验证密码，这个没有必要可以去除）」

本文件是 Phase E 的唯一权威规格。工作分支 `phase-e/upstream-sync`（合并提交 `9dff35f`）。
Phase D 的未提交成果全部保留在分支 `phase-d/snapshot`（`490eea5`），本阶段不动它。

## 1. 已冻结的事实与决策

| 项 | 决定 | 理由 |
|---|---|---|
| 重复功能 | **上游优先**，本地实现让位 | 用户 m04805 明确要求 |
| 合并结果 | `9dff35f`：`README.md`/`dashboard.html`/`tests/run_all.py` 取上游；`wb_proxy.py` = 上游 + 飞牛网关层（已 `git apply -3` 补回，含 `credit` 累加进上游的 `bump_models`） | 上游 6 个新提交都在这些文件里 |
| 飞牛网关层 | 已在 `wb_proxy.py:7023-7748` 完整存活（`GATEWAY_HEADER_USER`、`unix_peer_uid`、`dashboard_context_script`、`inject_dashboard_context`、`GatewayUnixHTTPServer`、`_apply_base_path`、`_gateway_user`、`_panel_ok`） | 唯一回归：`wb_proxy.py:9941 _apply_cli_overrides` 直接读 `args.base_path`，上游套件 `_test_anthropic_http.py` 的 `Args()` 桩没有该属性 → `AttributeError` |
| 客户端挂载契约 | 服务端注入 `window.__WB_BASE__`（如 `"/app/workbuddy2api"` 或 `""`）、`window.__WB_VIA_GATEWAY__`（bool）、`window.__WB_GATEWAY_USER__`（string），挂载时才注 `<base href>` | `dashboard_context_script()`（`wb_proxy.py:7063-7078`）已定型，客户端必须按它工作 |
| 免密入口 | 网关 socket 连接**只要 peer 校验通过（uid 0 = 网关，或应用自身 uid）即视为已登录**，不再要求 `X-Trim-Username`；该头只用于显示用户名。直连端口仍然要面板密码 | 真机探针证实：会话老化后 fnOS 不再注入该头，`/panel/status` 返回 200 + `authenticated:false`，于是面板回落到自己的密码（日志里看不到 401，只看到 `POST /panel/login`） |
| 包名 / 应用名 | **fpk 文件名与显示名 = `WorkBuddy2API-Hub`**；`manifest` 的 `appname` 标识符**保持 `workbuddy2api`** | 改名标识符会让 `/var/apps/<app>`、`/vol1/@appdata/<app>`、`gatewayPrefix` 全部另起，用户的账号/用量/设置不会自动跟着走（上次卸载已经清过一次数据）。文件名与界面显示名才是用户看得见的「名字」 |
| 版本 | `1.6.17.1`（`bash scripts/build-fpk.sh --print-version` 实测），4 段号 = 基线是上游最新 tag `v1.6.17` + 本分支第 1 个构建 | 沿用既有 derive_version 规则 |
| 交付方式 | 出测试包交用户人工测试；**不提交、不打 tag、不动设备**，等用户回话 | 沿用 m02207/m03476 以来的立场 |

## 2. 合并后测试基线（`python3 tests/run_all.py --jobs 4`）

**77 passed, 5 failed, 0 skipped**（12.9s，当时 82 个套件 = 64 py + 18 js；当前树 83 = 65 py + 18 js）。五条失败已全部定性：

| 套件 | 归属 | 断言 | 性质与处置 |
|---|---|---|---|
| `_test_anthropic_http.py` | 上游 | `AttributeError: 'Args' object has no attribute 'base_path'`（`wb_proxy.py:9941`） | **我们的真实回归** → 服务端修（`getattr`） |
| `_test_release_engineering.py` | 上游 | `'82 个套件：64 个 Python + 18 个 JS' not found in README` | README 数字要跟上（我们多了 5 个套件）→ 文档侧修 |
| `_test_matrix_filters.js` | 上游文件、**我们改过** | 3 条断言查 token tooltip（`titleTok`），上游看板没有该 tooltip | 我们 Phase C 的 token 单位切换断言在上游看板下失效 → 按上游行为收敛（若本阶段补回单位切换，再按新实现重写） |
| `_test_json_account_import.py` | 我们 | `'intl' != 'cn'`；`'cockpit' != 'import'`；`'doc.accessToken' unexpectedly found in dashboard.html` | 上游导入路径与看板已改（上游自己就用 `cockpit` 这个格式名）→ 按上游行为重写我们这套 |
| `_test_gateway_ui.js` | 我们 | `ReferenceError: wbUrl is not defined` | 上游看板没有 `wbUrl()`。**这套是挂载支持的规格**：上游看板的集中请求口是 `dashboard.html:3530`（GET）与 `:3536`（POST），外加 3 处绝对路径（`/panel/login`、`/panel/status`、`/accounts/export`）→ 按上游结构重做前缀支持，再把测试改到新实现 |

## 3. 上游看板缺失的本地能力（要补回的清单，均已核实）

上游 `dashboard.html`（397800B，与 `upstream/main` 逐字节一致）中：

- 「使用说明」/ API 地址 / 应急地址：**0 命中** → 补一小节。
- 「每 M tokens 对应积分」：**0 命中** → 补一列（服务端 `bump_models` 已带 `credit`，见 `wb_proxy.py:2022-2040`）。
- `safe-area` / `-webkit-text-size-adjust`：**0 命中** → 补移动端兜底 CSS（上游有 `viewport-fit`）。
- token 单位切换：只有一处 `k >= 1000 ? (k / 1000) + 'M' : k + 'K'`（`dashboard.html:2931`）→ 按需在数据看板/模型明细补统一格式化。
- 有 `导出账号`（`/accounts/export`，`dashboard.html:1820`/`:4029-4064`）→ 我们**不需要**再写导出。

## 4. 工作包

| WP | owner | 写域（唯一写者） | 交付 |
|---|---|---|---|
| WP-E1 服务端与网关 | api-integrator | `wb_proxy.py`、`tests/_test_gateway.py`、`tests/_test_platform_import.py`、`tests/_test_json_account_import.py` | `_apply_cli_overrides` 回归修好；免密口径落地（peer 即登录）；`/panel/status` 语义不变；我们那 3 套测试按新口径收敛并通过 |
| WP-E2 看板 | ui-panel | `dashboard.html`、`tests/_test_gateway_ui.js`、`tests/_test_matrix_filters.js`、`tests/_test_model_credit.py` | 挂载前缀支持（集中请求口 + 3 处绝对路径）；网关下不渲染密码框；使用说明（API/应急地址）；每 M tokens 积分列；移动端兜底 CSS；日志窗口浅色配色与深色 hover 按上游主题核对（真坏了才改） |
| WP-E3 打包与文档 | packager | `fnos/**`、`scripts/**`、`.github/**`、`README.md`、`fnos/README.md`、`docs/phase-e-delivery.md` | 显示名/文件名改 `WorkBuddy2API-Hub`；payload 带齐上游新模块与 `pricing/`；`--exclude='./docs'`；verify-fpk 通过；README 套件数与接口表更新；CI 的 `build-fpk.yml`/`sync-upstream.yml` 适配新树 |
| WP-E4 验收 | verifier | `tests/_test_phase_e_verify.py`、`docs/phase-e-verify.md` | 82 套件全绿、真的 unix socket 免密 E2E、挂载前缀 E2E、fpk 逐字节一致性、对抗性证伪 |

依赖：WP-E4 阻塞于 WP-E1/E2/E3。E1 与 E2 可并行（写域不重叠）。E3 的打包必须等 E1/E2 停笔。

第二波（等第一波停笔后再开，避免同文件双写）：

| WP | owner | 写域 | 交付 |
|---|---|---|---|
| WP-E5 cockpit 兼容导出（服务端） | api-integrator | `wb_export.py`、`wb_proxy.py` 导出路由段、`tests/_test_cockpit_export.py` | `POST /accounts/export` + `format`（`native`/`cockpit`，缺 `format` → 400），`GET /accounts/export` 行为不变 |
| WP-E6 cockpit 兼容导出（看板入口） | ui-panel | `dashboard.html`、`tests/_test_phase_e_ui2.js` | 账号工具条加「导出 (cockpit 兼容)」；使用说明一句话区分两种格式 |

理由：上游只做了 **导入** cockpit 格式（`wb_accounts.py:2902-2914`，裸数组 snake_case OAuth 行 → `"source":"cockpit"`），**导出** cockpit 格式是我们独有的增量，按用户「重复的以上游为准、不重复的保留」应当保留。Phase D 的实现可 `git show phase-d/snapshot:wb_export.py` 取回。

## 5. 明确不做（本阶段）

- Phase D 的超集功能（任务中心队列、桌面事件链、模型锁池、暂停选号、积分构成 FEFO 明细、
  模型锁池视图）：全部留在 `phase-d/snapshot`，上游已有对应能力（PR #109 / #159 / #174 / 软限流与熔断）。
  **例外：cockpit 格式导出是 WP-E5/E6，本阶段做**——上游只做导入、没做导出，按 m04805「重复的以上游为准」
  它不是重复功能，而 Phase D 用户明确要过（m04346），所以归到第二波补回，不随看板一起丢弃。
  用户若要，下一阶段再谈怎么在**上游看板**上嫁接，而不是继续维护我们那 5967 行看板。
- 思考档位丢选项（m03827）：上游 #117/#177 已修，合并后按上游结果复核即可。
- `Math.max(days, 1)`「不足一天算一天」与 D7（`Account.save()` 只按 uid 命名）两个遗留：本阶段不修。

## 6. 验收标准

1. `python3 tests/run_all.py --jobs 4` → **85 passed / 0 failed / 0 skipped**（收口时扫盘：85 个套件 = 66 py + 19 js，含 WP-E4 的 `_test_phase_e_verify.py`、WP-E5 的 `_test_cockpit_export.py`、WP-E6 的 `_test_phase_e_ui2.js`）；`bash scripts/verify-fpk.sh <最终包>` → **71 passed / 0 failed**。
2. 真机等价 E2E：AF_UNIX 连应用 socket，**不带 `X-Trim-Username`** 请求 `/panel/status` →
   `authenticated: true`、`via_gateway: true`；伪造/直连端口仍然要求面板密码。
3. 挂载态：`GET /app/<appname>/`（走 socket + base path）返回的 HTML 含 `<base href>` 与
   `window.__WB_BASE__="/app/<appname>"`；看板所有 API 调用都带该前缀。
4. `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk` 全绿，包内 `server/**` 与仓库逐字节一致，
   且包含上游新模块（`wb_pricing.py`、`wb_atrest.py`、`wb_modelsdev.py`、`wb_prompt.py`、`wb_ipintel.py`、
   `wb_probes.py`、`wb_catalog.py`、`wb_fingerprint.py`、`wb_identity.py`、`wb_webagent.py`、`wb_webtools.py`、
   `pricing/`）。
5. 交付物：`dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk` + `docs/phase-e-delivery.md`，**未提交、未打 tag、设备未动**。
