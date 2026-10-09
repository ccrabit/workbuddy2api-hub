# Phase E 独立验证报告（WP-E4 / task-14）

> 验证者：`verifier`（独立于任何写者）。分支 `phase-e/upstream-sync`，HEAD `9dff35f`（合并上游 v1.6.17 及其后 6 个提交）。
> 立场：不接受写者的口头结论，只认本机实跑输出；伪造输入、边界值、坏 payload、陌生 uid、未登录、未知 realm 一律打。
> 写域：`tests/_test_phase_e_verify.py`（验证套件）、`docs/phase-e-verify.md`（本文）。**本阶段未 `git commit`、未打 tag、未碰设备、未改任何写者文件。**
> 状态：**收口版 + CI 兼容修订**。数字来自最终包（`dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk`，412737 字节，sha256 `5edc6c97…`）上的独立复跑；本轮另把套件改造成可在 windows-latest（没有 `socket.AF_UNIX`）上跑，并新增 `e10` 平台预演段自证这一点。

## 0. 结论摘要

**合计：PASS=208 / FAIL=0 / SKIP=3；其中 E1..E8 为验收口径（PASS=168），E9 为第二波 WP-E5 的独立交叉验证（PASS=35），E10 为平台兼容预演（PASS=6，均是对套件自身可移植性的断言、不计入 E1..E8）。另：`run_all.py --jobs 4` = 85 passed / 0 failed / 0 skipped（58.1s，退出码 0），`verify-fpk.sh` = 71 passed / 0 failed。未验证项 9 条见 §4，有意口径差异 4 条见 §5，提交前置风险 1 条见 §3 R6。**

| # | 验收项 | 判定 | 通过 / 不通过 / 跳过 | 证据（命令见 §1 / 详见 §2） |
|---|---|---|---|---|
| E1 | 全量套件 `run_all.py --jobs 4` | **通过** | 85 / 0 / 0（本段自身 10 / 0 / 0） | §2.1 |
| E2 | 网关免密 E2E + TCP 伪造仍被拒 | **通过** | 14 / 0 / 0 | §2.2 |
| E2b | peer uid 矩阵（root 放行 / 陌生 uid 拒绝） | **通过（1 项跳过）** | 4 / 0 / 1 | §2.3 |
| E3 | 挂载前缀契约（`<base href>` / `__WB_BASE__` / 直连不注 / 所有调用带前缀） | **通过** | 32 / 0 / 0 | §2.4 |
| E4 | 每 M tokens 积分（后端 credit 累加 + 界面除零保护） | **通过** | 26 / 0 / 0 | §2.5 |
| E5 | 最终 fpk 一致性（命名 / payload / 逐字节 / verify-fpk） | **通过** | 55 / 0 / 0 | §2.6 |
| E6 | 真机设备探针（只读；设备已装 1.6.17.1） | **通过** | 3 / 0 / 0 | §2.7 |
| E7 | 免密防线加固面（socket 权限 / peer 不可读取向 / key 边界） | **通过（1 项登记）** | 10 / 0 / 0 | §2.8 |
| E8 | 交付纪律（跨提交状态成立 + 设备上跑的就是交付版） | **通过（2 项条件跳过）** | 13 / 0 / 2 | §2.9 |
| E9 | cockpit 兼容导出（独立段，交叉验证 WP-E5） | **通过（不计入 E1..E8 口径）** | 35 / 0 / 0 | §2.10 |
| E10 | 平台预演：删掉 `socket.AF_UNIX` 后整套仍绿 | **通过（不计入 E1..E8 口径）** | 6 / 0 / 0 | §2.11 |
| — | **合计（E1..E10）** | **通过** | **208 / 0 / 3** | — |

E8 的 2 项跳过都只在「提交前」这一侧成立、提交后自动转 PASS（HEAD 上还没有 tag；包内文件相对 HEAD 尚有未提交改动——这正是提交前应有的状态），见 §2.9。E2b 的 1 项跳过是本机无法以陌生 uid 起面板（§4 第 5 条）。

配套（写者的套件，我作为独立方在 E1 里确认其真的跑起来且不是被跳过，未改写者结论）：
`_test_gateway.py`、`_test_gateway_ui.js`、`_test_json_account_import.py`、`_test_model_credit.py`、`_test_platform_import.py`。

## 1. 复现入口

```bash
# 全量套件（E1 就是它；套件自身的 e1 段做同样的事并断言计数自洽）
python3 tests/run_all.py --jobs 4

# 我的验证套件：可整跑，也可按段名子串只跑一段（e1..e10）
python3 -u tests/_test_phase_e_verify.py
python3 -u tests/_test_phase_e_verify.py e2_gateway     # 只跑免密段
python3 -u tests/_test_phase_e_verify.py e5_package     # 只跑包一致性段
python3 -u tests/_test_phase_e_verify.py e9             # 只跑 cockpit 导出段
python3 -u tests/_test_phase_e_verify.py e10            # 只跑平台预演段（内部会再整套跑一遍）

# 换包 / 换看板快照（默认 dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk、仓库 dashboard.html）
WB_PKG=/path/to/other.fpk WB_DASHBOARD_PATH=/tmp/frozen/dashboard.html \
  python3 -u tests/_test_phase_e_verify.py e3_mount e5_package

# 换第三方锚（e9 的 Go 契约源码 / Go 面板真实导出的 cockpit 文件）
WB_GO_IMPORT_GO=/path/to/import.go WB_COCKPIT_SAMPLE=/path/to/xxx.cockpit.json \
  python3 -u tests/_test_phase_e_verify.py e9

# 未落地的验收项按硬失败计（默认记 SKIP）
WB_PHASE_E_STRICT=1 python3 -u tests/_test_phase_e_verify.py
```

套件自己起真进程：临时 TCP 端口 + `--unix-socket <tmp>/app.sock` + `--base-path /app/workbuddy2api` + `--panel-password`，raw socket 收发 HTTP，保证看到的是真实状态码与信封，而不是被 `urllib` 加工过的异常。

**平台可移植性（CI 矩阵含 windows-latest）**：`HAS_UNIX = hasattr(socket, "AF_UNIX")` 决定网关 socket 段；没有 AF_UNIX 时这些段一律 `skip(...)`（计 SKIP、不影响退出码），TCP 侧断言照跑；摘要用 `hashlib`（`sha256_file`/`md5_file`）而不是 `sha256sum`/`md5sum`；临时路径一律来自 `tempfile`。设备（`/vol1/**`）与最终包（`dist/**`，未进版本库）在 CI 上不存在，对应段走 `gate(...)`→SKIP，不会误红。

## 2. 逐项结论

### 2.1 E1 — 全量套件（85 / 0 / 0）

```bash
python3 tests/run_all.py --jobs 4
```

原始尾部：

```
  [PASS] _test_usage_share.js                   PASS=15 FAIL=0                                         0.1s
  [PASS] _test_phase_e_verify.py                PASS=208 FAIL=0 SKIP=3                                55.4s

  slowest: _test_phase_e_verify.py 55.4s, _test_connection_reuse.py 12.6s, _test_pricing_switch.py 3.5s
  85 passed, 0 failed, 0 skipped  (/vol2/1000/AgentWork/2api/workbuddy2api-hub)
  total 58.1s with --jobs 4
```

- 验收口径 **85 passed, 0 failed, 0 skipped**（85 = 66 Python + 19 JS，含本验证套件 `_test_phase_e_verify.py` 与第二波 UI 套件 `_test_phase_e_ui2.js`），与我实读的 `README.md:187`「85 个套件：66 个 Python + 19 个 JS」一致。
- 套件不写死数字：e1 段动态数 `tests/_test_*.{py,js}`，断言 `passed+failed+skipped == 树里的套件数`（自洽），所以新增套件不会被漏掉、也不会被旧数字掩盖。
- **这道门不拿「我自己也绿」当前提**（自指死循环：门自己红时 `passed` 永远差 1）。改为断言「失败的套件里除本套件外没有别的」+「本套件在 `run_all` 输出里被记为 `[PASS]` 且不带 `timed out`」+「退出码 0，或本套件是唯一红」；嵌在 `run_all` 里跑时本段自身 `skip`（防递归），此时套件仍被算作 passed。
- 逐套件确认 5 套我方套件真的跑了（`[PASS]` 且非 `[skip]`）：`_test_gateway.py`、`_test_gateway_ui.js`、`_test_json_account_import.py`、`_test_model_credit.py`、`_test_platform_import.py`。
- 本段自身 **10 / 0 / 0**。

### 2.2 E2 — 网关免密口径（14 / 0 / 0）

```bash
python3 -u tests/_test_phase_e_verify.py e2_gateway
```

实测（覆盖 `/tmp/probe_gate.py` 在真机上打的两种形态）：

| 场景 | 实测 |
|---|---|
| socket，**不带** `X-Trim-Username`，`GET <base>/panel/status` | `200` + `authenticated: true` + `via_gateway: true` + `gateway_user: ""` |
| socket，带 `X-Trim-Username: ccrab` | `gateway_user: "ccrab"`（该头只作显示名） |
| socket，无 token，`GET <base>/accounts` | `200`（面板会话已建立） |
| TCP（直连 8788），带伪造 `X-Trim-Username: root` | `authenticated: false`、`via_gateway: false`、`gateway_user: ""`、`/accounts` → `401` |
| TCP，`POST /panel/login` 拿 token 后 | `authenticated: true`，管理路由 `200`（面板密码仍是应急入口） |

结论：免密只发生在 unix socket 且 peer 校验通过时；TCP 侧不可伪造（**无头也已登录这次是被证实的**，不是靠写者描述）。

### 2.3 E2b — peer uid 矩阵（4 / 0 / 1）

```bash
python3 -u tests/_test_phase_e_verify.py e2_peer_matrix
```

socket 是 `0666`（世界可写），所以 **peer 凭据是唯一防线**。用 `setpriv --reuid=N` 起客户端分别连：

| 客户端 uid | 实测 | 服务端日志 |
|---|---|---|
| 0（= 网关） | `authenticated: true`，可读账号数据 | `gateway: peer uid 0, no X-Trim-Username header` |
| 1000（陌生本地用户） | `authenticated: false`，`/accounts` 拿不到数据 | `gateway: peer uid 1000, sign-on ignored: peer is not the gateway` |
| 65534（模拟「应用自身 uid」分支） | **跳过** | 沙箱里父目录是不可遍历的 `d---------`（`/vol2/1000/AgentWork/2api`），`setpriv` 起的面板读不到 `wb_proxy.py`（`Permission denied`），无法在本机复现「自己 uid」这一支；该支由写者的 root-only 套件 `tests/_test_gateway.py::test_a_foreign_uid_on_the_socket_is_not_signed_in` 在真机等价环境覆盖 |

### 2.4 E3 — 挂载前缀契约（32 / 0 / 0）

```bash
python3 -u tests/_test_phase_e_verify.py e3_mount
```

**挂载态（走 socket 请求 `/app/workbuddy2api/`）**：`200`，响应体含真标签 `<base href="/app/workbuddy2api/">`、`window.__WB_BASE__="/app/workbuddy2api"`、`window.__WB_VIA_GATEWAY__=true`；`GET <base>`（无斜杠）也 `200`；前缀被剥掉后业务路由可达（`<base>/health` → `200`）；挂载态 `POST <base>/panel/login` → `200` 且发 token；伪造前缀 `/app/other/panel/status` **不**被当成面板路由。
**直连态（TCP 请求 `/`）**：`200`，**不注** `<base href>`（用真标签正则判定，注释里的字样不算），`window.__WB_BASE__=""`、`window.__WB_VIA_GATEWAY__=false`。
**前缀参数不是写死的**：`--base-path /app/workbuddy2api/`（带尾斜杠）与 `--base-path /app/wb-alt` 都能起服务、注入的 `<base href>` 用归一化后的前缀（无尾斜杠）且请求可达；**socket 上不带前缀直呼 `/panel/status` 也 200**（fnOS 两种转法都不会 500）。

静态 + 运行时双层：

- 没有任何 `fetch('绝对路径')` 裸调用；`fetch()` 调用点（5 处）**全部**把 URL 交给 `wbUrl()`；面板的两个请求汇聚点 `getJSON()` / `postJSON()`（`dashboard.html` 内）体内都是 `fetch(wbUrl(url), …)`，所以其余所有调用点（`/accounts/*`、`/tasks*`、`/scheduler*`、`/accounts/export` 等）天然跟随前缀。
- 没有裸用 `EventSource` / `WebSocket` / `XMLHttpRequest` / `sendBeacon` / `location.assign`。
- 把 `const WB_BASE = (function(){…})();` + `function wbUrl(path)` 抽到 node 里求值：`window.__WB_BASE__='/app/workbuddy2api'` 时站内路径**全部**带前缀、`https://…` 与外域协议相对路径原样不动；`window.__WB_BASE__=''` 时原样返回。
- 第二波新增的 cockpit 导出按钮（`#btnExportCockpit` → `exportAccountsCockpit()` → `downloadExport(…, {format:'cockpit', realm})`）同样走 `wbUrl()` 汇聚点，无新增绝对路径调用。

### 2.5 E4 — 每 M tokens 积分（26 / 0 / 0）

```bash
python3 -u tests/_test_phase_e_verify.py e4_credit
```

后端（in-process 打桩 `wb_proxy.USAGE_LOG` + 真实 HTTP `GET /usage/analytics`）：

- 逐模型统计带 `credit`：`glm-5.3` → `all_time.credit == 84`、`window.credit == 84`、`total_tokens == 4,000,000`、`requests == 3`。
- 失败行口径：`kimi-k3` `errors == 2` / `requests == 0` / `credit == 8`，且「上游已计费」的失败行 tokens 仍保留（10+20）——这是上游刻意的口径（`feed()` 注释：token 总量跟真实消耗走，只有请求/错误计数看结果），**不是缺陷**。
- `outcome:"client_aborted"` 的行整行跳过（tokens/credit 都不计）。
- 总计 credit `84 + 8 = 92`，窗口总计同样 92。
- `GET /usage/analytics` → `200`，响应里没有 `NaN` / `Infinity` / `-Infinity` 字面量，是合法 JSON，模型行带 `credit`。

界面（`dashboard.html` 的 `creditPerM` / `fmtPerM` 抽到 node 里求值，12 组边界输入：`0` / `None` / `"abc"` / `-5` / `1e9` / 0 积分 / 字符串数字 / `1e12` / `1` / `3` …）：

- 任何组合都**不**外泄 `NaN` / `Infinity` / `undefined`；tokens 为 0 或非法 → 显示 `—`（没有比值，不是 0）；credit 为真实 0 → 显示 `0` 而不是 `—`；`42 积分 / 2M tokens` → `21`。
- 表头存在「每 M tokens 积分」列，渲染点都走 `fmtPerM()`（不各自手算），且不是裸 `credit/tokens`。

### 2.6 E5 — 最终 fpk 一致性（55 / 0 / 0）

```bash
python3 -u tests/_test_phase_e_verify.py e5_package
bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk
```

最终包指纹（我独立复算，与 packager/Lead 通报逐字符一致）：

| 项 | 值 |
|---|---|
| 文件 | `dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk` |
| 字节数 | `412737` |
| sha256（fpk 自身） | `5edc6c972e206181b4efeb49fd1c804a5ccb232b6c63a0ce5ed76498d64bbc27` |
| md5（fpk 自身） | `d45e598420425a9f992895445f3ef1ff` |
| manifest `checksum`（app.tgz 的 md5） | `7d66e48d4d7738192c0cf7499eb06666`（= 我解包后 `md5sum app.tgz` 的实算值） |
| manifest | `appname = workbuddy2api`、`version = 1.6.17.1`、`platform = all`、`service_port = 8788`、`display_name = WorkBuddy2API-Hub` |
| 旁置 `.sha256` | 与产物一致 |

- `appname` **没有**跟着改名（改了等于换应用、用户账号/用量会读不到），显示名才是 `WorkBuddy2API-Hub`。
- payload（`app.tgz` 里的 `server/**`）：**21 个文件，逐个与仓库逐字节一致**（枚举包内全部 `server/` 条目再比，不写死清单）；含 18 个模块/文件（`wb_proxy.py`、`wb_accounts.py`、`dashboard.html`、`wb_export.py`、`wb_pricing.py`、`wb_atrest.py`、`wb_modelsdev.py`、`wb_prompt.py`、`wb_ipintel.py`、`wb_probes.py`、`wb_catalog.py`、`wb_fingerprint.py`、`wb_identity.py`、`wb_webagent.py`、`wb_webtools.py`、`wb_scheduler.py`、`wb_settings.py`、`wb_tasks.py`）与 `server/pricing/**`。
- payload **不含** `accounts/`、`usage/`、`tests/`、`docs/`、`dist/`、`build/`、`scripts/`、`fnos/`、`.git/`（`scripts/build-fpk.sh` 的 `--exclude='./docs'` 等排除清单生效）。
- fnOS 外壳：`manifest` / `app.tgz` / `ui/**` / `cmd/**` / `wizard/**` / `config/**`；7 个 `cmd/*` 脚本齐全；`ui/config` 与 `fnos/ui/config` 逐字节一致且指向挂载前缀 `/app/workbuddy2api` 与 `app.sock`。
- `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk` → **71 passed, 0 failed**，退出码 `0`（94 行；尾部自述「the package behaves; only a real NAS can test the app store itself」）。该脚本从 55 条扩到 71 条（新增新命名/新模块/禁止目录具名断言），旧包上它会报 2 条失败（`the payload carries every top-level module of the tree`、`every packaged file is byte-identical to the tree`），最终包上全绿。

### 2.7 E6 — 真机设备探针（3 / 0 / 0，只读）

```bash
python3 -u tests/_test_phase_e_verify.py e6_device
```

设备现状（本轮实测）：`/vol1/@appcenter/workbuddy2api/` 已是**新版 1.6.17.1**——`server/` 源码里能 grep 到 `_gateway_trusted`，服务在跑，socket `/vol1/@appcenter/workbuddy2api/app.sock` 可直接只读探测：

- 无 `X-Trim-Username`：`{'panel_password_required': True, 'panel_password_is_default': True, 'authenticated': True, 'via_gateway': True, 'gateway_user': '', 'direct_port': 8788, 'api_key_set': True}` → 新免密口径在**真机**上成立（`authenticated: true` 而 `gateway_user` 为空；`panel_password_required: true` 只表示 TCP 直连仍要密码）。
- 带 `X-Trim-Username: ccrab`：`gateway_user` 回显 `ccrab`，`authenticated` 仍 `true`。
- 设备 `server/**` 与仓库工作树逐字节一致（E8 交叉核对，21 个文件，排除 `__pycache__`/`.pyc`）→ **设备上跑的就是这次交付的这一版**。

（前一轮记录、现已过期：设备当时是旧版，无头 `authenticated: false`、带头才 `true`，本段按 SKIP 处理。E6 的 `unix_request` 之前在无 `AF_UNIX` 的平台上没有守卫，被 E10 预演抓出，见 §3 R5。）

### 2.8 E7 — 免密防线加固面（10 / 0 / 0，另 1 项登记见 §5）

```bash
python3 -u tests/_test_phase_e_verify.py e7_hardening
```

- socket 权限 `0666` → peer 校验确实是唯一防线；socket 上仍申报 `panel_password_required: true`（TCP 仍要密码）。
- **peer 凭据读不到时 fail closed**：`connection=None`（以及「无凭据且无 `X-Trim-Username` 头」）时 `Handler._gateway_trusted()` 返回 `False`，服务端日志 `gateway: peer uid None, sign-on ignored: peer credentials unavailable`。
  这一条是本次验证**换来的加固**：验证初期实测该分支是 fail **open**（`uid is None` 不拒），我把最小复现与建议回传 `api-integrator`，WP-E1 采纳并改成拒绝；`wb_proxy.py` 的 `_gateway_trusted()` docstring 已写明理由（socket 是 0666，unreadable peer 不能假定是网关）。
- 非 gateway 传输带伪造 `X-Trim-Username: root` 不受信。
- API key 边界（见 §5 第 1 条）：socket 上 `/v1/models` 不带头 `200`；TCP 不带头 `401`（`invalid api key - send it as 'Authorization: Bearer <key>'`）；TCP 带正确 key `200`。

### 2.9 E8 — 交付纪律（13 / 0 / 2，提交前/提交后都成立）

```bash
python3 -u tests/_test_phase_e_verify.py e8_delivery
```

本段刻意做成**跨状态**成立，不再钉死某个 HEAD（否则 Lead 一提交/打 tag 自己就红）：

- `git merge-base --is-ancestor 9dff35f HEAD` → `0`：合并提交在 HEAD 的历史里（提交前 HEAD 就等于它，提交后是祖先），两种状态同一事实。
- HEAD 上的 tag：当前为空 → `skip`（不打分）；一旦有 tag，则必须 `== v1.6.17.1` 且 `git cat-file -t` 为 `tag`（annotated）。
- `git ls-files dist` 为空（产物不进版本库）。
- **包内文件相对 HEAD 无未提交改动**：`git status --porcelain -- <PKG_MODULES + scripts fnos .github README.md>`。当前（提交前）如实列出 dirty 项并 `gate`→SKIP；提交后这条自动转 PASS。这是「工作树与 fpk 不会静默分叉」的那道闸。
- `docs/phase-e-delivery.md`（6927 字节）含「包指纹 / 安装与备份 / 已知限制 / 测试路线」四节、写明安装状态、无 `PENDING_*` 占位符；旁置 `.sha256` 与产物一致。
- **设备只读核对**：`/vol1/@appcenter/workbuddy2api/server/**` 逐字节等于仓库工作树（21 个文件、排除 `__pycache__`/`.pyc`）；数据目录 `/vol1/@appdata/workbuddy2api` 只断言仍可读、`accounts/` 仍在。**不用 mtime**（用户随时可能安装/升级，运行中的服务还在持续写数据目录，mtime 断言在真机必然假红，且红了也证明不了什么）；「本次没有对设备执行任何写操作」作为流程事实记 NOTE + 登记项。

### 2.10 E9 — cockpit 兼容导出（35 / 0 / 0，独立段）

```bash
python3 -u tests/_test_phase_e_verify.py e9
```

**契约基准不用我们自己的代码**：`/tmp/panel-latest/internal/panel/import.go` 在本轮已不可读（登记为 NOTE，退回内置 17 键），所以改用**第三方产物锚**——真实 Go 面板导出的样机文件 `/vol2/1000/AgentWork/2api/账号文件/workbuddy-accounts-20261006163005.cockpit.json`：11 行、**每行键集恰好等于本契约的 17 个字段**、`domain` 全是裸主机（无 `://`）、`expires_at` 全是毫秒整数。

自起面板 + 真发 HTTP 的实测：

- `POST /accounts/export {"realm":"intl"|"cn","format":"cockpit"}` → `200`，`data` 是**裸数组**（没有 `accounts` 信封）、`count == len(data)`、`filename` 以 `.json` 结尾、**只含本 realm 的账号**；`format:"native"` 仍是信封（未被 cockpit 改动波及）。
- 每行：键集恰好 17、`expires_at` 毫秒整数（`> 1e12`）、`checkin_streak` 是 int、`token_type == "Bearer"`、`status ∈ {active, disabled}`、`domain` 不带 scheme 且 `is_global_domain()` 的结果与 realm 一致（Go 的 `isGlobalDomain` 逐字等价实现）、带凭据且**不含** `paused|realm|accessToken|refreshToken` 等网关私有字段。
- 往返（模块级）：`wb_accounts.normalise_import_row()` 读导出行的结果 —— token / nickname 不丢、`expires_at` 毫秒被读成秒、`realm` 由 `domain` 推出、`source == "cockpit"`；cn 行仍归 cn。
- 往返（HTTP 级）：另起一台干净面板 `POST /accounts/import {"data": 导出行}` → `200`、`added == 2`、**无 invalid / skipped**；`GET /accounts?realm=all` 回读 intl 行仍归 intl、cn 行仍归 cn；落盘 `accessToken` / `refreshToken` 与导出**逐字相同**。
- 拒绝面：未登录 `401`、缺 `format` `400`、未知 `format` `400`、非法 realm `400`、cockpit 且 `secrets:false` `400`（「cockpit export always carries credentials; drop secrets」）、未知 uid `404`。

结论：**WP-E5（task-15）我这边零发现**；这条与写者自测构成交叉印证（不是同一作者自证）。

### 2.11 E10 — 平台预演：删掉 `socket.AF_UNIX` 后整套仍必须绿（6 / 0 / 0）

```bash
python3 -u tests/_test_phase_e_verify.py e10_platform_sim
```

CI 矩阵里有 `windows-latest`，而 Windows 的 `socket` **没有** `AF_UNIX`／`socketserver.UnixStreamServer`。本段在本机（Linux）复刻那种形状：子进程先 `delattr(socket, "AF_UNIX")` 与 `delattr(socketserver, "UnixStreamServer"/"UnixDatagramServer")`，再 `runpy.run_path(本套件)` 跑整套，断言**退出码 0、`FAIL == 0`、`SKIP > 0`（确实跳过了 AF_UNIX 段）、其余段仍在真跑、输出无 Traceback**。

实测：子进程 `PASS=159 FAIL=0 SKIP=12`（12 条跳过全是 socket 相关：e2 免密三段、e2b peer 矩阵、e3 挂载态 socket、e7 socket 权限/key 边界、e6 真机探针等），父进程 6 / 0 / 0。

这道预演**当场抓到过一个真问题**：`e6_device` 直接调 `unix_request()` 而没有平台守卫，在无 `AF_UNIX` 的进程里抛 `RuntimeError` 让整段崩溃（子进程 `FAIL=1`，失败名 `段 e6_device 自身没有崩溃`）。修法是在 `DEVICE_SOCK` 存在性判断之后加 `needs_unix(...)` 早退，见 §3 R5。这就是「把平台模拟做成套件里的一个真实段」的价值：同一件事以后不会再打红 CI。

## 3. 缺陷与回归清单

| # | 现象 | 归属 | 状态 |
|---|---|---|---|
| R1 | peer 凭据不可读时 `_gateway_trusted()` 判为受信（fail open）：`uid is None` 不拒，socket 又是 0666 | `wb_proxy.py`（WP-E1 / api-integrator） | **已修并复测**：改为 `uid is None` 直接拒绝 + `peer credentials unavailable` 日志；e7 `10 / 0 / 0` |
| R2 | `_test_release_engineering.py:71` 断言 README 声明的套件数与实际扫盘一致，`README.md` 仍写旧值（当时 `README.md:187` = 「77 个套件：60 个 Python + 17 个 JS」） | `README.md`（WP-E3 / packager） | **已修并复测**：现为「85 个套件：66 个 Python + 19 个 JS」，`python3 tests/_test_release_engineering.py` → `Ran 6 tests` / `OK` / exit 0 |
| R3 | `_test_usage_share.js` `PASS=12 FAIL=3`：三条 summary 断言取到 `null`（测试要裸 `<td data-label="总 Token">`，而汇总行/模型行在该 `<td>` 上加了 `title=` 属性） | `dashboard.html` + 该套件（WP-E2 / ui-panel） | **已修并复测**：`node tests/_test_usage_share.js` → `PASS=15 FAIL=0` |
| R4 | 最终包缺失/漂移（`payload 含 server/wb_export.py` 失败、`包内 server/** 与仓库逐字节一致` 失败、`verify-fpk` 2 条失败、交付文档 5 处 `PENDING_*`） | WP-E3 打包时序 | **已消除**：最终包 412737 字节上 e5 `55 / 0 / 0`、`verify-fpk` `71 passed / 0 failed`、`grep -c PENDING` = 0 |
| R5 | 无 `AF_UNIX` 的平台上 `e6_device` 直接调 `unix_request()` 而**没有平台守卫** → 抛 `RuntimeError`，整段崩溃（E10 预演子进程 `FAIL=1`，失败名「段 e6_device 自身没有崩溃」） | `tests/_test_phase_e_verify.py`（我自己的写域） | **已修并复测**：`DEVICE_SOCK` 存在性判断之后加 `needs_unix("真机 socket 只读探针")` 早退；E10 子进程 `PASS=159 FAIL=0 SKIP=12`、父段 `6 / 0 / 0` |
| R6 | **提交前置风险**：`wb_export.py`（`wb_proxy.py:54` 顶层 `import wb_export`）、`tests/_test_cockpit_export.py`、`tests/_test_phase_e_ui2.js`、`tests/_test_phase_e_verify.py` 以及整个 `docs/`（4 个文件）都还是 **untracked（`??`）**；若用 `git commit -am` 提交，这些文件不会进 commit | 提交动作（git 由 Lead 执行） | **待处理**：请用 `git add -A`（或显式 `git add` 上述路径）再提交；否则推上去的提交缺少 `wb_export.py` 会**服务起不来**（不是软失败），CI 的套件数也会从 85 掉到 82 而让 `_test_release_engineering.py` 报 README 不符。提交后 e8 的「包内文件相对 HEAD 无未提交改动」应由 SKIP 转 PASS |

以上五轮内共发现 **4 个真实缺陷（R1/R2/R3/R5）**，全部已修复、我逐条复测转绿；R4 属「等最终包」的时序红，重建后一次性转绿；**R6 是提交动作上的前置条件，尚未发生（提交由 Lead 做），不属代码缺陷但会让 CI 红，已上报**。代码侧当前**无遗留未修复缺陷**。

## 4. 未验证与范围外

1. **真机 fnOS 应用中心安装**：安装属设备写操作，本阶段明令不做。包在沙箱里按 appcenter 真实目录形状解包/启动/导入/升级/停止/卸载（`scripts/verify-fpk.sh`，71 条），但真机安装与「应用中心点击升级」未验证。
2. **真机移动端渲染**：断点与 `data-label` 卡片化只做静态/桩 DOM 断言，未在真机窄屏看过。
3. **真实上游行为**：沙箱无外网，所有上游响应都是伪造的；「真账号能否真的领到积分/点亮任务」未验证。
4. **长时间并发与稳定性**：没有做小时级压测（并发队列、多账号轮询、网关长期连接）。
5. **网关 socket 上「应用自身 uid」这一支**：本机父目录不可遍历，无法起一个非 root 面板复现（见 §2.3）；由写者的 root-only 套件在真机等价环境覆盖。
6. **真机上的写操作**：设备现已装 1.6.17.1，只读探针（E6）在真机上验到 `authenticated: true`、`server/**` 与仓库逐字节一致；但安装/重启/升级全部由用户在应用中心完成，**我一次都没写过设备**，所以「升级会不会丢数据、卸载是否干净」仍不在验证范围。
7. **上游 tag 之后的每日同步**：`sync-upstream.yml` 的实际运行（含冲突中止）未在 CI 上观察。
8. **第二波 UI 的运行时行为（`#btnExportCockpit` 点击流）**：我只独立验了服务端契约（§2.10）与「该按钮经 `wbUrl()` 汇聚点、无新增绝对路径调用」（§2.4），按钮的 DOM 交互由写者套件 `tests/_test_phase_e_ui2.js` 覆盖、其文件与仓库逐字节进包（§2.6），我没有在真浏览器里点过。
9. **windows-latest 上的真跑**：本机是 Linux，只能做「删掉 `socket.AF_UNIX`」的预演（E10，子进程 `PASS=159 FAIL=0 SKIP=12`）与静态检查（`hashlib`、`tempfile`、无 `AF_UNIX` 裸用）；Windows 实际的路径分隔符、`tar.exe`/`bash` 差异、node 版本等，要等 CI 结果确认。E10 已经把「无 AF_UNIX 就得全绿」变成套件里的常驻断言，同一类问题不会再靠 CI 才发现。

## 5. 有意口径差异与登记项（不判 FAIL）

1. **网关 socket 上 `/v1` 的 API key 被一并免掉**（Lead 裁决：保持现状，这是有意设计）。
   事实：`_key_ok()` 首行是 `_panel_ok()`，而 WP-E1 把 `_panel_ok()` 从「socket 且带 `X-Trim-Username` 头」放宽为「socket 且 peer 校验通过」，于是 uid 0 或应用自身 uid 连 socket 打 `/v1` 不带头也 `200`（实测）；TCP 侧不带头 `401`、带正确 key `200`。
   结论一句话：**API key 仍然保护 TCP 入口；网关 socket 上的面板会话同时放开 `/v1`（`_key_ok()` 首行 `_panel_ok()` 的直接后果），属有意设计。**
   理由（三条）：① TCP（局域网直连 8788）仍强制 API key，外部调用者的控制点没动；② socket 上「免 key」的实际可达集 = `uid 0`（网关）或应用自身 uid，前者是根、后者本来就能读写 `/vol1/@appdata/workbuddy2api/**`（含 settings 与账号），没有新增权限面，陌生本地 uid 仍 401；③ 需求就是「网关前门可信、不要重复验证」，把 key 压回网关路径会制造第二种重复验证，与需求相反。
2. **导出路由没有「兄弟模块缺失就软失败」的分支**：`wb_proxy.py:54` 是顶层 `import wb_export`，所以 `wb_export.py` 若不在包里，进程会在启动时**直接起不来**（响亮的失败），而不是让 `POST /accounts/export` 悄悄 503。取舍登记：不另设运行期兜底，改由打包断言保证 —— 我已把 `wb_export.py` 加进 `PKG_MODULES` 并把「包内 `server/**` 与仓库逐字节一致」作为硬断言（§2.6）。
3. **cockpit 行的 realm 只能靠 `domain` 保真**：cockpit 格式没有 realm 字段，所以导出侧会把与 realm 矛盾的旧 `domain` 改写成该 realm 的裸主机，并在服务端日志点名（`cockpit export: N account(s) had a domain outside realm …`），不静默改写；反过来，导入侧一律按 `domain` 推断 realm。这是 Go 面板 `importCockpit` 的既有规则，不是我们的自由度。
4. **失败行仍计入 `credit`/tokens**（只不算 `requests`）——上游 `feed()` 的既有口径，非本阶段引入。

## 6. 交付物与指纹

- 报告：本文档（`docs/phase-e-verify.md`，不在 fpk payload 内；290 行）。
- 验证套件：`tests/_test_phase_e_verify.py`（1698 行，83014 字节，sha256 `e8bf78805fa67668516d87a1327cd56212d283f076a4cff0e86b6ff2823caf73`）。**11 段**：`e1_suites` / `e2_gateway` / `e2_peer_matrix` / `e3_mount` / `e4_credit` / `e5_package` / `e6_device` / `e7_hardening` / `e8_delivery` / `e9_cockpit_export` / `e10_platform_sim`；支持段名子串过滤，环境变量 `WB_PHASE_E_STRICT`、`WB_PKG`、`WB_DASHBOARD_PATH`、`WB_GO_IMPORT_GO`、`WB_COCKPIT_SAMPLE`，并可在无 `socket.AF_UNIX` 的平台上整跑（相关段记 SKIP）。
- 最终包指纹（我独立复算，未改动）：`dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk`，412737 字节，sha256 `5edc6c972e206181b4efeb49fd1c804a5ccb232b6c63a0ce5ed76498d64bbc27`，md5 `d45e598420425a9f992895445f3ef1ff`，manifest `checksum`（app.tgz md5）`7d66e48d4d7738192c0cf7499eb06666`。
- 本条验证结论对应的工作树：HEAD `9dff35f`（提交前），未提交、未打 tag、设备只读。**本轮只改了 `tests/_test_phase_e_verify.py` 与 `docs/phase-e-verify.md`；包内文件一个字节未动**（所以 412737 字节的包仍然有效，无需重打包）。
