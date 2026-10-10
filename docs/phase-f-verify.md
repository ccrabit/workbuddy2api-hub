# Phase F 独立终验报告（WP-F5 / task-25）

> 验证者：`verifier`（独立于全部写者）。写域只有本文件与 `tests/_test_phase_e_verify.py`。
> 本阶段目标（`docs/phase-f-plan.md`）：把上游 v1.6.19 并入飞牛 fork、修好「自动并入没生效」、
> 准备 FnDepot 上架材料、把版本号与上游三段号对齐（`1.6.19`）；**只出本地测试包**，不 push、不打 tag、
> 不发 Release、不动设备。用户原话见 `docs/phase-f-delivery.md:3`（m05838）。

## §0 结论摘要（一眼看全）

> 本版是 **task-27（WP-F9）** 收口版：把 Phase F 的交付纪律从「本地构建 + 本机数值」改成**状态感知**——
> 包对着**构建它的那个 tag 提交**验，设备对着**它自己那一版**包验，合并事实对着**HEAD 历史里最近一次合并**验；
> 环境给不出答案时 `gate()`/SKIP 并写明理由（**绝不 FAIL**），能给答案的地方不许退化成 SKIP。
> 三种环境（开发树 / depth-1 浅克隆 / Windows 形状）都必须 FAIL=0。
> **task-29（WP-F10）** 又修掉 Windows 腿唯一一条真红：CRLF 检出 vs 套件用文本模式读源文件（R25，见 §2.14）。

| 项 | 判定 | 通过 / 失败 / 跳过 | 证据 |
|---|---|---|---|
| 合并正确性（动态解析最近一次合并 / 上游文件未动 / 飞牛层在位） | **通过** | 15 / 0 / 0 | §2.1、E16 |
| 版本与 tag 契约（`fnos-X.Y.Z`、删四段发布号、不镜像上游 tag） | **通过** | 37 / 0 / 0 | §2.2、E13 |
| 自动并入工作流（三条 cron、冲突分支、去镜像、exit 1） | **通过（静态+行为级）** | 含在 E13 内 | §2.3 |
| FnDepot 源 `fnpack.json`（中心校验器 + 结构 + 与**已发布资产**对齐） | **通过** | 31 / 0 / 0 | §2.4、E14、R16 |
| 免密口径（socket peer 即登录 / TCP 伪造仍被拒） | **通过** | 14+4+10 / 0 / 1 | §2.5、E2/E2b/E7 |
| 挂载前缀契约（`<base href>` 仅挂载态 / 直连逐字节） | **通过** | 33 / 0 / 0 | §2.6、E3 |
| 每 M tokens 积分（后端 credit 累加 / 界面除零） | **通过** | 26 / 0 / 0 | §2.7、E4 |
| 包与交付纪律（包↔tag 提交 / 双 `verify-fpk` / 设备分状态） | **通过** | 60+15+13 / 0 / 2 | §2.8、E5/E8/E12 |
| 全量套件 `run_all.py --jobs 4` | **通过** | 122 / 0 / 0 | §2.9、E1 |
| 平台形状（无 AF_UNIX / shallow clone / 非 root） | **通过** | 8+11 / 0 / 0 | §2.10、E10/E11 |
| 交付说明与方案书一致性（F6 交叉核对，含设备状态带牙断言） | **通过** | 22 / 0 / 0 | §2.11、E15、R17/R23 |
| **E1 去重**（被 `run_all.py` 拉起时不重复跑一遍完整 run_all，task-30/R26） | **通过** | 本套件墙钟 49.6s → 26.8s，两轮 122/0/0 | §2.15 |
| **三环境 FAIL=0**（开发树 / depth-1 浅克隆 / Windows 形状） | **通过** | 352/0/2 · 253/0/15 · 8/0/0 | §2.12 |
| **敏感性证明**（改坏输入必红） | **通过**（4 条） | 见 §2.13 | §2.13 |

- **本套件合计（开发树）PASS=352 / FAIL=0 / SKIP=2**，exit 0（17 段；日志 `/tmp/wb-f10-full.log`，81.6s）。
  Lead 回填并提交交付说明后全绿：`351 / 0 / 3` → `352 / 0 / 2`（原来那条 `M scripts/build-fpk.sh` 引起的「包内文件有未提交改动」
  gate 现在真跑并 PASS）；回填前是 `340 / 6 / 3`（`/tmp/wb-f9-full2.log`，6 条红 = R17/R23 四条 + 其派生两条）。
  剩下 2 条 SKIP 是环境：① 以 uid 65534 起面板（沙箱父目录 `drwx------` 不可遍历）；② HEAD 上还没有 `fnos-*` tag。
- **depth-1 浅克隆（CI 形状）**：用**已提交**的树跑 = `PASS=249 / FAIL=4 / SKIP=15`（唯一根因是提交里的交付说明还写着
  设备 1.6.17.1，另 3 条是派生）——**这是文档没提交，不是套件问题**；把**回填后**的交付说明放进同一个克隆再跑 =
  **`PASS=253 / FAIL=0 / SKIP=15`，exit 0**（`/tmp/wb-f9-ci3b.log`）。⇒ Lead 提交回填后 CI 即绿。
- `python3 tests/run_all.py --jobs 4` → **122 passed, 0 failed, 0 skipped**（83.4s，exit 0；`/tmp/wb-f10-runall.log`）。
- `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.19_all.fpk` → 工作树上 **69 passed, 1 failed**
  （唯一失败 `every packaged file is byte-identical to the tree`，因为工作树已前移 24 个提交）；
  **在 tag 提交的检出上同一条命令 71 passed / 0 failed**（E5 实测）。「同一条命令在不同环境给不同数字」现在是
  套件里的显式断言（§2.8），不是含糊话。
- 3 条 SKIP（开发树）：① uid 65534 探针要能遍历父目录（沙箱里是 `drwx------`）；② HEAD 上没有 `fnos-*` tag
  （本阶段不打 tag）；③ 包内文件相对 HEAD 有未提交改动（`M scripts/build-fpk.sh`，packager 在途的 R19/R21/R22 改动）。
- **task-30（WP-F11）去重 e1 的嵌套 run_all**：套件被 `run_all.py` 拉起时（`WB_RUN_ALL=1`）不再自己再跑一遍
  完整 run_all，只冒烟一个已知良好的套件（`_test_lifecycle.py`，2.1s）。冻结克隆里 A/B 实测本套件墙钟
  **49.6s → 26.8s**，两轮都 `122 passed / 0 failed / 0 skipped`；独立运行时行为一字不变（仍完整嵌套，42.3s /
  10 条断言）。因为 e1 在外层 run_all 内只留 2 条断言，套件在外层 run_all 内是 `344 / 0 / 2`（独立运行仍是
  `352 / 0 / 2`）。详见 §2.15、R26。
- **一句话结论**：Phase F 的六件事在**契约级与行为级**都已成立 —— 三环境 FAIL=0、`run_all --jobs 4` 122/0/0、
  `verify-fpk` 在 tag 检出 71/0、设备侧只读复核通过，可以拿这个包上真机测；剩下的不是代码问题，而是
  **只有用户在真实环境里才能做完**的外部动作（应用中心里安装/复装、真实 GitHub 上跑一次自动并入、push + 打 tag + 发 Release）
  与几处**交付/上架前的清理与登记**（R18 可执行位、R15 上架口径、R21/R22/R24，见 §3 清单）。


## §1 复现入口

```bash
# 全套（约 60s；CI 上跑的就是这一条）
python3 tests/run_all.py --jobs 4

# 本套件（17 段，可用子串只跑某段）
python3 -u tests/_test_phase_e_verify.py                 # 开发树：PASS=351 FAIL=0 SKIP=3
python3 -u tests/_test_phase_e_verify.py e5              # 60/0/0  包 ↔ tag 提交 + 双 verify-fpk
python3 -u tests/_test_phase_e_verify.py e13             # 37/0/0  版本与 tag 契约
python3 -u tests/_test_phase_e_verify.py e14             # 31/0/0  FnDepot 源 + ls-remote 对抗 + 已发布资产
python3 -u tests/_test_phase_e_verify.py e15             # 22/0/0  交付说明一致性（含设备状态带牙断言）
python3 -u tests/_test_phase_e_verify.py e16             # 15/0/0  合并正确性审计

# 三环境（task-27 的硬要求：三处都必须 FAIL=0）
python3 tests/run_all.py --jobs 4                        # (a) 开发树
git clone --quiet --depth 1 file://$PWD /tmp/wb-f9-ci    # (b) CI 形状：shallow clone
cp tests/_test_phase_e_verify.py /tmp/wb-f9-ci/tests/
(cd /tmp/wb-f9-ci && PYTHONPATH=/tmp/wb-f9-ci python3 -u tests/_test_phase_e_verify.py)   # 已提交树 249/4/15 → 交付说明回填后 253/0/15
python3 -u tests/_test_phase_e_verify.py e10 e11         # (c) Windows 形状（无 AF_UNIX / 无 geteuid / 非 root）

# 包（本阶段我只读产物；构建是 packager/Lead 的事）
bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.19_all.fpk   # 工作树 69/1；tag 检出 71/0（E5 实测）
```

环境旋钮（都可选）：`WB_PHASE_E_STRICT=1`（「还没落地」从 SKIP 变硬 FAIL）、`WB_PKG`、`WB_PKG_VERSION`、
`WB_PHASE_E_PKG`（设备比对锚包）、`WB_WRONG_PKG`（错包副本）、`WB_PUBLISHED_ASSET`（已发布资产副本）、
`WB_RELEASE_PIPELINE_SUITE`（packager 套件路径，做结构门敏感性证明用）、`WB_MERGE_COMMIT`（历史断言的目标提交）、
`WB_DASHBOARD_PATH`（冻结版看板）。段落：`e1`…`e16`（`e8` 交付纪律、`e12` 错包反向取证、`e13` 版本与 tag 契约、
`e14` FnDepot 源、`e15` 交付说明一致性、`e16` 合并正确性审计）。


## §2 逐项结论

### 2.1 合并正确性（E16 = 15/0/0；合并对象由 git 动态解析，不再写死）

```
$ git rev-list --parents -n1 HEAD
39a16f6adda42e52b118086c7fa1f1afa9df5682 3d541733a4602688f2499e4434208e9d9dd174a0 5b5b5c1ccea5370026c6072f5fc7d813aa9a5e11
$ git merge-base --is-ancestor upstream/main HEAD ; echo $?
0
$ git log -1 --format=%s
Merge upstream/main (5b5b5c1) into the fnOS fork
```

- 断言**不写死 SHA**：从 `HEAD` 读父，要求「HEAD 是合并提交（恰好两个父）」+「第二父 == `upstream/main`」+
  「`upstream/main` 是 HEAD 的祖先」，浅克隆里查不到历史对象就 `gate` 成 SKIP（绝不由「查不到」变成红）。
  当前实测 = `39a16f6`，父 `3d54173`（我们上一版发布提交）与 `5b5b5c1`（= `upstream/main`，Phase F 那次合并的
  `e6902e2` 的后继）。Phase F 当时的合并提交是 `db9e58b`（父 `316eb8f` + `e6902e2`）——只作历史对照，套件不依赖它。
- 飞牛层与 FnDepot 件全部在位（`fnos/manifest`、`scripts/build-fpk.sh`、`scripts/verify-fpk.sh`、
  `.github/workflows/{build-fpk,sync-upstream}.yml`、`wb_export.py`、`fnpack.json`、`fndepot/{ICON.PNG,README.md}`）。
- 上游新增文件也在（`tests/_test_dashboard_cache_headers.py`、`wb_pricing.py`、`wb_modelsdev.py`、`wb_probes.py`、`wb_identity.py`、
  `.github/workflows/release.yml`）。
- **acceptance §5「不改上游 `release.yml`」实测成立**：`git diff upstream/main HEAD -- .github/workflows/release.yml` 为空。
- 上游 workflow 里**只有 `tests.yml` 被改了内容**（唯一有记录的例外：`tags: ["v*"]` → `tags: ["v*", "fnos-*"]`，
  并给版本断言加 `fnos-*` 分支）。`build-fpk.yml` / `sync-upstream.yml` 是纯新增（上游没有这两个文件）。
- 合并没有留下三方冲突标记：`git grep -n -E '^<<<<<<< '` / `'^>>>>>>> '` / `'^=======$'` 三个模式在全仓**都没有命中**
  （当前合并提交的标题 = `Merge upstream/main (5b5b5c1) into the fnOS fork`）。
- 登记项：**R18**（见 §3）。

### 2.2 版本与 tag 契约（E13 = 37/0/0）

静态面：`scripts/build-fpk.sh` 里 `head_release_tag` / `last_release_version` / `upstream_version` / `manifest_version` /
`derive_version` 五个函数齐全；**去掉注释行后**代码里不再出现 `next_release_ordinal`、也不再有四段版本正则；
回落链（`fnos-*` → 上游 `v*` → `fnos/manifest`）与 `-alpha<ahead>` 后缀都在；`upstream_version()` 用 `--refs`
（不镜像上游 tag）。`sync-upstream.yml` 里没有任何镜像上游 tag 的步骤，只推 `refs/tags/fnos-${version}`，
推之前先 `ls-remote --exit-code` 判重，冲突路径写 summary + 推 `sync-conflict/<UTC 日期>` 分支 + `git merge --abort` + `exit 1`，
`cron` 三条且保留 `workflow_dispatch`。`build-fpk.yml` 有 `--print-version` 门与 `::error::`/`exit 1`，
`fetch-depth: 0`。`tests.yml` 的 tag 门同时认 `fnos-*` 与历史四段 tag，`*-ci` 彩排豁免。

行为面（在临时 git 仓库里真跑 `bash scripts/build-fpk.sh --print-version`）：

| 场景 | 期望 | 实测 |
|---|---|---|
| HEAD 挂 `fnos-1.6.19` | `1.6.19` | `1.6.19` |
| 同一提交 `--alpha` | `1.6.19-alpha0` | `1.6.19-alpha0` |
| HEAD 另有干扰 tag `v9.9.9.9` | `1.6.19` | `1.6.19` |
| dispatch（HEAD 无 tag，能看见我们的历史 tag + 上游 tag） | `1.6.19-alpha1`（必带 `-alpha`） | `1.6.19-alpha1` |
| 无任何 tag、无 upstream remote | `1.6.10-alpha0` | `1.6.10-alpha0` |
| 修复前的脚本（`55dfad2:scripts/build-fpk.sh`）在 CI 当时的 tag 集合下 | `1.6.10.3`（重现 CI 红） | `1.6.10.3` |
| 现行脚本在同一集合下 | `1.6.10-alpha3`（带 alpha，不是发布号） | `1.6.10-alpha3` |

- 本树当前（HEAD 无 tag）实测 `bash scripts/build-fpk.sh --print-version` → **`1.6.19-alpha44`**，
  与交付说明 §2.4 写的值一致（44 = 相对上游 `v1.6.19` 的提交数）。
- packager 自己的套件 `tests/_test_release_pipeline.py` 我独立重跑：`Ran 19 tests in 1.779s` / `OK`（rc=0）；
  并静态核对它没有把修复「改成自证」（仍用 `revert_the_namespace()` 把命名空间退回四段来跑红半，
  Windows URL 形状走 `pathlib...as_uri()`，`subprocess.run(` 与 `cwd=` 计数相等）。

### 2.3 自动并入工作流（静态 + 行为级通过；**真实 GitHub 未验证**）

- 「没生效」的根因（三条 cron 写的是 UTC 而 GitHub 按 UTC 跑 ⇒ 实际落在北京 11:17）与修复（三条 cron
  `17 3`/`23 9`/`41 15` UTC + 冲突分支 + 去掉镜像上游 tag）我逐条在 `sync-upstream.yml` 里读到了对应代码，见 §2.2。
- 每一次失败都是**真冲突**（不是假红）：`git merge` 返回非 0 才进冲突分支，未冲突时走到 `merged=false; exit 0`。
- 如实说明：这套修复**还没有在真实 GitHub 上跑过一次**（`docs/phase-f-delivery.md` §2.2 自己也这么写）。
  我只能证明「代码形状与行为符合方案」，不能证明「下一次 cron 会绿」——列为 §4 未验证第 1 条。

### 2.4 FnDepot 源（E14 = 31/0/0，含 2 条登记）

- 结构：`schema_version` 是字符串 `"2"`；`source_info.name/author` 非空；`apps` 的键**恰好等于**
  `fnos/manifest` 的 `appname`（`workbuddy2api`，规范硬要求「应用键名与 FPK manifest 的 appname 完全一致」）；
  `display_name` 与 manifest 一致；`platform=["all"]`；`run_as="package"`、`install_type=""`；`is_docker` 是真 bool；
  `categories` 2 个；`icon_url`/`readme_url` 是**相对 URL**，按 README §8 合法（我按主 JSON 所在目录解析成
  `fndepot/ICON.PNG` / `fndepot/README.md` 并断言存在，**不当缺陷**）；ICON.PNG 是真 PNG（magic + 7666 字节 < 500KB）。
- 版本与下载地址：`releases` 只有一个版本键且 == `1.6.19`；`packages.all.download_url` 是 https 且形如
  `.../releases/download/fnos-1.6.19/WorkBuddy2API-Hub_1.6.19_all.fpk`。
- **用中心仓库自己的校验器独立跑过**（`/tmp/fndepot/generate_sources.py`，在子进程里 `GITHUB_TOKEN=dummy`，
  因为该模块缺 token 会在 import 时就 `exit(1)`）：
  `parse_and_fingerprint` → `True`、names `['workbuddy2api']`、sigs `['workbuddy2api|1.6.19']`、`v2`；
  `validate_v2_app('workbuddy2api')` → `True`；`is_forbidden_identity` 对 author/maintainer/distributor 全 `False`。
- 我另外独立重跑了 credits-engine 的 `tests/_test_fndepot_source.py`（388 行）：rc=0、`FAIL=0`、`PASS>=30`。
- **R16（已关闭）**：`fnpack.json` 的 `size`/`sha256` 曾是占位（`0` / 64 个 `0`），现已按**已发布资产**回填为
  `577842` / `3d341706c6fec4f7620ad75bba49fd3347b1b7c32c41d51cd8a4238c52f8a34c`，`download_url` 指向 Release
  `fnos-1.6.19` 的资产（release id `408987082`），E14 用 Releases API 独立复核过。
  **注意**：不能回填成本机 dist 新包的 `577330` / `71edade7…`（载荷相同、外壳不同）。
- **R15（登记，结论更正）**：方案书/交付说明里「现有仓库本身就够格被召回」的**方向对，但在 push 之前不成立**，
  详见 §3。

### 2.5 免密口径（E2 = 14/0/0，E2b = 4/0/1，E7 = 10/0/0）

- 真 unix socket、**不带** `X-Trim-Username` 打 `<base>/panel/status` → `authenticated:true` + `via_gateway:true`；
  TCP 直连即便伪造成 `X-Trim-Username: root` 仍然要密码（`authenticated:false`）；带上头时页面显示该用户名。
- peer 矩阵：uid 0 放行；陌生 uid（`setpriv` 切到 65534，超时 300s）连 socket → `/accounts` 401 且
  `authenticated:false`；服务端日志出现 `gateway: peer uid …` 轨迹。**peer 凭据读不到时是 fail closed**
  （`connection=None`、或既无 peer 凭据又无头 → 一律 `False`，日志 `sign-on ignored: peer credentials unavailable`）。
- 加固面：unix socket 权限是 `0666`（所以 peer 校验是唯一防线，这条我登记过）；`panel_password_required` 仍为 true；
  无论 socket 还是 TCP，`/panel/*` 仍受面板会话保护。
- SKIP 那 1 条：以 uid 65534 起一个完整面板需要能遍历父目录，沙箱里 `drwx------/d000` ⇒ 只跑了 peer 矩阵那半。
- 有意口径差异：**网关 socket 上的 `/v1` 也被免了 API key**（`_key_ok()` 首行就是 `_panel_ok()`）——Lead 已裁决
  「保持现状、写进交付说明」，理由与原文见 §5。

### 2.6 挂载前缀契约（E3 = 33/0/0）

- 挂载态（`GET /app/workbuddy2api/` 走 socket）：HTML 里有 `<base href="/app/workbuddy2api/">`，
  且 `window.__WB_BASE__="/app/workbuddy2api"` / `__WB_VIA_GATEWAY__=true` 都在（`<base href>` 断言用真标签正则，
  不会被注释里的字样误判）。
- **直连态（acceptance §2.2.1 的契约变更）**：响应体**逐字节等于** `dashboard.html` 只做语言替换后的内容——
  断言 `"<script>window.__WB_BASE__=" not in body`、`__WB_VIA_GATEWAY__=`/`__WB_GATEWAY_USER__=` 不在体里，
  再做整串相等比较。ETag 第 4 分量覆盖 `base_path|via_gateway|gateway_user`（否则第二个 NAS 用户会 304 拿到别人的页面）。
- 运行时 stub-DOM：把 `WB_BASE` 与 `wbUrl()` 抽出来用 node 求值——挂载态所有站内路径都带前缀，
  `https://`/`//` 外域原样，直连态原样；`fetch()` 首参一律是 `wbUrl(...)`，没有裸 `XMLHttpRequest`/`sendBeacon` 漏网。
- 前缀边界：带尾斜杠 `/app/workbuddy2api/` 与另一前缀 `/app/wb-alt` 都能起，注入的 `<base href>` 用归一化后的前缀；
  伪造前缀 `/app/other/panel/status` 不会被当面板路由；socket 上不带前缀直呼 `/panel/status` 仍 200。

### 2.7 每 M tokens 积分（E4 = 26/0/0）

- 后端：用上游新 API `_new_analytics_maps()` + `_fold_usage_analytics(row, realm, maps, half)` 逐行折叠，
  断言 `credit` 累加与 `window`/`all_time` 两个 half 的分桶都对。
- 界面：`creditPerM(credit, tokens)` 与 `fmtPerM()` 用 node 求值 12 组边界输入（0/None/`"abc"`/-5/1e9/字符串数字/1e12/1/3…），
  断言不外泄 `NaN`/`Infinity`/`undefined`；0 token → `—`，0 积分 → `0`，42 积分 / 2M tokens → 21。
- 表头 `每 M tokens 积分` 与汇总行都在（与 §2.11 的交付说明一致性一起看）。

### 2.8 包与交付纪律（E5 = 60/0/0，E8 = 15/0/2，E12 = 13/0/0）

```
$ sha256sum dist/WorkBuddy2API-Hub_1.6.19_all.fpk   # 与旁置 .sha256 一致
71edade7833191f189ade8d1ca1938faa12db9d0cd90ec316c3596a86c11ac98  WorkBuddy2API-Hub_1.6.19_all.fpk
$ stat -c %s dist/WorkBuddy2API-Hub_1.6.19_all.fpk
577330
$ bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.19_all.fpk | tail -2
==> 69 passed, 1 failed
    the package behaves; only a real NAS can test the app store itself.
```

- **包必须对着「构建它的那个提交」验**（task-27 的核心改动）：由 `fnos-1.6.19` tag 解析出提交 `26c2bcc`
  （HEAD 已前移 24 个提交），再用 `git show 26c2bcc:<path>` 与包 payload 逐字节比 —— 断言把 `app.tgz` 里枚举出的
  **每个文件**都比一遍（不是抽查），payload 共 **40 个文件（35 server + 3 ui + 2 config）**、**0 个 `__pycache__`/`*.pyc`**
  （R19 已修）；`ui/images/{64,256}.png` 对应仓库的 `fnos/ICON.PNG`/`ICON_256.PNG`。
- manifest：`appname=workbuddy2api`、`version=1.6.19`、`platform=all`、`service_port=8788`、
  `checksum = 27d6795c7ba2a4db89f1e82fabef6ef0` == md5(包内 `app.tgz`)；包内不含
  `accounts/`/`usage/`/`docs/`/`tests/`/`dist/`/`build/`/`scripts/`/`fnos/`/`.git/`。
- `verify-fpk.sh` 我在**两个环境**都独立跑过（不是采信 packager 的数字）：**发布 tag 的干净检出**上
  `71 passed / 0 failed`；**前移了 24 个提交的工作树**上 `69 passed / 1 failed`（唯一失败
  `every packaged file is byte-identical to the tree`）。同一命令两个数字都不是产品缺陷，见 §5.2。
- **与已发布资产的关系**：`fnos-1.6.19` Release 的资产是 577842 B / `3d341706…`，其 payload 与本机新包**逐文件相同**
  （E14 用 Releases API 独立复核；登记项「本机包比已发布资产多出的文件」实测 = 0 个）。
- 设备侧（只读、**状态感知**）：锚是**设备自报的 manifest 版本**（实测 `1.6.19`），不是本套件挑的版本 ——
  实测设备 `server/**` 的 **35 个源文件**与该版本包 payload 逐字节一致（**单向包含**：允许设备多出 `__pycache__`/`*.pyc`，
  实测 23 个 = 3 个 R19 痕迹 + 20 个运行时生成），设备 `wb_proxy.py` 的 banner 与包 payload 的相同，
  设备版本 `1.6.19` 不新于本仓最后一个发布版本，数据目录只读检查通过。**我没有对设备做任何写操作**，
  也**不用 mtime 判设备状态**（服务在跑、目录会一直被写）。
- 设备 provenance：设备 manifest `checksum = be761a0f2715cd903edcf8e88d4198f9` 在 `dist/` 里**没有**对应产物
  （现存 1.6.17.1 / 1.6.19 / 1.6.10.13 / 1.6.10.2 的 checksum 都对不上）⇒ 设备装的是**已被重建覆盖**的那一版
  1.6.19 本地包 —— 是**用户自己**装的（Lead 确认，见 §3 R23）。
- 反向取证（E12，Phase E 遗留的错包）：Release 上那份 `WorkBuddy2API-Hub_1.6.10.3_all.fpk` 与 Phase E 1.6.17.1 包
  payload 逐文件一致，只有 `manifest.version` 与 `checksum` 不同 ⇒ 包内部自洽、完整性断言抓不到版本错。
  这条依然是「已发布资产是错包」的硬证据（R8）。

### 2.9 全量套件（E1 = 10/0/0）

```
$ python3 tests/run_all.py --jobs 4
  ...
  122 passed, 0 failed, 0 skipped  (/vol2/1000/AgentWork/2api/workbuddy2api-hub)
  total 83.4s with --jobs 4
```

- 树里套件数（92 Python + 30 JS = 122）与 `README.md:134` 写的「122 个套件：92 个 Python + 30 个 JS」**逐字一致**；
  本轮 `122 passed + 0 failed` 全绿（交付说明回填前是 `121 passed / 1 failed`，唯一红就是本套件的 R17/R23 四条）。
- e1 的三条自指断言已删（「passed == 树里套件数」「0 failed」「退出码 0」），改成「除本套件外无失败」+
  「本套件记为 PASS」+「退出码 0 或本套件是唯一红」；嵌套 run_all 时自我 `skip` 防递归。
- 交付说明 §4.1 记的 `120 passed / 1 failed` 是**我改写前的旧数**（唯一红是我自己钉 Phase E 旧契约的套件）；
  那条红属 E5/F5 的正常交接，不是产品缺陷。改写后的三轮分别是 `121/1`（回填前）、`122/0`（回填后）。

### 2.10 平台形状（E10 = 8/0/0，E11 = 11/0/0）

- E10：在一个 `delattr` 掉 `socket.AF_UNIX`（以及 UnixStreamServer/UnixDatagramServer）的子进程里跑**整套**，
  要求 rc=0、FAIL=0；并用孙辈解释器验证那个子进程的形状确实是 `False False`（无 AF_UNIX、无 `geteuid`）。
- E11：真 `git clone --depth 1 file://<本地仓库>`（**必须用 `file://`**，普通路径会忽略 `--depth`）里跑 e8/e2b，
  祖先关系与 annotated tag 断言必须变 SKIP 而不是 FAIL；再跑非 root 模拟（`os.geteuid = lambda: 1000`）——
  `e2b` 必须以「切 uid 需要 root」的理由跳过（R12 就是这条在 Windows 上假红过）。
- 顺带审计：所有 AF_UNIX 探针都有 `needs_unix()` 门；`setpriv`/`chown` 只在 `needs_root()` 之后；
  `/vol1/**` 先判目录存在；`tar`/`bash`/`git` 各有 gate；所有文本读取都显式 `encoding`（无 cp1252 打印陷阱）；
  路径比较统一 `.replace(os.sep, "/")`。

### 2.11 交付说明与方案书一致性（E15 = 22/0/0）

- `docs/phase-f-delivery.md` 的包指纹与磁盘产物**逐项对上**（包名、字节数、sha256、
  manifest `checksum` == 包内 `app.tgz` 的 md5、版本 `1.6.19`、`appname=workbuddy2api`）。**回填后一致**
  （`577330 B / 71edade7… / 27d6795c…`）；回填前它是红的（文档还写着重建前的 `601800 / c482c9fc… / be761a0f…`），
  这就是 R17。
- 合并事实与 git 对上（**动态，不写死 SHA**）：HEAD 历史里最近一次合并正好两个父、第二父 == `upstream/main`、
  文档记录的上游 head 是本树历史的提交、三条 cron（`17 3`/`23 9`/`41 15`）、五个真缺陷的关键词都在文档里。
- **设备声明必须与设备一致**（带牙，本轮新增）：正则抓「设备当前装的是 X / 设备上跑的还是 X」，X ≠ 设备实测版本即红。
  **回填后一致**（设备 1.6.19 = 文档 1.6.19）；回填前文档写 `1.6.17.1`（第 17、103 行）→ 红，这就是 R23。
  设备版本是我在真机上只读读出来的，不是抄文档。
- **R17/R23 已关闭**：Lead 已回填包指纹、§4.2 与设备状态（并注明设备上的 1.6.19 是**用户自己**装的、
  我方对设备只有只读核查）。回填前这四条是红的、回填后 22/0/0 —— 红→绿只由文档内容决定，这本身也是一条敏感性证明。
- 方案书 `docs/phase-f-plan.md` 里 FnDepot 那段已按实测更正，我核对过：它写了「`generate_sources.py:344` 只有仓库搜索那一支」
  与「`:352-356` 两支没有任何名字过滤」，并明确「不必须新建仓库」。我另外**直接读生成器源码**验证了这条更正：
  名字过滤在 `:344`（只有一处），代码搜索的两个 query 在 `:353` 与 `:356`，且这两行**都不带** `full_name` 过滤。

### 2.12 三环境 FAIL=0（task-27 的硬要求）

- **(a) 开发树**：本套件 `PASS=352 / FAIL=0 / SKIP=2`，exit 0（`/tmp/wb-f10-full.log`）；
  `python3 tests/run_all.py --jobs 4` = **`122 passed / 0 failed / 0 skipped`（83.4s，exit 0）**。
  交付说明回填前的那一轮是 `340 / 6 / 3` 与 `121 passed / 1 failed`（唯一红 = 本套件），差异全部来自 R17/R23 的文字。
- **(b) depth-1 浅克隆（CI 形状）**：`git clone --quiet --depth 1 file://$PWD /tmp/wb-f9-ci3`（**必须用 `file://`**，
  普通本地路径会忽略 `--depth` 而把整段历史拷过来，那样预演什么都证明不了），再把套件复制进去：用**已提交**的树跑
  = `PASS=249 / FAIL=4 / SKIP=15`（唯一根因是**提交里**的交付说明还写着设备 1.6.17.1，另 3 条为派生）；把**回填后**的
  交付说明放进同一个克隆再跑 = **`PASS=253 / FAIL=0 / SKIP=15`，exit 0**（`/tmp/wb-f9-ci3b.log`），
  ⇒ 只要 Lead 提交回填，CI 就是绿的。15 条 SKIP 全部是 `gate()` 且都写了理由：没有 `dist/` 包（E5/E12/E15）、
  depth-1 看不到历史对象（e8 的合并提交、e15 的合并事实与上游 head）、推不出版本（e8 的设备新旧比较）、
  `55dfad2` 不可达（e13 的修复前红复现）、没有 `upstream/main`（e16 的祖先关系与上游 diff）。
  分段：e1 10、e2 14、e2b 6、e3 33、e4 26、e5 0/0/1、e6 3、e7 10、e8 10/0/4、e9 35、e10 8、e11 11、
  e12 0/0/1、e13 34/0/1、e14 30/0/1、e15 11/0/4、e16 7/0/3。
- **(c) Windows 形状**：本机不是 Windows，用 `PLATFORM_SIM_CUSTOMIZE`（sitecustomize 在**整棵进程树**里删掉
  `socket.AF_UNIX`、`socketserver` 的六个 `Unix*` 类与 `os.geteuid`）→ e10 在子进程里 `runpy` 跑整套：**8 / 0 / 0**；
  e11 另跑一个非 root 子进程预演，要求 `e2b` 只 SKIP 不 FAIL（这正是 R12 在 windows-latest 上假红过的地方）。
  真 Windows 以 CI 腿为准（§4）。
- **为什么 CI 之前三平台全红（我独立复现出的两条根因）**：① `actions/checkout` 是 depth-1，问历史对象的断言
  （`git merge-base --is-ancestor`、`git cat-file -t <tag>`）在浅克隆里根本问不出答案，必须 `gate()/SKIP`；
  ② **发布 tag `fnos-1.6.19` 指向的 `26c2bcc` 是单父提交**（`26c2bcc db9e58b`，标题
  `test(verify): rewrite the fnOS gates for the three-part version and FnDepot`），而 HEAD `39a16f6` 才是合并——
  所以「HEAD 是合并提交」这条在任何 tag 检出下都是假的。两条都改成「HEAD 历史里最近一次合并」+ `have_object()` 前置后，
  浅克隆里 FAIL=0。

### 2.13 敏感性证明（改坏输入必红）与「发布后稳态」

三条**故意改坏**的实验，证明这些断言不是碰巧绿的：

| # | 改坏什么 | 命令 | 结果 |
|---|---|---|---|
| 1 | 把包副本里 `server/wb_export.py` 第 200 字节翻一位、重算 manifest checksum（`/tmp/wb-sens/WorkBuddy2API-Hub_1.6.19_all.fpk`） | `WB_PKG=/tmp/wb-sens/WorkBuddy2API-Hub_1.6.19_all.fpk python3 -u tests/_test_phase_e_verify.py e5` | **58 / 2**：`包载荷与 fnos-1.6.19 的树逐字节一致（40 个文件） -> ['server/wb_export.py (payload 9794a80a vs 26c2bcce… 的树)']`、`工作树上 verify-fpk 的失败数符合预期（1） -> []` |
| 2 | 已发布资产副本尾部多 1 字节（`/tmp/wb-sens/badcopy.fpk`） | `WB_PUBLISHED_ASSET=/tmp/wb-sens/badcopy.fpk python3 -u tests/_test_phase_e_verify.py e14` | **30 / 1**：`已发布资产副本的字节数与 sha256 与报告常量一致 -> (577843, '1773d865ee2fab76')` |
| 3 | 删掉 packager 套件里第 148 行调用点的 `cwd=`（`/tmp/wb-sens/pipeline_nocwd.py`） | `WB_RELEASE_PIPELINE_SUITE=/tmp/wb-sens/pipeline_nocwd.py python3 -u tests/_test_phase_e_verify.py e13` | **35 / 2**：`每个 subprocess.run 调用点都传了 cwd= -> {'call_sites': 5, 'sites_without_cwd': [148]}` |

| 4 | 在 Linux 上造 **CRLF 检出**（`git -c core.autocrlf=true clone … /tmp/wb-crlf`：`dashboard.html` = 560303 B / 10188 个 CRLF / 0 个裸 LF） | 修前：`(cd /tmp/wb-crlf && python3 -u tests/_test_phase_e_verify.py e3)`；修后同一条命令 | 修前 **32 / 1**：`直连 GET / == dashboard.html + 本次语言替换（逐字节，上游缓存头契约） -> (473324, 463136, 'zh')`（与 CI 日志逐字符相同，差值 = 10188 = 行数）；修后 **33 / 0 / 0** |

第 3 条还配了反证：只在注释里写 `cwd=` 的副本 `/tmp/wb-sens/pipeline_comment.py` → **该 check 仍 PASS**
（而旧的 `count("subprocess.run(") == count("cwd=")` 计数门在同一份文件上会算成 `5 != 6` → 假红）。
`tests/_test_release_pipeline.py` 里实测 5 个调用点（行 97/148/157/425/477）全部显式传了 `cwd=`。

**「发布后稳态」的定义**（套件按它决定「真跑」还是「SKIP」）：HEAD 恰好是某个 `fnos-X.Y.Z` 的提交、
`dist/` 里有该版本的包、设备装的就是那一版 —— 此时 E5 的「包载荷 == 该 tag 的树」必须 0 drift、
E5 在 tag 检出上跑 `verify-fpk` 必须 0 failed、E8 的「设备 `server/**` == 该包 payload」必须逐字节相等、
E14 的 fnpack 必须等于已发布资产。任何一环不在位（无 `dist/`、浅克隆、设备版本对不上、文档没回填）→
`gate()`/SKIP 并写明理由，**绝不 FAIL**，也**绝不用别的版本的包冒充锚**。

### 2.14 Windows 腿的 CRLF 根因（task-29 / R25）

CI run `38061914772`（`b8174b2`）只有 `windows-latest / python 3.12` 一条腿红，红在步骤 `Run every suite`，
artifact `11673721866` 里唯一根因套件是本套件、套件内唯一根因 check（日志 `:39`）：

```
[FAIL] 直连 GET / == dashboard.html + 本次语言替换（逐字节，上游缓存头契约）  -> (473324, 463136, 'zh')
```

- **根因**：GitHub 的 Windows runner 检出把 LF 转成 CRLF（本机 LF：`dashboard.html` 550115 B / 10188 行 / 0 个 CRLF；
  runner 上 560303 B / 10188 个 CRLF）。服务端按磁盘字节原样吐，而 `dashboard_source()` 当时是**文本模式** `open(path, encoding=…)`，
  通用换行把 CRLF 归一成 LF ⇒ 期望值每行少一字节，`473324 − 463136 = 10188` 正好是行数。
  上游自己的套件就是按磁盘字节读的（`tests/_test_dashboard_cache_headers.py:130` 用 `"rb"`、`:201` 用 `"ab"`），
  所以这是**测试侧口径错**，不是产品缺陷——**没有改任何产品代码**。
- **改法**（`tests/_test_phase_e_verify.py:831-840`，`dashboard_source()`）：改成 `open(path, "rb")` 再
  `.decode("utf-8", "replace")`，并加注释说明「Windows 检出可能是 CRLF，服务端吐的是磁盘字节」。
  调用点（`:1172` 的语言替换）不用改（替换目标串不含换行）。
- **同类点位审计**（要求 5）：在套件里搜了「`open(` + `read()` + 与 HTTP 响应/包载荷逐字节比」的四种形态 ——
  ① `expected = …` 只有这一处（`grep -n "expected ="` 唯一命中，且 `body ==`/`== body` 也只此一处）；
  ② 包载荷 ↔ **git 树**走 `payload_differs_from_git()`（`:391-406`），比的是 `git show <tag>:<path>` 的 blob 字节（LF），
  **与检出换行无关**；③ 包载荷 ↔ **工作树**的 `payload_differs_from_tree()`（`:409-424`）是磁盘字节比磁盘字节，
  且 e5 里它的用途正是「解释 verify-fpk 为什么会报 payload 不一致」，期望值由同一个 drift 列表算出（CRLF 下两边同时变化，判定不变）；
  ④ 设备侧比对（e8/e6）读的是**设备上的安装文件**与**包 payload**，两边都来自同一个包，与仓库换行无关。
  ⇒ 套件里**没有第二处**「文本读源码 vs 线上字节」的脆弱点。
- **灵敏度**：§2.13 第 4 条 —— 同一份 CRLF 检出上「修前 32/1（差值 10188）→ 修后 33/0/0」，LF 检出（开发树）始终 33/0/0。

### 2.15 被 run_all 拉起时不再重复跑一遍完整 run_all（task-30 / R26）

**先说清楚动机的来龙去脉**：这条改动最初是从 CI 上发现的 —— `windows-latest` 腿在 run `38063082755`
把本套件判成 `[FAIL] _test_phase_e_verify.py timed out after 300s`（同一 artifact 里套件自己是
`PASS=172 FAIL=0 SKIP=27`，它内部那条 e1 的嵌套 run_all 就花了 157.6s）。**但那不再是本改动的动机**：
用户已决定删掉全部自建 workflow（含 `tests.yml`），GitHub 上不再有自动运行，Windows 超时这件事不会再发生。
改动本身与 CI 无关地成立：**套件是被 `run_all.py` 拉起来的时候，不该再嵌套跑一遍完整 run_all** ——
外层那次 run 正在跑全部套件（包括本文件），嵌套是纯粹重复；而且它让「谁负责全量自检」这件事有两个答案。

**做法**（只碰 `tests/run_all.py` 与 `tests/_test_phase_e_verify.py`，产品代码与包一个字节未动）：

| 位置 | 改动 |
|---|---|
| `tests/run_all.py:26-33`（模块 docstring） | 说明本 runner 会给子进程留 `WB_RUN_ALL=1` 标记及其用途 |
| `tests/run_all.py:244-249`（`main()` 构造子进程 env） | `env["PYTHONIOENCODING"] = "utf-8"` 之后加 `env["WB_RUN_ALL"] = "1"` + 注释 |
| `tests/_test_phase_e_verify.py:536-541` | 新常量 `HARNESS_SMOKE_SUITE = "_test_lifecycle.py"`（快、每个 CI 腿都绿） |
| `tests/_test_phase_e_verify.py:860-886` | `e1_suites()` 里在 `WB_E1_NESTED` 分支**之后**新增 `WB_RUN_ALL == "1"` 分支 |

新分支只做「harness 冒烟」：`python3 tests/run_all.py _test_lifecycle.py --timeout 60`，断言 ① 退出码 0
② 汇总行是 `1 passed, 0 failed` ③ 打一条 NOTE 说明「完整集合的自检由外层那次 run_all 承担」。
`WB_E1_NESTED` 分支仍在前（e10/e11 的子跑因此行为不变），**独立运行（没有 `WB_RUN_ALL`）时路径一字未改**：
仍是完整嵌套 run_all + 原有 4 条断言（计数自洽 / 除本套件外无红 / 本套件被算作 passed / 退出码 0）+ 5 条
「我们的套件真的跑了」。

四条证明（task-30 要求 3）：

| # | 证明 | 命令 | 结果 |
|---|---|---|---|
| ① | 外层 run_all 里本套件墙钟：修前 vs 修后（同一个冻结克隆，唯一差异是这两个文件的版本） | `python3 tests/run_all.py --jobs 4`（克隆 = HEAD `6d7a64d` + 我的两个文件 / 再 `git checkout --` 回 HEAD 版） | 修后 **26.8s**、`122 passed / 0 failed / 0 skipped`、exit 0；修前 **49.6s**、同样 `122 / 0 / 0`。开发树上同样方向：78.9s（task-29 的 `/tmp/wb-f10-runall.log`）→ 41.6s |
| ② | 新分支确实生效 | `WB_RUN_ALL=1 python3 -u tests/_test_phase_e_verify.py e1_s` | **2.16s**，`PASS=2 FAIL=0`，NOTE `harness 冒烟耗时 = 2.1s` + 尾行 `1 passed, 0 failed, 0 skipped`（浅克隆里同一条 **2.15s**）。注意段落过滤是**子串**匹配：`e1` 会同时选中 e10–e16（16.3s），要单测 e1 得用 `e1_s` |
| ③ | 独立运行没有被削弱 | `python3 -u tests/_test_phase_e_verify.py e1_s`（不带 `WB_RUN_ALL`） | **42.3s**，`PASS=10 FAIL=0`（4 条核心断言 + 0 skipped + 退出码 + 5 条「我们的套件真的跑了」），NOTE `run_all 计数 = passed=122 failed=0 skipped=0` |
| ④ | 最慢平台的预算 | 用 CI 实测分解：Windows 上非 e1 工作 ≈142s + 嵌套 run_all 157.6s ≈ 300s（撞线） | 去重后把 157.6s 换成一次冒烟（Linux 2.1s，按 4× 估 ≈8s）⇒ 预计 ≈150s，余量 `300 / 150 ≈ 2.0×`（目标 ≥1.8×）。这是**预算估算**，且 CI 已不再运行，所以不是 CI 断言 |

三环境（task-30 要求 4）：

| 环境 | 命令 | 结果 |
|---|---|---|
| 开发树（冻结版 = HEAD + task-30 两个文件，隔离 packager 的在途改动） | `python3 tests/run_all.py --jobs 4` | `122 passed / 0 failed / 0 skipped`，exit 0；本套件行 `PASS=254 FAIL=0 SKIP=11 26.8s`（克隆里没有 `dist/`，故 SKIP 多） |
| depth-1 浅克隆（**没有 `WB_RUN_ALL`，所以仍完整嵌套** —— 这是它唯一与 CI 形状不同的地方） | `git clone --depth 1 file://<repo>` + 复制套件 → `python3 -u tests/_test_phase_e_verify.py` | `PASS=253 FAIL=0 SKIP=15`，exit 0，**49.2s**；其中 e1 的嵌套 run_all 自己 **32.1s**（NOTE `run_all 尾行`）。同克隆里 `WB_RUN_ALL=1 … e1_s` = 2.15s |
| Windows 形状（e10 平台预演） | 套件内 e10 | **8 / 0 / 0**（平台预演子进程计数 `PASS=185 FAIL=0 SKIP=26`），e11 **11 / 0 / 0** |

要求 5 的两个契约套件：`tests/_test_run_all_contracts.py` = `OK`（21.2s，它把 `run_all.py` 按字节复制到沙箱里跑，
所以它验的正是「真 runner 本身」）；`scripts/check_clean_checkout.py`（在跑完套件的克隆里）=
`checkout is clean: the suites left no repository-local state behind`，exit 0。

**注意（本报告写就时的开发树状态）**：`packager` 正在删 `.github/workflows/*`（task-31），
所以开发树上直接跑本套件会有 19 条红，全部在 e13/e14/e16 的「workflow 文件」断言上（外加 e10 的两条派生）——
那是**套件钉在旧 CI 现实上**，正是 task-34（WP-G2）要改成新现实的部分；**与本改动无关**
（同一个冻结克隆里，改动前后都是 0 FAIL，见上表 ①）。

## §3 缺陷与登记项

本阶段**没有发现任何未修复的产品缺陷**：当前开发树上本套件 `352 / 0 / 2`、`run_all --jobs 4` 122 passed / 0 failed。
以下 12 条是登记项（`register()`，不计 PASS/FAIL），按「Lead 交付前必须处理」排序：

| 编号 | 事项 | 性质 | 归属 / 建议 |
|---|---|---|---|
| **R17** | 交付说明第 11/90 行的包指纹曾指着重建前的包（601800 / `c482c9fc…` / `be761a0f…`），§4.2 曾占位 | **已修**（Lead 回填） | 现为 577330 B / `71edade7…` / checksum `27d6795c…` + 本报告 §0 的数字；e15 复测 22/0/0 |
| **R23** | 交付说明曾写「设备当前装的是 1.6.17.1」「设备一个字没动」，但设备实际是 **1.6.19**（manifest checksum `be761a0f…`，20:18 装、20:19 起服务），且是**用户自己**装的 | **已修**（Lead 回填 §1/§5，含「我方只做只读核查」） | 旧文两句在「发布前」是真的、现已过时；新增的带牙断言（e15）复测通过 —— 这正是它该抓的东西 |
| **R16** | `fnpack.json` 的 `size`/`sha256` 曾是占位 | **已关闭** | 已按**已发布资产**回填 `577842` / `3d341706…`；E14 用 Releases API 独立复核（release `408987082`）。**不要**回填成本机 dist 的 577330 |
| **R19** | 嵌套 `__pycache__/*.pyc` 进包（本机构建 ≠ CI 构建） | **已修**（packager task-28） | `scripts/build-fpk.sh` +2 行：`--exclude='__pycache__'`（:230）与 `--exclude='*.pyc'`（:231）；新包载荷 0 个字节码、与已发布资产逐文件相同 |
| **R20** | 验收套件必须「状态感知 + 浅克隆安全」 | 纪律（归我） | §2.12/§2.13 就是这条的定义；CI 上这套件只在 `26c2bcc` 才进树而 CI 是 depth-1，所以「CI 红 ≠ 包坏」，要先看是哪条 gate |
| **R21** | `build-fpk.sh` 的排除式与 `.gitignore` 漂移（`logs/`、`suite-logs/`、`.pytest_cache/`、`wrt/ipk/`、`wrt/apk/`、`*.pyo`…） | **本阶段不修** | 根治 = 暂存源改成 `git ls-files`；本轮登记 |
| **R22** | `app.tgz` 的 md5 随目录 mtime 变、字节级不可复现（同一 tag 两次构建 checksum 不同） | **本阶段不修** | 口径 = 载荷内容 + 已发布资产 sha256（E5/E12/E14 都按这个判） |
| **R15** | 「现有仓库本身够格被召回」在 push 之前不成立 | 结论更正（文档与实际不符） | 上架说明改成「push 之后才可被代码搜索索引」 |
| **R18** | `docker-publish.yml` / `release-checksums.yml` 在我们树里是 100755（上游 100644） | 噪音（内容一字未改） | 交付前 `chmod 644` 清掉；来源是 Phase E 的 `55dfad2`/`9dff35f` |
| **R24** | 设备面板仍是默认密码（`panel_password_is_default: true`） | 设备配置，不是代码缺陷 | 交付说明里提一句；网关 socket 免密与它无关 |
| **R25** | 验收套件用**文本模式**读 `dashboard.html` 再与 HTTP 响应逐字节比 → 只有 Windows 腿红（CRLF 检出） | **已修**（task-29，测试侧口径错、产品代码一字未动） | `dashboard_source()`（`tests/_test_phase_e_verify.py:831-840`）改成 `open(path, "rb").read().decode(...)`；同类点位审计结论与敏感性证明见 §2.14 / §2.13 第 4 条 |
| **R26** | 验收套件在 `run_all.py` 内**又嵌套跑一遍完整 run_all**（重复劳动；最慢平台上曾把套件顶过每套件墙钟） | **已修**（task-30，按「谁调用谁负责全量」去重；产品代码一字未动） | `run_all.py:249` 给子进程留 `WB_RUN_ALL=1`；`_test_phase_e_verify.py:860-886` 在被 run_all 拉起时改为冒烟 `_test_lifecycle.py`，独立运行时行为不变。CI 里完整集合的自检由 CI 自己那次 run_all 承担（CI 已按要求停用）；证明见 §2.15 |

**R15 的完整证据**（这条是 Lead 主动要求我独立复核的，我复核的结论是「方向对、但前提缺一句」）：

- 生成器源码（我逐行读的）：仓库搜索那一支有 `if "fndepot" in full_name.lower():`（**`:344`，全文件只此一处**）；
  代码搜索两个 query 在 **`:353`**（`filename:fnpack.json`）与 **`:356`**（`+fork:true`），两行都不带名字过滤。
  ⇒ Lead 的更正**成立**，方案书现在写的也是这个。查重规则「Fork 永远输给非 Fork」在 `process_overlap()`
  `:306-307`，但它**只在已判定 high-risk 的配对里生效**（血缘对门槛 `name_rate>=0.50 or sig_rate>=0.30`），
  所以不是无条件「fork 必输」。
- **但我实测到一条前提**：GitHub 代码搜索索引的是**默认分支**，而我们根目录的 `fnpack.json` 只存在于**未推送的**
  合并提交里。证据：`GET /repos/ccrabit/workbuddy2api-hub/contents/fnpack.json` → **404**；
  `git ls-tree --name-only origin/main` 既没有 `fnpack.json` 也没有 `fndepot/`；`origin/main` 还是 `316eb8f`
  （合并提交 `db9e58b` 未推送）。另外 `GET /repos/ccrabit/workbuddy2api-hub` → `fork: true`，
  上游 `ardeyouxipianyi/workbuddy2api-hub`（`fork: false`）目前没有 `fnpack.json`（其 contents 也是 404）。
- ⇒ 结论方向对（不必新建仓库），但要写成「**push 之后**才具备被召回的条件；一旦上游也上架同签名文件，
  我们作为 fork 会按 `:306-307` 判负」。我**没有**对 GitHub 做任何写操作，只做了匿名 GET。

### Lead 交付前必须处理的事（清单）

1. **`fnpack.json` 已回填正确，别再动**（R16 关闭）：`size = 577842`、`sha256 = 3d341706c6fec4f7620ad75bba49fd3347b1b7c32c41d51cd8a4238c52f8a34c`，
   对应的是**已发布的 Release 资产**，不是本机 `dist/` 里的新包（577330 / `71edade7…`）——
   两者载荷逐文件相同、只差 gzip 外壳与产物时间，**不要**用本机包的数字覆盖。
2. **回填 `docs/phase-f-delivery.md`**（R17 + R23）——**Lead 已完成**：包指纹改为 `577330` 字节 /
   sha256 `71edade7833191f189ade8d1ca1938faa12db9d0cd90ec316c3596a86c11ac98` / checksum `27d6795c7ba2a4db89f1e82fabef6ef0`，
   设备状态改为 **1.6.19 且由用户自装**，并注明我方只做只读核查。**注意**：回填只存在于工作树，**还没提交** ——
   提交之前 depth-1 克隆/CI 看到的仍是旧文（我实测：红→绿只由这一份文件决定，见 §2.12(b)）。
3. **改上架说明的口径**（R15）：写成「**push 之后**才具备被代码搜索索引的条件；作为上游 fork，
   一旦上游也上架同签名文件，我们会按查重规则判负」。
4. **清掉可执行位噪音**（R18）：`chmod 644 .github/workflows/docker-publish.yml .github/workflows/release-checksums.yml`。
5. **决定并执行外部动作**（只有用户能定）：push → 打 annotated tag `fnos-1.6.19` → 发 Release。
   Release 资产既是 `download_url` 的目标，也是 FnDepot 收录（中心仓库每天 16:00 UTC 生成 `valid_sources.txt`）的前提。
6. **仓库 Issues 开关**：同步冲突路径要靠 issue/summary 留痕，而我们的 PAT 改不了 `has_issues`，需要用户在 Settings 里打开。
7. **设备现状已确认并由 Lead 写进交付说明 §5**（R23）：设备上**已经是 1.6.19**，而且是**用户自己装的**——
   设备 manifest 的 `checksum = be761a0f2715cd903edcf8e88d4198f9` 正是 packager 重建前那一版本地包
   （Lead 留证 `/tmp/wb-r19-old-dist-1.6.19.fpk`，601800 B / sha256 `c482c9fc…`）的 checksum，而那份包就是
   Phase F 交付答复里 `present` 给用户的两份文件之一；用户随后「测试完成」时装上并跑起来（`server/**` mtime 20:18、
   进程 20:19 起）。**我方对设备自始至终只有只读核查**（`ls`/`stat`/`md5sum`/socket 探针），没有 install/upgrade/uninstall。
   交付说明旧文里「设备当前装的是 1.6.17.1」「设备一个字没动」两句是**当时（发布前）的事实**，现已过时。
   另记一条（Lead 要求写进 R23）：设备载荷 = **已发布资产载荷的 40 个文件 + 3 个 `server/release/__pycache__/*.cpython-311.pyc`（R19 的字节码）+ 运行时
   `__pycache__` 目录**，其余逐字节相同 ⇒ e8 的设备比对是**单向包含**（设备必须含包内每个文件的相同 md5，允许设备多出
   `__pycache__`/`*.pyc`），不是双向集合相等。
8. **`server/**` 在本次验证窗口内没有被任何人改过**（e5 的逐字节门与 e8 的未提交改动门在看着）。若交付前又有人动了包内文件，
   必须重建包并让我复跑 `e5`/`e12`，才能再说「可以交付」。
9. **提一句设备默认密码**（R24）：设备 `/panel/status` 报 `panel_password_is_default: true`，直连 8788 即可尝试登录。

## §4 未验证清单（我做不到，或不在此范围）

1. **真实 GitHub 上的自动并入**：三条 cron 的行为、冲突分支推送、issue/summary 都需要真实跑一次才能确认；
   交付说明自己也写「这套修复还没在真实 GitHub 上跑过一次」。我只能证明代码形状与行为级 fixture。
2. **真机安装动作本身**：包在应用中心里能不能装、能不能原地升级、主题/单位/说明在真机浏览器里的观感，
   要有人**做安装动作**才能看（Phase F 我自己一个字没动设备）。但**运行态**我已用只读探针在设备上验过
   （§2 里 e6 的 7 条）：设备实际装的是 1.6.19（manifest checksum `be761a0f…`，装于 20:18、服务 20:19 起），
   免密口径（socket 上 `authenticated: true`、`via_gateway: true`）、挂载前缀（`<base href="/app/workbuddy2api/">`
   与 `window.__WB_BASE__`/`__WB_VIA_GATEWAY__`）、版本串都成立。脚注：设备装的是**重建前**那版（R23），
   与最终包差 3 个 `release/__pycache__/*.pyc`（R19 的字节码），载荷其余部分逐字节相同；
   设备上那份 1.6.19 是**用户自己装的**（Lead 确认，见 §3 R23）。
   另外 e8 的设备比对是**单向包含**：设备必须含包内每个源文件的相同 md5，允许设备多出 `__pycache__`/`*.pyc`
   （实测设备上 23 个：3 个本地构建痕迹 + 20 个运行时生成），不是双向集合相等。
3. **FnDepot 收录**：`valid_sources.txt` 由中心仓库每天 16:00 UTC 生成，收录与否要等它跑一次（且要先 push）；
   `download_url` 指向的 Release 资产要等 push + 打 tag + 发 Release 之后才存在。
4. **Release/上架动作本身**：本阶段没 push、没打 tag、没发 Release（我也不允许做），这几步只有用户决定后才能做。
5. **`/v1` 在网关 socket 上免 API key 的影响面**：我只能证明「uid 0 或应用自身 uid 连 socket 打 `/v1` 不带头也 200，
   TCP 仍 401」；真机上有没有第三个用户能碰到这个 socket，取决于 NAS 的权限模型，需要真机确认。
6. **Windows 腿**：e10/e11 在本地复算形状；真实 `windows-latest / python 3.12` 腿在 CI run `38061914772` 上跑完过整套，
   当时唯一红就是 R25（已在 task-29 修）。修后 Windows 的最终判定仍以你再跑一次 CI 为准（我没有 push 权限，也没 push）。

## §5 有意口径差异（写进交付说明用）

1. **网关 socket 上的 `/v1` 也被免 API key**：`_panel_ok()` 的首行就是 `_key_ok()` 的前置，所以 peer 校验通过后
   连 `/v1` 也不需要 API key（TCP 直连仍 401 并有提示）。Lead 裁决保持现状，指定原句：
   「API key 仍然保护 TCP 入口；网关 socket 上的面板会话同时放开 `/v1`（`_key_ok()` 首行 `_panel_ok()` 的直接后果），
   属有意设计」。
2. **`verify-fpk.sh` 的同一命令在不同检出上给出不同结果**（都不是产品缺陷）：在**发布 tag 的检出**
   （`git worktree add --detach … fnos-1.6.19`）上对已发布包装的是 `71 passed / 0 failed`；在**前移了 24 个提交的
   工作树**上对同一个新包装的是 `69 passed / 1 failed`，唯一失败是 `every packaged file is byte-identical to the tree`
   （「包 != 这棵树」），另有「包就是这棵树构建的」因 HEAD 无 tag 而跳过。两个数字我都独立跑过（e5 里状态感知地覆盖两条路径）。
3. **`create tarball` 的 `checksum` 派生自 app.tgz 的成员 mtime**：所以同一个源树两次构建的 checksum 可能不同，
   而「包内容是否一致」要用 payload 逐字节比对（E5/E12 就是这么做的）。
4. **设备断言不用 mtime**：用户可能随时安装/升级，服务也在持续写数据目录；e8 只做「逐字节一致 + 数据目录可读」。
5. **`fnos/manifest` 里的 `version = 1.6.10` 是占位值**（构建时被 `write_manifest` 覆写），静态读仓库时会看到它。

## §6 交付物与指纹（本报告写就时）

| 文件 | 行数 / 字节 | sha256 |
|---|---|---|
| `tests/_test_phase_e_verify.py`（task-30 后） | 3780 行 / 201580 字节 | `96d12522637881eba7331d15524784d1f81876920547100b63851cb149eac48e` |
| `tests/run_all.py`（task-30 后） | 339 行 / 13416 字节 | `dceea00f2886800c3aa106f6b8fd7e5d8a7f3ea9d8dcd483a888318c0c064cee` |
| `dist/WorkBuddy2API-Hub_1.6.19_all.fpk`（本机重建后） | 577330 B | `71edade7833191f189ade8d1ca1938faa12db9d0cd90ec316c3596a86c11ac98` |
| `/tmp/wb-published/WorkBuddy2API-Hub_1.6.19_all.fpk`（已发布资产副本） | 577842 B | `3d341706c6fec4f7620ad75bba49fd3347b1b7c32c41d51cd8a4238c52f8a34c` |

- 本报告：`docs/phase-f-verify.md`（自有 sha256 不写在正文里——写进来就会因为这一行立刻失效）。
- 工作树状态（`git status --porcelain`，HEAD = `b8174b2`「chore(release): fix the payload, make the acceptance suite state-aware」）：
  我的写域里被改的是 `M tests/_test_phase_e_verify.py`（task-29 的 R25 + task-30 的 R26）、`M tests/run_all.py`（task-30）、
  `M docs/phase-f-verify.md`（本报告）。**同一次 `git status` 里还有别人的在途改动**，我既没碰也没评：
  `D .github/workflows/{build-fpk,docker-publish,release-checksums,sync-upstream,tests}.yml`（packager task-31 删自建 workflow）、
  未跟踪的 `docs/phase-g-plan.md` 与 `scripts/gh-release.py`（Lead/packager 的 Phase G 草稿）。
- **发布 tag**：`fnos-1.6.19`（annotated）→ `26c2bcc`，是 HEAD 的祖先（`git describe` = `fnos-1.6.19-25-gb8174b2`，领先 25 个提交）。
- 包内文件（`server/**`、`ui/**`、`fnos/**`、`scripts/**`）在这个窗口里**没有被任何人改过**——
  e5 的逐字节比对与 e8 的未提交改动门就是这条的看门人。
- 我不 `git commit`、不 push、不打 tag、不动设备、不重建包（`dist/`、`build/` 的单写者是 Lead/packager）。
