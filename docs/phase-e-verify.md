# Phase E 独立验证报告（WP-E4 / task-14）

> 验证者：`verifier`（独立于任何写者）。分支 `phase-e/upstream-sync`，HEAD `55dfad2`（`9dff35f` 合并上游 v1.6.17 及其后 6 个提交之后，本 fork 的交付提交；tag `v1.6.17.1` 已打）。task-20 复跑时 HEAD 已是 `9b6c630`（`v1.6.17.1` 重指在 `adac7eb` 上，HEAD 越过该 tag 一个提交）。
> 立场：不接受写者的口头结论，只认本机实跑输出；伪造输入、边界值、坏 payload、陌生 uid、未登录、未知 realm 一律打。
> 写域：`tests/_test_phase_e_verify.py`（验证套件）、`docs/phase-e-verify.md`（本文）。**本阶段未 `git commit`、未打 tag、未碰设备、未改任何写者文件。**
> 状态：**收口版 + CI 兼容修订（第二轮）+ 发布流水线复核（第三轮，task-18）+ CI Windows 腿修订（第四轮，task-20）**。数字来自最终包（`dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk`，412737 字节，sha256 `5edc6c97…`）上的独立复跑；套件已能在 windows-latest（没有 `socket.AF_UNIX`）上整跑（`e10` 预演），并新增 `e11` 复刻 CI 的真实形状——**shallow clone（depth 1）+ 非 root runner**，因为 v1.6.17.1 的 tag CI 正是被这两件事打红的（见 §3 R7）；`e13` 独立复核发布流水线修复（修复前 `1.6.10.3` → 修复后 `1.6.17.1`；R10 由 Lead 修复、我已复测关闭，见 §2.14）；task-20 修掉最后一条只在 Windows 上红的断言（R12，平台措辞 + 守卫顺序）、把 e5 的包版本断言改成状态感知（R13）、并把 e10 平台预演加硬成「整个进程树都变 Windows 形状」（`sitecustomize.py` 走 `PYTHONPATH`）——加硬后当场暴露 **R14**：`scripts/verify-fpk.sh` 的网关探针依赖 `socket.AF_UNIX`，无该能力时 e5 改为跳过沙箱调用（只记一条 SKIP，不把环境缺失误判成包缺陷）。

## 0. 结论摘要

**合计：PASS=266 / FAIL=0 / SKIP=2；其中 E1..E8 为验收口径（PASS=169），E9 为第二波 WP-E5 的独立交叉验证（PASS=35），E10 为平台兼容预演（PASS=8），E11 为 CI 形状预演（PASS=11），E12 为已发布错包的反向取证（PASS=12，task-19），E13 为发布流水线修复的独立复核（PASS=31，task-18）——后五段都是对套件自身可移植性/发布资产/发布流水线的断言、不计入 E1..E8。另：`run_all.py --jobs 4` = 86 passed / 0 failed / 0 skipped（53.5s，退出码 0；本套件行 `PASS=266 FAIL=0 SKIP=2 50.8s`），`verify-fpk.sh`（本机最终包，HEAD 已越过发布 tag 的当前状态）= 70 passed / 1 failed，唯一红是 `the package is what this tree builds`——因为本树此刻派生 `1.6.17.2` 而包是 `1.6.17.1`（该断言的结构与判定见 §2.6、登记见 §3 R13）。未验证项 11 条见 §4，有意口径差异 3 条 + R11 登记见 §5，R12/R13/R14 三条套件侧问题见 §3，提交前置风险 R6 已闭环（`55dfad2` 提交时用 `git add -A`）见 §3。**

**task-18 结论（一句话）**：流水线修复经我独立复现红/绿——同一个 fixture（CI 当时看得见的 `v1.6.10/.1/.2` + HEAD 上的 `v1.6.17.1`）里，**修复前脚本报 `1.6.10.3`（正是错包版本）、修复后报 `1.6.17.1`**；dispatch 形状（HEAD 无 tag、54 个 tag 都可见）派生 `1.6.17.2`。**R10（`tests/_test_release_pipeline.py` 的 `"file://" + path`）已由 Lead 修复、我复测关闭**，故**可以提交/推送**——详见 §2.14 / §3 R9–R11。

**task-19 结论（一句话）**：Release `v1.6.17.1` 的附件 `WorkBuddy2API-Hub_1.6.10.3_all.fpk`（411262 B）**只是 manifest 版本号错**——它的 payload 26 个文件与本机最终包逐文件 md5 相同、也与仓库逐字节相同，所以**把 tag `v1.6.17.1` 重指到修复提交让 CI 重新构建是安全的**（详见 §2.13 / §3 R8）。

**task-20 结论（一句话）**：windows-latest 腿唯一那条红是**我的断言过严**——CI 原文 `[FAIL] 非 root 模拟：uid 矩阵记为 SKIP（不是 FAIL） -> ['[SKIP] e2b peer uid 矩阵  (本平台没有 socket.AF_UNIX（Windows）：网关 socket 传输不存在)']`；Windows 既没有 `socket.AF_UNIX` 也没有 `os.geteuid`，`needs_unix()` 先于 `needs_root()` 命中，旧断言只认「切 uid 需要 root」这一句。现改为钉「**e2b peer uid 矩阵这一项被跳过**」+「理由是共用常量 `ENV_SKIP_REASONS` 之一」+「绝不是 FAIL」，另加两条防空跑断言（段名确实命中、子跑恰好 `PASS=0 FAIL=0 SKIP=1`）；同一份 Windows 形状输出上实测：旧断言 `False`（= CI 的红）、新断言 `True`（详见 §2.12 / §3 R12）。顺手审计了整份套件里依赖平台措辞/POSIX 行为/具体错误文本的断言，见 §3 R12 末尾的审计表。

| # | 验收项 | 判定 | 通过 / 不通过 / 跳过 | 证据（命令见 §1 / 详见 §2） |
|---|---|---|---|---|
| E1 | 全量套件 `run_all.py --jobs 4` | **通过** | 86 / 0 / 0（本段自身 10 / 0 / 0） | §2.1 |
| E2 | 网关免密 E2E + TCP 伪造仍被拒 | **通过** | 14 / 0 / 0 | §2.2 |
| E2b | peer uid 矩阵（root 放行 / 陌生 uid 拒绝） | **通过（1 项跳过）** | 4 / 0 / 1 | §2.3 |
| E3 | 挂载前缀契约（`<base href>` / `__WB_BASE__` / 直连不注 / 所有调用带前缀） | **通过** | 32 / 0 / 0 | §2.4 |
| E4 | 每 M tokens 积分（后端 credit 累加 + 界面除零保护） | **通过** | 26 / 0 / 0 | §2.5 |
| E5 | 最终 fpk 一致性（命名 / payload / 逐字节 / verify-fpk） | **通过** | 56 / 0 / 0 | §2.6 |
| E6 | 真机设备探针（只读；设备已装 1.6.17.1） | **通过** | 3 / 0 / 0 | §2.7 |
| E7 | 免密防线加固面（socket 权限 / peer 不可读取向 / key 边界） | **通过（1 项登记）** | 10 / 0 / 0 | §2.8 |
| E8 | 交付纪律（跨提交状态成立 + 设备上跑的就是交付版） | **通过（1 项跳过）** | 15 / 0 / 1 | §2.9 |
| E9 | cockpit 兼容导出（独立段，交叉验证 WP-E5） | **通过（不计入 E1..E8 口径）** | 35 / 0 / 0 | §2.10 |
| E10 | 平台预演：删掉 `socket.AF_UNIX` 后整套仍绿 | **通过（不计入 E1..E8 口径）** | 8 / 0 / 0 | §2.11 |
| E11 | CI 预演：shallow clone（depth 1）+ 非 root runner | **通过（不计入 E1..E8 口径）** | 11 / 0 / 0 | §2.12 |
| E12 | 已发布错包反向取证（Release 资产 vs 本机包 vs 仓库） | **通过（不计入 E1..E8 口径）** | 12 / 0 / 0 | §2.13 |
| E13 | 发布流水线修复（tag 可见性 / 版本推导 / 六条对抗） | **通过（不计入 E1..E8 口径；1 项登记见 §5）** | 31 / 0 / 0 | §2.14 |
| — | **合计（E1..E13）** | **通过** | **266 / 0 / 2** | — |

E8 的 1 项跳过是「包内文件相对 HEAD 无未提交改动」——本轮复跑时 packager 正在改 `scripts/build-fpk.sh`、`.github/workflows/*.yml`、`README.md`（都不是 payload 文件，e5 的逐字节比对才是真正抓包的断言），所以它按设计记 SKIP 而不是红；E2b 的 1 项跳过是本机无法以陌生 uid 起面板（§4 第 5 条）。

配套（写者的套件，我作为独立方在 E1 里确认其真的跑起来且不是被跳过，未改写者结论）：
`_test_gateway.py`、`_test_gateway_ui.js`、`_test_json_account_import.py`、`_test_model_credit.py`、`_test_platform_import.py`。

## 1. 复现入口

```bash
# 全量套件（E1 就是它；套件自身的 e1 段做同样的事并断言计数自洽）
python3 tests/run_all.py --jobs 4

# 我的验证套件：可整跑，也可按段名子串只跑一段（e1..e13）
python3 -u tests/_test_phase_e_verify.py
python3 -u tests/_test_phase_e_verify.py e2_gateway     # 只跑免密段
python3 -u tests/_test_phase_e_verify.py e5_package     # 只跑包一致性段
python3 -u tests/_test_phase_e_verify.py e9             # 只跑 cockpit 导出段
python3 -u tests/_test_phase_e_verify.py e10            # 只跑平台预演段（内部会再整套跑一遍）
python3 -u tests/_test_phase_e_verify.py e11            # 只跑 CI 预演段（depth-1 clone + 非 root）
python3 -u tests/_test_phase_e_verify.py e12            # 只跑已发布错包反向取证（要先下载资产）
python3 -u tests/_test_phase_e_verify.py e13            # 只跑发布流水线段（临时 repo fixture，不碰工作树）

# 下载 Release v1.6.17.1 的资产（错包）交给 e12 复算（默认路径就写在这里；没有副本时该段记 SKIP）
mkdir -p /tmp/wb-wrongpkg && cd /tmp/wb-wrongpkg
curl -sSL -o WorkBuddy2API-Hub_1.6.10.3_all.fpk \
  https://github.com/ccrabit/workbuddy2api-hub/releases/download/v1.6.17.1/WorkBuddy2API-Hub_1.6.10.3_all.fpk
# .sha256 走 browser URL 会以 curl(18)（HTTP/2 断流）失败，要用 API 资产端点（公开仓库无需 Authorization，
# 302 由 -L 跟随；若带 Authorization 反而 403）：
curl -sSL --http1.1 -H "Accept: application/octet-stream" \
  -o WorkBuddy2API-Hub_1.6.10.3_all.fpk.sha256 \
  https://api.github.com/repos/ccrabit/workbuddy2api-hub/releases/assets/623945562
WB_WRONG_PKG=/tmp/wb-wrongpkg/WorkBuddy2API-Hub_1.6.10.3_all.fpk \
  python3 -u tests/_test_phase_e_verify.py e12

# 对下载来的错包跑仓库的完整性门（不碰 dist/：脚本用 mktemp 并在结尾删除工作目录）
bash scripts/verify-fpk.sh /tmp/wb-wrongpkg/WorkBuddy2API-Hub_1.6.10.3_all.fpk   # 70 passed / 1 failed

# CI 形状复现（e11 做的事情，也可以手工验一遍）
git clone --depth 1 --branch v1.6.17.1 file://"$PWD" /tmp/ci-sim && cd /tmp/ci-sim
python3 tests/run_all.py --jobs 4        # 未修版（tag 里的那一版）：84 passed, 1 failed
cp "$OLDPWD/tests/_test_phase_e_verify.py" tests/ && python3 tests/run_all.py --jobs 4   # 85 / 0 / 0

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

**CI 形状（shallow clone + 非 root）**：`e8` 的两条历史断言先看 `is_shallow()`/`git cat-file -e 9dff35f^{commit}`，`e2b` 的 uid 矩阵先看 `needs_root()`（`getattr(os, "geteuid", lambda: -1)() != 0`），二者在 CI 上记 SKIP 而不是红；`e11` 在本机用 `git clone --depth 1 file://…` 与 `os.geteuid = lambda: 1000` 把这两个形状做成常驻预演（§2.12）。

## 2. 逐项结论

### 2.1 E1 — 全量套件（86 / 0 / 0）

```bash
python3 tests/run_all.py --jobs 4
```

原始尾部（task-20 最终复跑，`/tmp/wb-e20b-runall.log`；task-20 加硬 e10 之前那轮为 `PASS=264` / `66.0s`，task-18 那轮为 `PASS=261` / `62.5s`，task-19 那轮为 `PASS=231` / `56.8s`）：

```
  [PASS] _test_connection_reuse.py              SUMMARY: PASS=8 FAIL=0                                12.6s
  [PASS] _test_phase_e_verify.py                PASS=266 FAIL=0 SKIP=2                                50.8s

  slowest: _test_phase_e_verify.py 50.8s, _test_connection_reuse.py 12.6s, _test_pricing_switch.py 3.6s
  86 passed, 0 failed, 0 skipped  (/vol2/1000/AgentWork/2api/workbuddy2api-hub)
  total 53.5s with --jobs 4
```

- 验收口径 **86 passed, 0 failed, 0 skipped**（86 = 67 Python + 19 JS，含我的 `_test_phase_e_verify.py`、第二波 UI 套件 `_test_phase_e_ui2.js`，以及 packager 本轮新增的 `tests/_test_release_pipeline.py`），与我实读的 `README.md:187`「86 个套件：67 个 Python + 19 个 JS」一致。（CI 期望值由 Lead 给的 85 变为 **86**，是新增套件所致，不是套件被跳过。）

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

### 2.6 E5 — 最终 fpk 一致性（56 / 0 / 0）

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
- `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk`：**同一命令的输出随 HEAD 相对发布 tag 的位置而变**（本轮实测两种状态）——
  - HEAD 就是发布 tag 时（`55dfad2`，包构建时）→ **71 passed, 0 failed**，退出码 `0`（94 行；尾部自述「the package behaves; only a real NAS can test the app store itself」）。
  - HEAD 越过 tag 一个提交时（`9b6c630`，task-20 复跑时）→ **70 passed, 1 failed**，唯一失败名 `the package is what this tree builds`：本树 `bash scripts/build-fpk.sh --print-version` = **`1.6.17.2`**（`v1.6.17.1` 在 `adac7eb` 上，HEAD 上的 `9b6c630` 是它的下一个提交），而包 manifest 是 `1.6.17.1`；payload 逐字节比对等其余 70 条全过。这不是包的问题，也不是产品缺陷：该断言的定义就是「包 == 本树此刻会构建出来的东西」，HEAD 一动它必然改口。
  - 该脚本从 55 条扩到 71 条（新增新命名/新模块/禁止目录具名断言），旧包上它会报 2 条失败（`the payload carries every top-level module of the tree`、`every packaged file is byte-identical to the tree`），最终包上全绿。
- 因此 e5 段对 verify-fpk 的判定改成**状态感知**（不再写死「0 failed」）：先取 `bash scripts/build-fpk.sh --print-version` 与包 manifest 的 `version`——相等时要求 **0 failed**；不相等时要求**恰好 1 条失败、失败名就是 `the package is what this tree builds`、且派生值确实 != 包版本**，另外要求通过条数仍成规模（不是脚本半途夭折），退出码 `0` 或仅因这一条而 `1`。运行输出原文：
  ```
  [NOTE] 包版本 vs 本树派生版本 = {'package': '1.6.17.1', 'deriving': '1.6.17.2', 'same_tree': False,
                                  'failed_names': ['the package is what this tree builds']}
  [PASS] verify-fpk 只反对「包版本 != 本树派生版本」这一条（树已越过发布 tag）
  [PASS] verify-fpk 的其余断言仍成规模（不是脚本半途夭折）
  [PASS] verify-fpk 退出码 0，或仅因树越过 tag 而 1
  ```
  这条耦合登记为 §3 R13。
- **无 `socket.AF_UNIX` 时这一条会变成假红**（task-20 加硬 e10 后实测）：`scripts/verify-fpk.sh` 的网关探针本身就是 unix socket 客户端（`:330` / `:379` 用 `socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)` 连 `<payload>/app.sock`，`:126` 断言 `cmd/main` 带 `--unix-socket`，`:416` 断言 socket `0666`）。把整个进程树变成 Windows 形状后同一份包实测 **67 passed / 4 failed**，多出的三条正是 `the gateway socket is world-writable`、`the gateway signs the NAS user in (exit 1, wanted 0)`、`...and still does when the session header is gone (exit 1, wanted 0)`——都是「沙箱跑不起来」，不是包的问题。所以 e5 现在先判 `HAS_UNIX`：没有 `AF_UNIX` 就只记一条 SKIP、不调沙箱（`register` R14，见 §3 R14），上面的 tar/命名/manifest/payload/checksum 断言照跑（它们与传输无关）。

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

### 2.9 E8 — 交付纪律（15 / 0 / 1，提交前/提交后都成立）

```bash
python3 -u tests/_test_phase_e_verify.py e8_delivery
```

本段刻意做成**跨状态**成立，不再钉死某个 HEAD（否则 Lead 一提交/打 tag 自己就红）：

- `git merge-base --is-ancestor 9dff35f HEAD` → `0`：合并提交在 HEAD 的历史里（提交前 HEAD 就等于它，提交后是祖先），两种状态同一事实。**但 shallow clone（CI 的 `fetch-depth: 1`）里这个对象根本不可达**，此时先判 `git rev-parse --is-shallow-repository` 与 `git cat-file -e 9dff35f^{commit}`，不成立就记 `skip`（文案点明「CI 走这条」），不削弱完整 clone 上的强断言（见 §3 R7、§2.12）。
- HEAD 上的 tag：当前为 `v1.6.17.1`，`git cat-file -t` = `tag`（annotated）；shallow clone 里 tag 对象不可达时改记 `skip`（本机 clone 实测 annotated 对象反而可达，但 CI 的 checkout 只取 commit，报 `commit`）。
- `git ls-files dist` 为空（产物不进版本库）。
- **包内文件相对 HEAD 无未提交改动**：`git status --porcelain -- <PKG_MODULES + scripts fnos .github README.md>`。提交前如实列出 dirty 项并 `gate`→SKIP，提交后转 PASS。这是「工作树与 fpk 不会静默分叉」的那道闸。
- `docs/phase-e-delivery.md`（6927 字节）含「包指纹 / 安装与备份 / 已知限制 / 测试路线」四节、写明安装状态、无 `PENDING_*` 占位符；旁置 `.sha256` 与产物一致。
- **设备只读核对**：`/vol1/@appcenter/workbuddy2api/server/**` 逐字节等于仓库工作树（21 个文件、排除 `__pycache__`/`.pyc`）；数据目录 `/vol1/@appdata/workbuddy2api` 只断言仍可读、`accounts/` 仍在。**不用 mtime**（用户随时可能安装/升级，运行中的服务还在持续写数据目录，mtime 断言在真机必然假红，且红了也证明不了什么）；「本次没有对设备执行任何写操作」作为流程事实记 NOTE + 登记项。

本段在 task-19 复跑时是 **15 / 0 / 1**：唯一 SKIP = 「包内文件相对 HEAD 无未提交改动」，因为当时 packager 正在改 `scripts/build-fpk.sh`、`.github/workflows/{build-fpk,sync-upstream}.yml`、`README.md`（四行 dirty 被原样打出；`docs/phase-e-verify.md` 与 `tests/_test_phase_e_verify.py` 是我自己在改，也在清单里）。这四行**都不是 payload 文件**，真正抓「工作树与 fpk 分叉」的是 e5 的逐字节比对（当时 55 / 0 / 0 全绿；task-20 改成状态感知后为 56 / 0 / 0，见 §2.6），所以按设计记 SKIP 而不是红。`scripts/verify-fpk.sh` 与 `scripts/build-fpk.sh` 不在任何 payload 里（§2.6 的禁止清单里就含 `scripts/`）。

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

### 2.11 E10 — 平台预演：删掉 `socket.AF_UNIX` 后整套仍必须绿（8 / 0 / 0）

```bash
python3 -u tests/_test_phase_e_verify.py e10_platform_sim
```

CI 矩阵里有 `windows-latest`，而 Windows 的 `socket` **没有** `AF_UNIX`／`socketserver.UnixStreamServer`，`os` 也**没有** `geteuid`。本段在本机（Linux）复刻那种形状，并且 task-20 把它加硬成**整棵进程树**都是这种形状：一段 `sitecustomize.py`（删 `socket.AF_UNIX`、`socketserver.Unix*` 六个类，`if hasattr(os,"geteuid"): del os.geteuid`）写到临时目录并放进 `PYTHONPATH`——CPython 在 site 初始化时会导入 `PYTHONPATH` 上的 `sitecustomize`，所以本段拉起的子进程**以及子进程再拉起的孙进程**都变 Windows 形状；孙进程只 `runpy.run_path(本套件)` 跑整套，然后断言**退出码 0、`FAIL == 0`、`SKIP > 0`（确实跳过了 AF_UNIX 段）、其余段仍在真跑、输出无 Traceback、新起的解释器形状恰为 `False False`**。

为什么必须加硬：旧版只在子进程里 `delattr`，孙进程（`e11` 的 shallow-clone 子跑、非 root 子跑）仍是完整 Linux socket 模块，于是**抓不到 R12**（CI 那条 windows-latest 假红恰恰靠孙进程的措辞差异）。

实测（task-20 复跑）：子进程 `PASS=201 FAIL=0 SKIP=13`（13 条跳过全是 socket 相关：e2 免密三段、e2b peer 矩阵、e3 挂载态 socket、e7 socket 权限/key 边界、e6 真机探针、e5 的 verify-fpk 沙箱等），父进程 8 / 0 / 0。加硬后当场红过一次（父段 `4 / 3`，子进程 `PASS=203 FAIL=1`），那次红**问出了 R14**（`verify-fpk.sh` 的网关探针依赖 `AF_UNIX`），修法是 e5 在无 `AF_UNIX` 时跳过沙箱调用。

同一轮里还纠正了我自己的一个错误断言：原打算用「孙进程的 `[SKIP] e2b peer uid 矩阵 (...AF_UNIX...)` 行」来证明形状继承，但 `e11` 在嵌套预演里会**自我跳过**（`WB_E1_NESTED`/`WB_E11_NESTED` 守卫，防递归），输出里根本没有那一行——于是改成直接探孙辈解释器形状（断言 `hasattr(socket,'AF_UNIX'), hasattr(os,'geteuid')` 打印 `False False`），并加一条「e11 在嵌套预演里确实自我跳过」的断言把原因写清。

这道预演**当场抓到过一个真问题**：`e6_device` 直接调 `unix_request()` 而没有平台守卫，在无 `AF_UNIX` 的进程里抛 `RuntimeError` 让整段崩溃（子进程 `FAIL=1`，失败名 `段 e6_device 自身没有崩溃`）。修法是在 `DEVICE_SOCK` 存在性判断之后加 `needs_unix(...)` 早退，见 §3 R5。这就是「把平台模拟做成套件里的一个真实段」的价值：同一件事以后不会再打红 CI。

### 2.12 E11 — CI 预演：shallow clone（depth 1）+ 非 root runner（11 / 0 / 0）

```bash
python3 -u tests/_test_phase_e_verify.py e11
```

tag `v1.6.17.1` 的 CI（run `37886526097`，`head_sha 55dfad2`）三平台 tests 全红，唯一红的就是本套件，现象是 `[FAIL] 合并提交 9dff35f 在 HEAD 的历史里 -> 128`、`[FAIL] tag v1.6.17.1 是 annotated -> commit`、`[FAIL] uid 0（=网关）连 socket -> authenticated: true -> (127, {})`。根因两条，都是**环境形状**而不是产品缺陷：

- `actions/checkout` 默认 **shallow clone（`fetch-depth: 1`）**：`git merge-base --is-ancestor 9dff35f HEAD` 报 `fatal: Not a valid object name 9dff35f`（rc 128），`git cat-file -t v1.6.17.1` 只拿到 commit 而拿不到 annotated tag 对象。
- runner **不是 root**（uid 1000）：`setpriv` 切到陌生 uid 的探针以 127 失败，而 `needs_unix()` 只判了 `AF_UNIX` 存在（Linux CI 有，非 root 没有权限）。

改法（只在本套件里）：`e8` 先算 `git rev-parse --is-shallow-repository` 与 `git cat-file -e 9dff35f^{commit}`，任一不成立就把两条**历史**断言记 `skip`（完整 clone 时强断言不削弱，本机仍是 PASS）；`e2b` 在 `setpriv` gate 之后加 `needs_root()`，非 root 记 `skip`；新增本段把这个形状固化成常驻断言。

本机实测（`file://` 是关键——普通本地路径 clone 会忽略 `--depth`、整段历史都在，那样预演什么都证明不了）：

| 步骤 | 结果 |
|---|---|
| `git clone --quiet --depth 1 file://<repo> <tmp>/shallow` | 成功；`is-shallow-repository` = `true` |
| 在该 clone 里 `git merge-base --is-ancestor 9dff35f HEAD` | rc `128`（复刻 CI 的 `-> 128`） |
| clone 里跑 `e8_delivery e2_peer_matrix`（用工作树那一版套件） | `PASS=18 FAIL=0 SKIP=2`，被跳过的正是「9dff35f 祖先关系」与「annotated 判定」，`FAIL=0`、退出码 0 |
| 非 root 模拟子进程（`os.geteuid = lambda: 1000`）只跑 `e2_peer_matrix` | 退出码 0、`FAIL=0`、`PASS=0 FAIL=0 SKIP=1`（记「切 uid 需要 root」） |

**端到端复算（Lead 指定的那条命令）**：

```bash
git clone --depth 1 --branch v1.6.17.1 file:///vol2/1000/AgentWork/2api/workbuddy2api-hub /tmp/ci-sim
cd /tmp/ci-sim && python3 tests/run_all.py --jobs 4
#   84 passed, 1 failed, 0 skipped   （失败项就是 `_test_phase_e_verify.py`，复现 CI 红）
cp /vol2/1000/AgentWork/2api/workbuddy2api-hub/tests/_test_phase_e_verify.py tests/
python3 tests/run_all.py --jobs 4
#   85 passed, 0 failed, 0 skipped   （同一 shallow clone，换成修好的套件即全绿）
```

本机（非 shallow，HEAD `55dfad2`）：`python3 tests/run_all.py --jobs 4` = **85 passed / 0 failed / 0 skipped**（57.9s，exit 0），其中本套件 `PASS=220 FAIL=0 SKIP=1`（55.1s）。（这两段数字是 task-19 之前那一刻的快照，当时树里是 85 个套件；task-19 复跑时 packager 新增了 `tests/_test_release_pipeline.py`，树与 README 一起变成 86，见 §2.1。）

**第四轮（task-20）：Windows 腿最后一条红 = 我自己的断言过严。** tag `v1.6.17.1` 重指到 `adac7eb` 后的 CI（run `37891379131`，HEAD `9b6c630`）三个腿里只有 `windows-latest / python 3.12` 红，唯一红行原文（我从 artifact `suite-logs-windows-latest-3.12` 读到，与 Lead 转述逐字一致）：

```
  [FAIL] 非 root 模拟：uid 矩阵记为 SKIP（不是 FAIL）  -> ['[SKIP] e2b peer uid 矩阵  (本平台没有 socket.AF_UNIX（Windows）：网关 socket 传输不存在)']
```

根因是**守卫顺序 + 措辞耦合**：Windows 既没有 `socket.AF_UNIX` 也没有 `os.geteuid`，所以 `e2b` 的 `needs_unix()`（`tests/_test_phase_e_verify.py:619`）**先于** `needs_root()` 命中，落下的 skip 文案是 AF_UNIX 那条；而 e11 的非 root 断言只认「切 uid 需要 root」这一句，于是「确实按设计跳过了」被判成红。`e11` 当时 `PASS=8 FAIL=1`，其余两条（退出码 0、`FAIL == 0`）已过。

改法（只在本套件里，`tests/_test_phase_e_verify.py`）：

- 新增共用常量 `SKIP_NO_UNIX = "本平台没有 socket.AF_UNIX（Windows）：网关 socket 传输不存在"`、`SKIP_NO_ROOT = "切 uid 需要 root（CI runner 非 root）：本段跳过"`、`ENV_SKIP_REASONS = (SKIP_NO_UNIX, SKIP_NO_ROOT)`，`needs_unix`/`needs_root` 改成用它们发 skip（单一真相源，断言与文案不再各写一份）。
- 断言重写为：**`e2b peer uid 矩阵` 这一项确实出现在 SKIP 行里**（按项目名钉住，不是只看计数）+ **理由是 `ENV_SKIP_REASONS` 之一**（环境原因，不是产品原因）+ **同一项绝不出现在 FAIL 行里**；再加两条防空跑断言：`e2b peer uid 矩阵` 确实被段名过滤命中并跑到、以及子跑计数**恰好** `PASS=0 FAIL=0 SKIP=1`（只有这一项）。所以没有退化成「只看 `SKIP=1`」的永真断言——项目名写错、e2b 被整段漏跑、或者它变成 FAIL，都仍然会红。
- 顺手审计同类脆弱点（Windows / 无 AF_UNIX 下逐条复核）：AF_UNIX 相关探针（e2 socket 半段 / e2b / e3 / e6 / e7）都由 `needs_unix` 或 `HAS_UNIX` 门住；`setpriv`+`chown` 类只出现在 `needs_root` 之后；`/vol1/**` 只读探针先判目录存在；`tar`/`bash`/`git` 三个外部工具各有一道 gate，缺工具走 SKIP（e8 此前没有 gate，无 git 会 `FileNotFoundError` 崩段 → 已补）；文本文件读取全部显式 `encoding`（无 cp1252 陷阱）；路径比较都已 `.replace(os.sep, "/")`；唯一断言产品措辞的地方是本套件自己的日志串（`gateway: peer uid`）与 unittest 的 `Ran`/`OK` 字样。同一类「钉死别人的测试条数」的三处断言也放松成解析 `Ran (\d+) tests` / `skipped=(\d+)` 后断关系（`rc == 0` + 条数 > 0 + 0 < skip < ran），不再写死 `Ran 8 tests`／`skipped=5`。

复算证据（红/绿同一份输出）：

| 步骤 | 结果 |
|---|---|
| Windows 形状预演（`/tmp/winsim/sitecustomize.py`：删 `socket.AF_UNIX`、删 `socketserver.UnixStreamServer/UnixDatagramServer`、`del os.geteuid`；`PYTHONPATH` 让子进程继承）里跑 `e11` | **PASS=11 FAIL=0 SKIP=0**；NOTE 打出的 skip 文案正是 CI 里那一句 |
| 把同一份 Windows 形状输出喂给两个断言（`PYTHONPATH=/tmp/winsim` 的 `os.geteuid = lambda: 1000` 子进程） | 旧断言（只认「切 uid 需要 root」）= **False**（= CI 的红）；新断言（项目名 + `ENV_SKIP_REASONS` 之一）= **True** |
| 真 `git clone --depth 1 file://<repo>`（`is-shallow-repository` = `true`）里跑 `e8_delivery e2_peer_matrix e11_ci_rehearsal`，用仓库里已提交的那版套件 | `PASS=26 FAIL=0 SKIP=2` |
| 同一个 clone 里换成工作树这一版套件再跑同样三段 | `PASS=28 FAIL=0 SKIP=2`（跳过两条仍是按设计的历史断言） |
| 缺工具守卫：`env PATH=/tmp/emptybin /usr/bin/python3 -u tests/_test_phase_e_verify.py e8_delivery e13_release_pipeline` | `PASS=10 FAIL=0 SKIP=2`（e8 记「本机没有 git」，e13 静态 10 条照跑、行为段记「本平台没有 bash, git」） |

`e11` 段最终 **11 / 0 / 0**（`PASS=11 FAIL=0 SKIP=0`），并在段尾 `register("R12 …")` 记录这条平台措辞/守卫顺序的修复（见 §3 R12）。

### 2.13 E12 — 已发布错包反向取证（12 / 0 / 0，task-19）

```bash
WB_WRONG_PKG=/tmp/wb-wrongpkg/WorkBuddy2API-Hub_1.6.10.3_all.fpk \
  python3 -u tests/_test_phase_e_verify.py e12
bash scripts/verify-fpk.sh /tmp/wb-wrongpkg/WorkBuddy2API-Hub_1.6.10.3_all.fpk
```

要回答的问题：Release `v1.6.17.1` 的附件是 `WorkBuddy2API-Hub_1.6.10.3_all.fpk`（411262 B）——**它是不是只是版本号错、payload 与我们要发布的一致？能不能把 tag 重指到修复提交让 CI 重新构建？**

取证链（每一步都独立复算，不采信任何一方口述）：

| 步骤 | 实测 |
|---|---|
| 下载完整性 | 资产 `id=623945559`，411262 B，sha256 `c5b7da5fe4f35a5c8ef3327cb192227f9d86a6b86ed40744586a0d3945e25351`；GitHub 附带的 `.sha256`（`id=623945562`，101 B）内容与实算**逐字符一致** → 下载物没坏 |
| 与本地最终包的关系 | 错包 md5 `402ddfd3ebaa9a7f58ed89babe9a74de`；本机 `dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk` 412737 B / sha256 `5edc6c97…bbc27` |
| manifest（各 14 行） | **只差两行**：`version = 1.6.10.3` vs `1.6.17.1`；`checksum = 36039fe3d92f180b1a5e96256fc974be` vs `7d66e48d4d7738192c0cf7499eb06666`。其余逐字相同（`appname = workbuddy2api`、`display_name = WorkBuddy2API-Hub`、`platform = all`、`service_port = 8788`、`source = thirdparty`、maintainer/distributor 等） |
| 包内部自洽 | **两份包各自 `manifest.checksum == md5(自己的 app.tgz)`** → 错包在完整性意义上是「合格包」，sha256/checksum 类断言抓不到版本错 |
| 外层 tar（各 25 个成员） | 成员名集合一致；**只有 `app.tgz` 尺寸不同**（391188 vs 391960，Δ772）与两处权限差（`app.tgz`/`manifest` 0644 vs 0755）；23 个成员尺寸权限完全相同；所有外层成员 mtime 都不同（错包 `1791522039` = CI 构建 2026-10-09 13:00 CST，本机 `1791517184` = 11:39） |
| app.tgz 内层（各 31 个成员） | **名字+大小+权限表完全相同**（表 md5 `c155e7dd87aa58846159bbdb2644e56a`）；内层文件 mtime 不同；两个 gzip 头 mtIME 字段都是 0 → **app.tgz 的字节差异只来自 tar 成员 mtime** |
| payload 逐文件 | 各 26 个文件（`server/**` 21 + `config/{privilege,resource}` + `ui/config` + `ui/images/{64,256}.png`）；**逐文件 md5 完全一致**，排序后「路径+md5」总哈希两份都是 `4c2296ddd9247d83259742aa33bc2ad9` |
| payload vs 仓库工作树 | 映射 `server/*`→仓库根、`ui/config`→`fnos/ui/config`、`ui/images/64.png`→`fnos/ICON.PNG`、`ui/images/256.png`→`fnos/ICON_256.PNG`、`config/*`→`fnos/config/*`：错包 `相同 26 / 不同 0`，本机包 `相同 26 / 不同 0` |
| 仓库侧漂移 | `git diff --stat HEAD -- ':(top)*.py' ':(top)pricing' ':(top)fnos' ':(top)LICENSE' ':(top)dashboard.html'` **无输出** → payload 源文件相对 HEAD 无未提交改动（所以「payload == 仓库」等价于「payload == 提交代码」） |
| 仓库的完整性门怎么看它 | `bash scripts/verify-fpk.sh <错包>` → **70 passed / 1 failed**，exit 1；唯一红是 `:103 assert "the package is what this tree builds" test "$(build-fpk.sh --print-version)" = "$MANIFEST_VERSION"`（树推导 1.6.17.1 ≠ 包 1.6.10.3）。同一份脚本对**本机最终包** → **71 passed / 0 failed**；其中 `PASS every packaged file is byte-identical to the tree` 对**错包也通过** |
| 版本方向 | 四段版本比较 `1.6.10.3 < 1.6.17.1` → 若有人在 1.6.17.1 之后装错包，应用中心会判为**降级**；用户设备上装的是本地构建的 1.6.17.1（§2.7），Release 资产 `download_count = 0` |

**结论：可以重指 tag。** 错包只是 manifest 的 `version`（以及由 app.tgz mtime 派生的 `checksum`）错，payload 与要发布的代码**逐文件一致**、也与仓库 HEAD 一致；没有任何用户装过这个错包，所以重指 tag 不会造成「设备收到的代码与已装代码不同」。重指的代价与注意事项：

1. Release 会重建 → 新的 `.sha256`（附件名也会变回 `WorkBuddy2API-Hub_1.6.17.1_all.fpk`），凡是把旧 sha256 记下来的人需要改用新值；
2. 重指前值得跑一次 `git diff --stat <旧 tag 提交>..<新 tag 提交> -- ':(top)*.py' ':(top)pricing' ':(top)fnos' ':(top)LICENSE' ':(top)dashboard.html'`，输出为空才能保证「新包 payload 与设备已装的那份完全相同」；一旦 payload 源文件有改动，新包就不是「同名同内容重发」而是真正的代码更新（那也未必是错，但要让用户知道）；
3. CI 侧版本必须由「HEAD 上的四段 tag」直接决定（task-17 正在做的事），否则同一次提交在开发机与 CI 上还会算出两个版本。

### 2.14 E13 — 发布流水线修复：独立复核（30 / 0 / 0，task-18）

命令：`python3 -u tests/_test_phase_e_verify.py e13`（段内所有 fixture 都在 `tempfile` 临时 repo 里，不写工作树）；对照的手工复现见下表的「原始输出」列。

**六条对抗检查（Lead task-18 必做 3 的逐条判定）**

| # | 检查 | 判定 | 证据 |
|---|---|---|---|
| ① | HEAD 上有多个四段 tag | **通过** | fixture 同时挂 `v1.6.17.2` 与 `v9.9.9.9` → `--print-version` = `9.9.9.9`（`git tag --points-at HEAD \| sort -V \| tail -1`，确定性取最高）；此时若 workflow 推的是 `v1.6.17.2`，比对 `1.6.17.2 != 9.9.9.9` → **REFUSE**（不会静默出错版本） |
| ② | annotated tag | **通过** | `git cat-file -t <tag>` = `tag`、`git tag --points-at HEAD` 同样列出 annotated tag、`--print-version` 照常给出该 tag；alpha 模式在 HEAD 有 tag 时给 `1.6.17.1-alpha12`（`-alpha` 构建按构造就是推导值，有意） |
| ③ | 旧提交上的 `v1.6.10.1/.2` 是否仍给对 ordinal | **通过** | 无 tag 的 HEAD（只看得见 `v1.6.10`/`.1`/`.2`）→ `1.6.10.3`（与修复前一致，历史行为未被破坏）；一旦 `v1.6.17` 也可见 → `1.6.17.1`（四段 tag 不当 base，`upstream_tag()` 的 grep 只认三段） |
| ④ | dispatch 在无上游 tag 的克隆里派生什么 | **通过（残留风险已量化，见 R11）** | 见下方「④ 实测」 |
| ⑤ | `git push origin --tags` 会不会泄本地临时 tag | **通过（证伪）** | 全仓 workflow 里 `git push` 只有 4 处：`sync-upstream.yml:92` 推**单个**上游 tag 的 ref、`:116` `HEAD:main`、`:254` 推**单个** release tag 的 ref，另两处是文档字符串；`re.search(r"git push[^\n]*--tags")` 无命中（`--tags` 只出现在 `git fetch --tags`/`git ls-remote --tags`）。且镜像循环前先 `git ls-remote --exit-code --tags origin refs/tags/<t>` 判存在 → 幂等、只推缺的、不会顺手把本地临时 tag 推上去 |
| ⑥ | 新套件在 Windows / 浅克隆下是 SKIP 还是崩 | **通过（原登记的 R10 已由 Lead 修复，见下）** | `tests/_test_release_pipeline.py`：正常树 `Ran 8 tests / OK`；`PATH=""`（bash 与 git 都不在）→ `Ran 8 tests / OK (skipped=5)`、rc 0（3 条静态用例照跑，5 条行为用例 `skipTest("needs bash and git on PATH")`）；只有在 PATH 上放 `git` 而没 `bash` → 同样 5 条 skip、rc 0；`--depth 1` 浅克隆里覆盖工作树文件 → `Ran 8 tests / OK`。**浅克隆里若保留 HEAD 上修复前的已提交脚本 → `FAILED (failures=6)`**，说明这套用例真的能因错版本变红（不是空转）。**R10 的复测（Lead 修后我重跑 e13）**：代码里已无 `file://" + ` 拼接（注释里的反例先剥掉再判）、`import pathlib` + `as_uri()` 都在、该套件每个 `subprocess.run(` 都走 `cwd=` 传路径（不把路径拼进命令行），`python3 tests/_test_release_pipeline.py` → `Ran 8 tests / OK` |

**① / ② / ④ 的红绿原始输出（修复前 vs 修复后，同一个 fixture）**

```text
# fixture：只有 scripts/build-fpk.sh + fnos/manifest；祖先提交依次打 v1.6.10 / v1.6.10.1 / v1.6.10.2，
# 最后一个提交打 v1.6.17.1（= CI 当时能看见的 tag 集合）
$ git show 55dfad2:scripts/build-fpk.sh > scripts/build-fpk.sh   # 修复前那一版（467 行）
$ bash scripts/build-fpk.sh --print-version
1.6.10.3                        # ← 与 Release 附件 WorkBuddy2API-Hub_1.6.10.3_all.fpk 的版本逐字符相同

$ cp <工作树>/scripts/build-fpk.sh scripts/build-fpk.sh           # 修复后
$ bash scripts/build-fpk.sh --print-version
1.6.17.1                        # ← 就是 HEAD 上的 tag
```

**④ 实测（Lead 要的数字：dispatch 会不会又出低版本包）**

```text
# /tmp/wbpv/fork.git = 本仓库的 bare 克隆，删到只剩 origin 上那 54 个 tag；再从 file:// 克隆出来，
# 并在 HEAD 上放一个「流水线修复、还没打 tag」的空提交（= workflow_dispatch 的形状）
$ git tag --points-at HEAD                 -> （空）
$ git tag --merged HEAD --list 'v*' | grep -E '^v[0-9]+(\.[0-9]+){2}$' | sort -V | tail -1
v1.6.17
$ bash scripts/build-fpk.sh --print-version
1.6.17.2                        # ← 基线 1.6.17 + 已存在的 v1.6.17.1 → 第四位 2（不是 1.6.10.x）
```

同一 clone 里把 `v1.6.11…v1.6.17` 删掉（模拟「还没跑过 sync 的 fork」）→ `1.6.10.3`（新旧脚本一致）：这就是 R11 登记的残留风险——**dispatch 的版本下限只由「本克隆看得见的 tag」保证**；`fnos/manifest` 的 `version` 是构建时被 `write_manifest` 覆写的占位值（实测 `1.6.10`），所以 Lead 设想的「派生值低于 manifest.version 就拒绝」这条规则抓不到 `1.6.10.3`（`1.6.10.3 > 1.6.10`）。**判定：可接受**，因为 dispatch 构建不发 Release（发 Release 的步骤被 `if: inputs.ref != '' || startsWith(github.ref, 'refs/tags/v')` 门住，只出 artifact），且 origin 现已镜像全部 54 个 tag；若要加强，下限应取「可见的最新四段 release tag」而不是 manifest。

**修复后的端到端形状**：CI 形状的 depth-1 浅克隆（覆盖工作树文件）里 `python3 tests/run_all.py --jobs 4` → `86 passed, 0 failed, 0 skipped`，`total 23.4s`，无任何 `[FAIL]`；本机的 packager 套件与我的套件同轮全绿（§2.1）。CI 的 tag 门禁片段抄进 fixture 实跑：`TAG_REF=v1.6.17.1` → ALLOW（rc 0）；`TAG_REF=v1.6.10.1` → `::error::tag v1.6.10.1 asks for version 1.6.10.1, but this tree derives 1.6.17.1 …` + REFUSED（rc 1）。

**`file://` URL 的跨平台实测（R10 的证据与关闭）**：`file:///tmp/…` rc 0；`file://localhost/tmp/…` rc 0；`file://C:/tmp/…` rc 0（host 段被忽略）；**`file://C:\tmp\x\work`（反向斜杠形状，即 `"file://" + "C:\\Users\\…"` 在 Windows 上会拼出的样子）→ rc 128 `fatal: no path specified; see 'git help pull' for valid url syntax`**——这条反证现在作为常驻断言留在 `e13` 里（「裸拼出来的形状在 git 眼里仍是非法 URL」），所以修复不会悄悄回退。**Lead 已修**：`tests/_test_release_pipeline.py:31` 加 `import pathlib`，`:152` 改成 `source = pathlib.Path(self.work).resolve().as_uri()`；我的 e13 复测断言「代码里无 `file://" + ` 拼接」「有 `import pathlib` + `as_uri()`」「每个 `subprocess.run(` 都用 `cwd=`」三条全 PASS（e13 由 26 条变 30 条，登记项只剩 R11）。全仓 `file://` 现在只有两处：该套件的 `as_uri()` 与注释，以及我的 `tests/_test_phase_e_verify.py` 里的 `pathlib.Path(ROOT).resolve().as_uri()` / e11 的 clone。**附带确认**：`pathlib` 对含空格/非 ASCII 的路径做百分号编码，比裸拼更稳（Lead 实测 `file:///tmp/demo/%E5%B7%A5%E4%BD%9C%20tree`）。

## 3. 缺陷与回归清单

| # | 现象 | 归属 | 状态 |
|---|---|---|---|
| R1 | peer 凭据不可读时 `_gateway_trusted()` 判为受信（fail open）：`uid is None` 不拒，socket 又是 0666 | `wb_proxy.py`（WP-E1 / api-integrator） | **已修并复测**：改为 `uid is None` 直接拒绝 + `peer credentials unavailable` 日志；e7 `10 / 0 / 0` |
| R2 | `_test_release_engineering.py:71` 断言 README 声明的套件数与实际扫盘一致，`README.md` 仍写旧值（当时 `README.md:187` = 「77 个套件：60 个 Python + 17 个 JS」） | `README.md`（WP-E3 / packager） | **已修并复测**：现为「85 个套件：66 个 Python + 19 个 JS」，`python3 tests/_test_release_engineering.py` → `Ran 6 tests` / `OK` / exit 0 |
| R3 | `_test_usage_share.js` `PASS=12 FAIL=3`：三条 summary 断言取到 `null`（测试要裸 `<td data-label="总 Token">`，而汇总行/模型行在该 `<td>` 上加了 `title=` 属性） | `dashboard.html` + 该套件（WP-E2 / ui-panel） | **已修并复测**：`node tests/_test_usage_share.js` → `PASS=15 FAIL=0` |
| R4 | 最终包缺失/漂移（`payload 含 server/wb_export.py` 失败、`包内 server/** 与仓库逐字节一致` 失败、`verify-fpk` 2 条失败、交付文档 5 处 `PENDING_*`） | WP-E3 打包时序 | **已消除**：最终包 412737 字节上（当时）e5 `55 / 0 / 0`、`verify-fpk` `71 passed / 0 failed`、`grep -c PENDING` = 0（e5 现为 `56 / 0 / 0`，见 §2.6） |
| R5 | 无 `AF_UNIX` 的平台上 `e6_device` 直接调 `unix_request()` 而**没有平台守卫** → 抛 `RuntimeError`，整段崩溃（E10 预演子进程 `FAIL=1`，失败名「段 e6_device 自身没有崩溃」） | `tests/_test_phase_e_verify.py`（我自己的写域） | **已修并复测**：`DEVICE_SOCK` 存在性判断之后加 `needs_unix("真机 socket 只读探针")` 早退；E10 子进程 `PASS=159 FAIL=0 SKIP=12`（该快照；task-20 最终复跑为 `PASS=201 FAIL=0 SKIP=13`，父段 `8 / 0 / 0`，见 §2.11）、父段 `6 / 0 / 0` |
| R6 | **提交前置风险**：`wb_export.py`（`wb_proxy.py:54` 顶层 `import wb_export`）、`tests/_test_cockpit_export.py`、`tests/_test_phase_e_ui2.js`、`tests/_test_phase_e_verify.py` 以及整个 `docs/`（4 个文件）都还是 **untracked（`??`）**；若用 `git commit -am` 提交，这些文件不会进 commit | 提交动作（git 由 Lead 执行） | **已闭环**：`55dfad2` 已把这些文件全部纳入版本库（`git ls-files` 命中，工作树只剩本套件本次的修改），e8「包内文件相对 HEAD 无未提交改动」已由 SKIP 转 PASS |
| R7 | **CI 假红（v1.6.17.1 tag CI 三平台全红）**：`actions/checkout` 是 shallow clone（depth 1）→ `merge-base --is-ancestor 9dff35f HEAD` 报 128、annotated tag 对象不可达；runner 非 root → `setpriv` 切 uid 的探针以 127 失败。三条都是**套件的断言假设了本机环境**，不是交付件缺陷（包 job 与 tag 门禁都是绿的） | `tests/_test_phase_e_verify.py`（我自己的写域） | **已修并复算**：`e8` 加 shallow/对象可达性判定后记 SKIP（完整 clone 仍 PASS）、`e2b` 加 `needs_root()`、新增 `e11` 常驻预演；真 shallow clone 里 `run_all --jobs 4` 由 `84 passed, 1 failed` 变为 `85 passed, 0 failed, 0 skipped`（§2.12） |

| R8 | **已发布的包版本号错（task-19）**：tag `v1.6.17.1` 的 CI 构建出的 Release 附件是 `WorkBuddy2API-Hub_1.6.10.3_all.fpk`（411262 B）。根因 `scripts/build-fpk.sh` 的版本推导依赖「本仓库能看到的上游三段 tag」，而 CI 的 shallow clone 里可见的是 `v1.6.10`（origin 当时只补到 `v1.6.17.1`）→ 三段推 `1.6.10`、ordinal 3 → `1.6.10.3`；开发机从 upstream fetch 过 `v1.6.17` → `1.6.17.1`。**同一提交、两个环境、两个版本号** | `scripts/build-fpk.sh` + CI（packager / task-17） | **payload 无问题、版本号待修复**：错包 payload 26 个文件与本机最终包逐文件 md5 相同、也与仓库 HEAD 逐字节相同（§2.13），包内部自洽（`checksum == md5(app.tgz)`）所以完整性门只能抓到 `the package is what this tree builds` 这一条（错包 70 passed / 1 failed）；**无人装过该错包**，可安全重指 tag 让 CI 重建。修复（四段 tag 直接决定版本 + CI 显式传 VERSION 并断言一致）在 task-17 进行中 |

| R9 | R8 的修复（task-17）：版本由「HEAD 上的四段 tag」直接决定，CI 不再让脚本自己猜 | `scripts/build-fpk.sh` + `.github/workflows/{build-fpk,sync-upstream}.yml`（packager） | **已修并由我独立复现红/绿**：同一 fixture 里修复前 `1.6.10.3` → 修复后 `1.6.17.1`（§2.14）；`build-fpk.yml` 用 `TAG_REF` 传 tag、比对 `--print-version` 不一致就 `::error::` + `exit 1`；`sync-upstream.yml` 镜像**每一个**上游三段 tag（先 `ls-remote` 判存在）、且 `git push` 只推单个 ref（无 `--tags`）。CI 形状浅克隆里 `run_all --jobs 4` = `86 passed / 0 failed / 0 skipped` |

| R10 | **跨平台风险**：`tests/_test_release_pipeline.py` 原用 `"file://" + self.work` 拼 clone URL；Windows 上 `self.work` 是 `C:\Users\…\Temp\…`，拼出 `file://C:\Users\…`（反向斜杠）→ 该用例会在 windows-latest 上红 | `tests/_test_release_pipeline.py`（packager；Lead 代为修复） | **已修并复测关闭**：Lead 加 `import pathlib` 并改成 `source = pathlib.Path(self.work).resolve().as_uri()`（`:152`）。我的复测：`python3 tests/_test_release_pipeline.py` → `Ran 8 tests / OK`；e13 三条断言全 PASS（代码无 `file://" + ` 拼接、有 `as_uri()`、每个 `subprocess.run(` 走 `cwd=`），并把「裸拼形状 `file://C:\…` 在 git 眼里非法（rc 128 no path specified）」留作**常驻反证断言**，防止回退 |
| R11 | dispatch 的版本下限只由「看得见的 tag」保证（登记，非缺陷） | `scripts/build-fpk.sh` + CI | **登记为有意口径差异**（§5）：只看得见 `v1.6.10/.1/.2 + v1.6.17.1` 的克隆里 dispatch 派生 `1.6.10.3`；`fnos/manifest` 的 version 是占位值 `1.6.10`（构建时被 `write_manifest` 覆写），所以「派生值 < manifest.version 就拒绝」抓不到它。判定**可接受**（dispatch 不发 Release、origin 已镜像全部 54 个 tag） |
| R12 | **CI 假红（windows-latest 腿唯一一条红，task-20）**：`e11` 的非 root 断言只认「切 uid 需要 root」这一句措辞，而 Windows 既没有 `socket.AF_UNIX` 也没有 `os.geteuid`，`needs_unix()` 先于 `needs_root()` 命中、skip 文案是 AF_UNIX 那条 → 把「按设计跳过」判成红（CI run 37891379131，原文见 §2.12） | `tests/_test_phase_e_verify.py`（我自己的写域） | **已修**：`SKIP_NO_UNIX`/`SKIP_NO_ROOT`/`ENV_SKIP_REASONS` 常量做单一真相源；断言改成「项目名 `e2b peer uid 矩阵` 出现在 SKIP 行」+「理由 ∈ `ENV_SKIP_REASONS`」+「该项目绝不出现在 FAIL 行」，并加两条防空跑断言（段名确实命中、子跑恰好 `PASS=0 FAIL=0 SKIP=1`）——没有弱化成只看 `SKIP=1`。同一份 Windows 形状输出上旧断言 `False` / 新断言 `True`；`e11` 转 `11 / 0 / 0`。**同类审计**（Windows / 无 AF_UNIX 下逐条复核）与「缺 `git` 时 `e8` 崩段」「钉死别人测试条数」两处一并修掉，审计表见 §2.12 |
| R13 | **状态耦合（登记）**：`e5` 原先写死「`verify-fpk` 0 failed」，而 `scripts/verify-fpk.sh` 最后一条是「包 == 本树此刻会构建的东西」——HEAD 一旦越过发布 tag（`9b6c630` 相对 `v1.6.17.1` 在 `adac7eb`），本树派生 `1.6.17.2` 而包是 `1.6.17.1`，这条必然改口（实测 70 passed / 1 failed，唯一红就是它） | `tests/_test_phase_e_verify.py`（我自己的写域） | **已修（状态感知）**：先比「本树派生版本 vs 包 manifest 版本」——相等要求 0 failed；不等要求**恰好 1 条失败且失败名就是 `the package is what this tree builds`** + 通过条数仍成规模 + 退出码 0 或仅因这一条而 1。**不是产品缺陷**（verify-fpk 的行为正确），登记以免下次误判 |
| R14 | **平台耦合（登记）**：`scripts/verify-fpk.sh` 的网关探针是 unix socket 客户端（`:330` / `:379` `socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)` 连 `<payload>/app.sock`；`:126` 断言 `cmd/main` 带 `--unix-socket`；`:416` 断言 socket `0666`），所以没有 `AF_UNIX` 的平台（windows-latest）整个沙箱跑不起来——`e5` 调它会多出三条假红（`the gateway socket is world-writable`、`the gateway signs the NAS user in (exit 1, wanted 0)`、`...and still does when the session header is gone`），实测同一份包在 Windows 形状的进程里 67 passed / 4 failed | `tests/_test_phase_e_verify.py`（我自己的写域） | **已修**：`e5` 在跑沙箱前判 `HAS_UNIX`，没有 `AF_UNIX` 就 `skip`（「verify-fpk 沙箱（网关探针需要 socket.AF_UNIX）」）+ `register("R14 …")`，上面的 tar/命名/manifest/payload/checksum 断言照跑。`scripts/verify-fpk.sh` 本身**不需要改**（它只在本机/NAS 上跑，那里有 `AF_UNIX`），登记以免下次在 Windows 上误判成包缺陷 |

以上共发现 **7 个真实缺陷（R1/R2/R3/R5/R7 在代码与套件侧，R8 在发布流水线侧，R10 在跨平台）+ 1 项登记（R11，非缺陷）**：R1/R2/R3/R5/R7 已修复、我逐条复测转绿；R8 的 payload 经取证无问题、其修复 R9 已由我独立复现红/绿；**R10 已由 Lead 修复并由我复测关闭（e13 三条断言 + 常驻反证）**；R11 是登记项不是缺陷；R4 属「等最终包」的时序红，重建后一次性转绿；**R6 是提交动作上的前置条件，已随 `55dfad2` 闭环**。task-20 又发现并修掉三处**我自己套件**的问题：**R12（windows-latest 腿唯一那条红 = 平台措辞 + 守卫顺序，已修，`e11` → 11/0/0）**、**R13（`e5` 的包版本断言与 HEAD 位置耦合，已改为状态感知，登记为「不是产品缺陷」）**、**R14（`e5` 无条件调 `verify-fpk.sh`，而该沙箱的网关探针依赖 `socket.AF_UNIX`；无 `AF_UNIX` 时改为 SKIP + 登记，`scripts/verify-fpk.sh` 本身不改）**。**当前无遗留未修复缺陷。**

## 4. 未验证与范围外

1. **真机 fnOS 应用中心安装**：安装属设备写操作，本阶段明令不做。包在沙箱里按 appcenter 真实目录形状解包/启动/导入/升级/停止/卸载（`scripts/verify-fpk.sh`，71 条），但真机安装与「应用中心点击升级」未验证。
2. **真机移动端渲染**：断点与 `data-label` 卡片化只做静态/桩 DOM 断言，未在真机窄屏看过。
3. **真实上游行为**：沙箱无外网，所有上游响应都是伪造的；「真账号能否真的领到积分/点亮任务」未验证。
4. **长时间并发与稳定性**：没有做小时级压测（并发队列、多账号轮询、网关长期连接）。
5. **网关 socket 上「应用自身 uid」这一支**：本机父目录不可遍历，无法起一个非 root 面板复现（见 §2.3）；由写者的 root-only 套件在真机等价环境覆盖。
6. **真机上的写操作**：设备现已装 1.6.17.1，只读探针（E6）在真机上验到 `authenticated: true`、`server/**` 与仓库逐字节一致；但安装/重启/升级全部由用户在应用中心完成，**我一次都没写过设备**，所以「升级会不会丢数据、卸载是否干净」仍不在验证范围。
7. **上游 tag 之后的每日同步**：`sync-upstream.yml` 的实际运行（含冲突中止）未在 CI 上观察。
8. **第二波 UI 的运行时行为（`#btnExportCockpit` 点击流）**：我只独立验了服务端契约（§2.10）与「该按钮经 `wbUrl()` 汇聚点、无新增绝对路径调用」（§2.4），按钮的 DOM 交互由写者套件 `tests/_test_phase_e_ui2.js` 覆盖、其文件与仓库逐字节进包（§2.6），我没有在真浏览器里点过。
9. **windows-latest 上的真跑**：本机是 Linux，只能做「整棵树删掉 `socket.AF_UNIX`／`socketserver.Unix*`／`os.geteuid`」的预演（E10，子进程 `PASS=201 FAIL=0 SKIP=13`，父段 8/0/0）与静态检查（`hashlib`、`tempfile`、无 `AF_UNIX` 裸用）；Windows 实际的路径分隔符、`tar.exe`/`bash` 差异、node 版本等，要等 CI 结果确认。E10 已经把这变成常驻断言（且把形状沿 `PYTHONPATH` 的 `sitecustomize` 传给孙进程，断言孙辈解释器为 `False False`）；`e11` 另把 CI 的 **shallow clone + 非 root** 形状也在本机做成常驻断言（`git clone --depth 1 file://…` 后只跑 `e8`/`e2b`/`e11`），但**没有真的在 Windows runner 上跑过**。task-20 修掉的 R12（平台措辞 + 守卫顺序）同样只能用同一份 Windows 形状输出复算（旧断言 `False` / 新断言 `True`），**真 Windows 以 CI 的 windows-latest 作业为准**。R14 提醒的边界同样只能靠这种预演发现：`e5` 在无 `AF_UNIX` 时已改为跳过 `verify-fpk.sh` 沙箱，所以 `scripts/verify-fpk.sh` 的网关探针**在真 Windows 上从未被本套件要求跑通**（它本来也只在本机/NAS 上跑）。
10. **错包是否被任何人装过**：我只能证明 GitHub 侧 `download_count = 0`、且设备 `/vol1/@appcenter/workbuddy2api/server/**` 与仓库（= 错包 payload）逐字节一致，因此**即使有人装了错包，跑着的也是同一份代码**；但「有没有人装过」这件事我无法从任何一边验证，只能采信 Lead 的说明。另：重指 tag 后 Release 资产会被重建，我**没有对 GitHub Release 做任何写操作**（全程只读下载），这一步由 Lead 执行。
11. **R10 在真 Windows 上的表现**：我在 Linux 上用 Windows 会拼出的同一串 URL（`file://C:\…`）实测 git 报 rc 128，据此判定原写法有跨平台风险；Lead 已改成 `pathlib.Path(...).as_uri()` 并复测关闭（§2.14）。但**没有在 Windows runner 上跑过**修正后的套件，且若该 runner 的 `bash` 不在 PATH 上，那 5 条行为用例会走 `skipTest`（rc 0）而不是真跑。以 CI 的 windows-latest 作业为准。

## 5. 有意口径差异与登记项（不判 FAIL）

1. **网关 socket 上 `/v1` 的 API key 被一并免掉**（Lead 裁决：保持现状，这是有意设计）。
   事实：`_key_ok()` 首行是 `_panel_ok()`，而 WP-E1 把 `_panel_ok()` 从「socket 且带 `X-Trim-Username` 头」放宽为「socket 且 peer 校验通过」，于是 uid 0 或应用自身 uid 连 socket 打 `/v1` 不带头也 `200`（实测）；TCP 侧不带头 `401`、带正确 key `200`。
   结论一句话：**API key 仍然保护 TCP 入口；网关 socket 上的面板会话同时放开 `/v1`（`_key_ok()` 首行 `_panel_ok()` 的直接后果），属有意设计。**
   理由（三条）：① TCP（局域网直连 8788）仍强制 API key，外部调用者的控制点没动；② socket 上「免 key」的实际可达集 = `uid 0`（网关）或应用自身 uid，前者是根、后者本来就能读写 `/vol1/@appdata/workbuddy2api/**`（含 settings 与账号），没有新增权限面，陌生本地 uid 仍 401；③ 需求就是「网关前门可信、不要重复验证」，把 key 压回网关路径会制造第二种重复验证，与需求相反。
2. **导出路由没有「兄弟模块缺失就软失败」的分支**：`wb_proxy.py:54` 是顶层 `import wb_export`，所以 `wb_export.py` 若不在包里，进程会在启动时**直接起不来**（响亮的失败），而不是让 `POST /accounts/export` 悄悄 503。取舍登记：不另设运行期兜底，改由打包断言保证 —— 我已把 `wb_export.py` 加进 `PKG_MODULES` 并把「包内 `server/**` 与仓库逐字节一致」作为硬断言（§2.6）。
3. **cockpit 行的 realm 只能靠 `domain` 保真**：cockpit 格式没有 realm 字段，所以导出侧会把与 realm 矛盾的旧 `domain` 改写成该 realm 的裸主机，并在服务端日志点名（`cockpit export: N account(s) had a domain outside realm …`），不静默改写；反过来，导入侧一律按 `domain` 推断 realm。这是 Go 面板 `importCockpit` 的既有规则，不是我们的自由度。
4. **失败行仍计入 `credit`/tokens**（只不算 `requests`）——上游 `feed()` 的既有口径，非本阶段引入。
5. **R11：dispatch 的版本下限只由「看得见的 tag」保证**（task-18 登记，判定可接受）。
   事实：只看得见 `v1.6.10`/`.1`/`.2` + `v1.6.17.1` 的克隆里，`workflow_dispatch`（HEAD 无 tag）会派生 `1.6.10.3`；`fnos/manifest` 的 `version` 是构建时被 `write_manifest` 覆写的占位值（实测 `1.6.10`），所以「派生值低于 `manifest.version` 就拒绝」这条规则抓不到它（`1.6.10.3 > 1.6.10`）；真正能作下限的是「本克隆可见的最新四段 release tag」（`v1.6.17.1`）。
   判定**可接受**的理由：① dispatch 构建**不发 Release** —— 发 Release 的步骤被 `if: inputs.ref != '' || startsWith(github.ref, 'refs/tags/v')` 门住，只出 artifact；② 修复 R9 之后，`push tag` 路径由 tag 自身决定版本，不受可见 tag 集合影响；③ origin 现已镜像全部 54 个 tag（`git ls-remote --tags origin` 与本机集合逐项相同），tag 饥饿的克隆只可能是「还没跑过 sync 的 fork」。若要加强，把下限从 `fnos/manifest` 换成「可见的最新四段 release tag」。

## 6. 交付物与指纹

- 报告：本文档（`docs/phase-e-verify.md`，不在 fpk payload 内）。
- 验证套件：`tests/_test_phase_e_verify.py`（2491 行，129406 字节，sha256 `7ca9f61cb75e615697b7ce0a18ad0fe3e65da9ab81603ba1de7709fcd09c74ff`）。**14 段**：`e1_suites` / `e2_gateway` / `e2_peer_matrix` / `e3_mount` / `e4_credit` / `e5_package` / `e6_device` / `e7_hardening` / `e8_delivery` / `e9_cockpit_export` / `e10_platform_sim` / `e11_ci_rehearsal` / `e12_released_pkg` / `e13_release_pipeline`；支持段名子串过滤，环境变量 `WB_PHASE_E_STRICT`、`WB_PKG`、`WB_DASHBOARD_PATH`、`WB_GO_IMPORT_GO`、`WB_COCKPIT_SAMPLE`、`WB_WRONG_PKG`，并可在无 `socket.AF_UNIX` 的平台（段记 SKIP）与 shallow clone / 非 root runner 上整跑；`e12` 在没有已发布错包副本时记 SKIP（CI 走这条）；`e13` 的所有 repo fixture 都在 `tempfile` 里建（不写工作树、不需要网络）。task-20 的改动（两批）：第一批 = `HAS_GIT` + `SKIP_NO_UNIX`/`SKIP_NO_ROOT`/`ENV_SKIP_REASONS` 常量、`e11` uid 断言重写（R12）、`e5` 包版本断言状态感知（R13）、`e8`/`e13` 缺工具走 SKIP、三处「钉别人测试条数」放松；第二批 = `e10` 改成整棵树 Windows 形状（`PLATFORM_SIM_CUSTOMIZE` 走 `PYTHONPATH`）+ 孙辈解释器形状断言、`e5` 在无 `AF_UNIX` 时跳过 `verify-fpk.sh` 沙箱（R14）。全套 **PASS=266 FAIL=0 SKIP=2**（分段：e1 10 / e2 14 / e2b 4-0-1 / e3 32 / e4 26 / e5 56 / e6 3 / e7 10 / e8 14-0-1 / e9 35 / e10 8 / e11 11 / e12 12 / e13 31）。改动行号（`git diff -U0`，新文件行号）：`71`（HAS_GIT）、`92-103`（共用理由常量）、`112` / `125`（needs_unix/needs_root 用常量）、`1153` / `1157`（e5 取 `pkg_version`）、`1250-1279`（e5 verify-fpk：无 `AF_UNIX` 先 SKIP + R14 登记）、`1284-1313`（e5 verify-fpk 状态感知判定）、`1370-1378`（e8 缺 git gate）、`1748-1800`（`PLATFORM_SIM_CUSTOMIZE`）、`1802-1860`（e10 的 `PYTHONPATH` 传递 + 孙辈形状断言）、`1972-2002`（e11 uid 断言 + 两条防空跑）、`2004-2022`（`register("R12 …")`）、`2275-2279`（e13 bash/git 守卫）、`2376-2380` / `2385-2396` / `2416-2418`（三处条数断言放松）。
- 本报告：`docs/phase-e-verify.md`（503 行）。报告自身的 sha256 只在最后一次编辑之后才定得下来，所以写在这里会立刻失效——我在交给 Lead 的收口消息里给出最终 sha256（写本行不改行数，故行数在定稿前就已稳定）。
- 最终包指纹（我独立复算，未改动）：`dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk`，412737 字节，sha256 `5edc6c972e206181b4efeb49fd1c804a5ccb232b6c63a0ce5ed76498d64bbc27`，md5 `d45e598420425a9f992895445f3ef1ff`，manifest `checksum`（app.tgz md5）`7d66e48d4d7738192c0cf7499eb06666`。
- 已发布错包指纹（只读下载物，`/tmp/wb-wrongpkg/WorkBuddy2API-Hub_1.6.10.3_all.fpk`）：411262 字节，sha256 `c5b7da5fe4f35a5c8ef3327cb192227f9d86a6b86ed40744586a0d3945e25351`，md5 `402ddfd3ebaa9a7f58ed89babe9a74de`，manifest `version = 1.6.10.3` / `checksum = 36039fe3d92f180b1a5e96256fc974be`（§2.13）。
- 本条验证结论对应的工作树：task-18 那一刻是 HEAD `55dfad2`（tag `v1.6.17.1` 已打，`cat-file -t` = `tag`）；task-20 复跑时 HEAD 已是 `9b6c630`（`v1.6.17.1` 在 `adac7eb` 上，即 HEAD 越过该 tag 一个提交）。本轮我的改动只有 `tests/_test_phase_e_verify.py` 与 `docs/phase-e-verify.md` 两个文件，仍未 `git commit`（git 由 Lead 做）；task-20 复跑时 `git status --porcelain` 只剩 `M docs/phase-e-release-notes.md`、`M docs/phase-e-verify.md`、`M tests/_test_phase_e_verify.py`（packager 的 `scripts/**`、`.github/**`、`README.md`、`tests/_test_release_pipeline.py` 均已提交；树里 86 个套件，README 已同步为「86 个套件：67 个 Python + 19 个 JS」）。**包内文件一个字节未动**：412737 字节的包仍然有效、无需重打包；`verify-fpk.sh` 对它当前报 `70 passed / 1 failed`（唯一红 `the package is what this tree builds`，因为本树此刻派生 `1.6.17.2`，见 §2.6 与 R13）——HEAD 回到发布 tag 时同一命令仍是 71 passed / 0 failed。

