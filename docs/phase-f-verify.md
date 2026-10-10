# Phase F 独立终验报告（WP-F5 / task-25）

> 验证者：`verifier`（独立于全部写者）。写域只有本文件与 `tests/_test_phase_e_verify.py`。
> 本阶段目标（`docs/phase-f-plan.md`）：把上游 v1.6.19 并入飞牛 fork、修好「自动并入没生效」、
> 准备 FnDepot 上架材料、把版本号与上游三段号对齐（`1.6.19`）；**只出本地测试包**，不 push、不打 tag、
> 不发 Release、不动设备。用户原话见 `docs/phase-f-delivery.md:3`（m05838）。

## §0 结论摘要（一眼看全）

| 项 | 判定 | 通过 / 失败 / 跳过 | 证据 |
|---|---|---|---|
| 合并正确性（基线 / 上游文件未动 / 飞牛层在位） | **通过** | 13 / 0 / 0 | §2.1、E16 |
| 版本与 tag 契约（`fnos-X.Y.Z`、删四段发布号、不镜像上游 tag） | **通过** | 37 / 0 / 0 | §2.2、E13 |
| 自动并入工作流（三条 cron、冲突分支、去镜像、exit 1） | **通过（静态+行为级）** | 含在 E13 内 | §2.3 |
| FnDepot 源 `fnpack.json`（中心校验器 + 结构 + 下载 URL） | **通过**（1 项须回填） | 26 / 0 / 0 | §2.4、E14、R16 |
| 免密口径（socket peer 即登录 / TCP 伪造仍被拒） | **通过** | 14+4+10 / 0 / 1 | §2.5、E2/E2b/E7 |
| 挂载前缀契约（`<base href>` 仅挂载态 / 直连逐字节） | **通过** | 33 / 0 / 0 | §2.6、E3 |
| 每 M tokens 积分（后端 credit 累加 / 界面除零） | **通过** | 26 / 0 / 0 | §2.7、E4 |
| 包与交付纪律（命名 / manifest / 逐字节 / verify-fpk） | **通过** | 56+14+13 / 0 / 2 | §2.8、E5/E8/E12 |
| 全量套件 `run_all.py --jobs 4` | **通过** | 121 / 0 / 0 | §2.9、E1 |
| 平台形状（无 AF_UNIX / shallow clone / 非 root） | **通过** | 8+11 / 0 / 0 | §2.10、E10/E11 |
| 交付说明与方案书一致性（F6 交叉核对） | **通过**（1 处待回填） | 21 / 0 / 0 | §2.11、E15、R17 |

- **本套件合计：PASS=334 / FAIL=0 / SKIP=3**（命令见 §1；原始日志 `/tmp/wb-f-full4.log`，共 17 段）。
- `python3 tests/run_all.py --jobs 4` → **121 passed, 0 failed, 0 skipped**（57.7s，exit 0；`/tmp/wb-f-runall3.log`）。
  Phase E 收口时这里是 86 套件，本阶段树里已有 91 个 Python + 30 个 JS 套件，全部真跑、没有一个被跳过。
- `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.19_all.fpk` → **70 passed, 0 failed**（exit 0；`/tmp/wb-f-verifyfpk.log`）。
  唯一未真跑的断言是「包就是这棵树构建的」——它是 tag 门（HEAD 上没有 `fnos-*` tag 时按设计跳过），打 tag 后会变 71 条。
- 3 条 SKIP 都写明理由：① 以 uid 65534 复现「应用自身 uid」分支要能遍历父目录（沙箱里是 `drwx------`）；
  ② HEAD 上没有 tag（本阶段不打 tag）；③ 包内文件相对 HEAD 有未提交改动（`README.md` 是 Lead 正在改的交付文档）。
- **一句话结论**：Phase F 的六件事在**契约级与行为级**都已成立，可以拿这个包上真机测；
  剩下的都不是代码问题，而是**只有用户在真实环境里才能做完的三件外部动作**（真机安装、真实 GitHub 上跑一次自动并入、
  push + 打 tag + 发 Release），外加 **3 件交付前必须做的事**：回填 `fnpack.json` 的 `size`/`sha256`（R16）、
  回填交付说明 §4.2（R17）、以及决定「不新建仓库」这条路要不要以「push 之后才成立」的前提写进上架说明（R15）。

## §1 复现入口

```bash
# 全套（约 55s；CI 上跑的就是这一条）
python3 tests/run_all.py --jobs 4

# 本套件（17 段，可用子串只跑某段）
python3 -u tests/_test_phase_e_verify.py                 # 全部：PASS=334 FAIL=0 SKIP=3
python3 -u tests/_test_phase_e_verify.py e13             # 37/0/0  版本与 tag 契约
python3 -u tests/_test_phase_e_verify.py e14             # 26/0/0  FnDepot 源 + ls-remote 对抗
python3 -u tests/_test_phase_e_verify.py e15             # 21/0/0  交付说明一致性
python3 -u tests/_test_phase_e_verify.py e16             # 13/0/0  合并正确性审计

# 包
VERSION=1.6.19 bash scripts/build-fpk.sh                 # 由 packager/Lead 执行，本阶段我只读产物
bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.19_all.fpk   # 70 passed / 0 failed
```

环境旋钮（都可选）：`WB_PHASE_E_STRICT=1`（「还没落地」从 SKIP 变硬 FAIL）、`WB_PKG`、`WB_PKG_VERSION`、
`WB_PHASE_E_PKG`（设备比对锚包）、`WB_WRONG_PKG`（错包副本）、`WB_PHASE_F_MERGE`（默认 `db9e58b`）、
`WB_DASHBOARD_PATH`（冻结版看板）。本阶段新增段落：`e13`（版本与 tag 契约）、`e14`（FnDepot 源 + ls-remote 对抗）、
`e15`（交付说明一致性）、`e16`（合并正确性审计）。

## §2 逐项结论

### 2.1 合并正确性（E16 = 13/0/0）

```
$ git rev-list --parents -n1 db9e58b
db9e58b6fb2bfc1096b8056776f39716fda1eb0c 316eb8f0d23839ec4daffd954076b5a0a8fa4945 e6902e25ff0bab01b18845e886cd0d98d18ad5f1
$ git merge-base --is-ancestor upstream/main db9e58b ; echo $?
0
```

- 合并提交 `db9e58b` 两个父分别是**我们上一版发布提交 `316eb8f`**与 **`upstream/main` = `e6902e2`**；`upstream/main` 确实是它的祖先。
- 飞牛层与 FnDepot 件全部在位（`fnos/manifest`、`scripts/build-fpk.sh`、`scripts/verify-fpk.sh`、
  `.github/workflows/{build-fpk,sync-upstream}.yml`、`wb_export.py`、`fnpack.json`、`fndepot/{ICON.PNG,README.md}`）。
- 上游新增文件也在（`tests/_test_dashboard_cache_headers.py`、`wb_pricing.py`、`wb_modelsdev.py`、`wb_probes.py`、`wb_identity.py`、
  `.github/workflows/release.yml`）。
- **acceptance §5「不改上游 `release.yml`」实测成立**：`git diff upstream/main HEAD -- .github/workflows/release.yml` 为空。
- 上游 workflow 里**只有 `tests.yml` 被改了内容**（唯一有记录的例外：`tags: ["v*"]` → `tags: ["v*", "fnos-*"]`，
  并给版本断言加 `fnos-*` 分支）。`build-fpk.yml` / `sync-upstream.yml` 是纯新增（上游没有这两个文件）。
- 合并没有留下三方冲突标记：`git grep -n -E '^<<<<<<< '` / `'^>>>>>>> '` / `'^=======$'` 三个模式在全仓**都没有命中**
  （合并提交的标题也写明是 `Merge upstream/main (v1.6.19 + 34 commits) into the fnOS fork`）。
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

### 2.4 FnDepot 源（E14 = 26/0/0，含 2 条登记）

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
- **R16（登记，须发布前回填）**：`size` 还是 `0`、`sha256` 还是 64 个 `0`，而真实包是 601800 字节 /
  `c482c9fc…f89f0e`。中心把它标为「建议项」，但下载器要靠它校验完整性 ⇒ 建议把回填做成发布步骤的一环。
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

### 2.8 包与交付纪律（E5 = 56/0/0，E8 = 14/0/2，E12 = 13/0/0）

```
$ sha256sum dist/WorkBuddy2API-Hub_1.6.19_all.fpk   # 与旁置 .sha256 一致
c482c9fca2032d2aeee9e54b2dedc37139de9c669be883e85b18ce7d1ff89f0e  WorkBuddy2API-Hub_1.6.19_all.fpk
$ ls -l dist/WorkBuddy2API-Hub_1.6.19_all.fpk
601800 字节
$ bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.19_all.fpk | tail -2
==> 70 passed, 0 failed
    the package behaves; only a real NAS can test the app store itself.
```

- 包名、manifest（`appname=workbuddy2api`、`version=1.6.19`、`platform=all`、`service_port=8788`、
  `checksum = be761a0f2715cd903edcf8e88d4198f9` == md5(包内 `app.tgz`)）、`ui/config`、payload 里 `server/` 下**全部 52 个文件**
  与仓库**逐字节一致**（不是抽查：断言从 `app.tgz` 枚举出的每个 `server/**` 再逐个比对），
  包内 payload 共 60 条（52 server + 5 ui + 3 config），且不含 `accounts/`/`usage/`/`docs/`/`tests/`/`dist/`/`build/`/`scripts/`/`fnos/`/`.git/`。
- verify-fpk 的 70 条我独立跑过一遍（不是采信 packager 的数字），并且判据是**状态感知**的：
  包版本 `1.6.19` == 本树派生的三段版本（`1.6.19-alpha44` 的 base），0 failed 就该是 0 failed。
- 设备侧（只读）：设备 `/vol1/@appcenter/workbuddy2api/server/**` 与发布的 **Phase E 1.6.17.1 包 payload**逐文件 md5 一致；
  设备 `wb_proxy.py` 的版本串与那个包 payload 里的相同；设备版本（1.6.17）不新于本树要交付的版本；
  数据目录只读检查通过。**我没有对设备做任何写操作**，也**不用 mtime 判设备状态**（服务在跑、目录会一直被写）。
- 反向取证（E12，Phase E 遗留的错包）：Release 上那份 `WorkBuddy2API-Hub_1.6.10.3_all.fpk` 与 Phase E 1.6.17.1 包
  payload 逐文件一致，只有 `manifest.version` 与 `checksum` 不同 ⇒ 包内部自洽、完整性断言抓不到版本错。
  这条依然是「已发布资产是错包」的硬证据（R8）。

### 2.9 全量套件（E1 = 10/0/0）

```
$ python3 tests/run_all.py --jobs 4
  ...
  [PASS] _test_phase_e_verify.py   PASS=334 FAIL=0 SKIP=3   53.4s
  121 passed, 0 failed, 0 skipped  (/vol2/1000/AgentWork/2api/workbuddy2api-hub)
  total 57.7s with --jobs 4
```

- 树里套件数（91 Python + 30 JS = 121）与 `README.md:134` 写的「121 个套件：91 个 Python + 30 个 JS」**逐字一致**。
- e1 的三条自指断言已删（「passed == 树里套件数」「0 failed」「退出码 0」），改成「除本套件外无失败」+
  「本套件记为 PASS」+「退出码 0 或本套件是唯一红」；嵌套 run_all 时自我 `skip` 防递归。
- 交付说明 §4.1 记的 `120 passed / 1 failed` 是**我改写前的旧数**（唯一红是我自己钉 Phase E 旧契约的套件）；
  现在全套 121/0/0 —— 那条红属 E5/F5 的正常交接，不是产品缺陷。

### 2.10 平台形状（E10 = 8/0/0，E11 = 11/0/0）

- E10：在一个 `delattr` 掉 `socket.AF_UNIX`（以及 UnixStreamServer/UnixDatagramServer）的子进程里跑**整套**，
  要求 rc=0、FAIL=0；并用孙辈解释器验证那个子进程的形状确实是 `False False`（无 AF_UNIX、无 `geteuid`）。
- E11：真 `git clone --depth 1 file://<本地仓库>`（**必须用 `file://`**，普通路径会忽略 `--depth`）里跑 e8/e2b，
  祖先关系与 annotated tag 断言必须变 SKIP 而不是 FAIL；再跑非 root 模拟（`os.geteuid = lambda: 1000`）——
  `e2b` 必须以「切 uid 需要 root」的理由跳过（R12 就是这条在 Windows 上假红过）。
- 顺带审计：所有 AF_UNIX 探针都有 `needs_unix()` 门；`setpriv`/`chown` 只在 `needs_root()` 之后；
  `/vol1/**` 先判目录存在；`tar`/`bash`/`git` 各有 gate；所有文本读取都显式 `encoding`（无 cp1252 打印陷阱）；
  路径比较统一 `.replace(os.sep, "/")`。

### 2.11 交付说明与方案书一致性（E15 = 21/0/0）

- `docs/phase-f-delivery.md` 的包指纹与磁盘产物**逐项对上**：包名、601800 字节、sha256 `c482c9fc…`、
  manifest `checksum` == 包内 `app.tgz` 的 md5、版本 `1.6.19`、`appname=workbuddy2api`。
- 合并事实与 git 对上：`db9e58b` 的两个父、`upstream/main = e6902e2`、三条 cron（`17 3`/`23 9`/`41 15`）、
  五个真缺陷的关键词都在文档里。
- 设备声明：文档写「设备上跑的还是 1.6.17.1」，设备上的版本串与 Phase E 包 payload 里的相同 ⇒ 一致。
- **R17（登记）**：交付说明 §4.2「独立终验」还是占位（「待 verifier 的 `docs/phase-f-verify.md` 收口后填」）——
  本文件就是那份输入，回填由 Lead 在交付前完成。
- 方案书 `docs/phase-f-plan.md` 里 FnDepot 那段已按实测更正，我核对过：它写了「`generate_sources.py:344` 只有仓库搜索那一支」
  与「`:352-356` 两支没有任何名字过滤」，并明确「不必须新建仓库」。我另外**直接读生成器源码**验证了这条更正：
  名字过滤在 `:344`（只有一处），代码搜索的两个 query 在 `:353` 与 `:356`，且这两行**都不带** `full_name` 过滤。

## §3 缺陷与登记项

本阶段**没有发现任何未修复的产品缺陷**（FAIL=0）。以下 4 条是登记项（`register()`，不计 PASS/FAIL），
按「Lead 交付前必须处理」排序：

| 编号 | 事项 | 性质 | 归属 / 建议 |
|---|---|---|---|
| **R16** | `fnpack.json` 的 `size=0`、`sha256=000…` 是占位 | 发布前必须回填 | 用 `dist/WorkBuddy2API-Hub_1.6.19_all.fpk` 的 601800 与 `c482c9fc…` 回填；建议做成发布步骤的一环 |
| **R17** | 交付说明 §4.2「独立终验」仍是占位 | 交付前必须回填 | Lead：把本报告 §0 的数字塞进去 |
| **R15** | 「现有仓库本身够格被召回」在 push 之前不成立 | 结论更正（文档与实际不符） | 上架说明改成「push 之后才可被代码搜索索引」 |
| **R18** | `docker-publish.yml` / `release-checksums.yml` 在我们树里是 100755（上游 100644） | 噪音（内容一字未改） | 交付前 `chmod 644` 清掉；来源是 Phase E 的 `55dfad2`/`9dff35f` |

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

1. **回填 `fnpack.json`**：`size` → `601800`、`sha256` → `c482c9fca2032d2aeee9e54b2dedc37139de9c669be883e85b18ce7d1ff89f0e`（R16）。
   顺序很重要：**先把要发布的那个包定死再回填**——包一旦重建，这两个值立刻过期。
2. **回填 `docs/phase-f-delivery.md` §4.2**：本报告 §0 的数字是 `PASS=334 / FAIL=0 / SKIP=3`、
   `run_all --jobs 4` = `121 passed / 0 failed / 0 skipped`、`verify-fpk` = `70 passed / 0 failed`；
   加上登记项 R15–R18 与 §4 的 6 条未验证（R17）。
3. **改上架说明的口径**（R15）：写成「**push 之后**才具备被代码搜索索引的条件；作为上游 fork，
   一旦上游也上架同签名文件，我们会按查重规则判负」。
4. **清掉可执行位噪音**（R18）：`chmod 644 .github/workflows/docker-publish.yml .github/workflows/release-checksums.yml`。
5. **决定并执行外部动作**（只有用户能定）：push → 打 annotated tag `fnos-1.6.19` → 发 Release。
   Release 资产既是 `download_url` 的目标，也是 FnDepot 收录（中心仓库每天 16:00 UTC 生成 `valid_sources.txt`）的前提。
6. **仓库 Issues 开关**：同步冲突路径要靠 issue/summary 留痕，而我们的 PAT 改不了 `has_issues`，需要用户在 Settings 里打开。
7. **告诉用户设备现状**：设备上仍是 1.6.17.1（本次一个字没动），1.6.19 是就地升级。
8. **`server/**` 在本次验证窗口内没有被任何人改过**（e5 的逐字节门与 e8 的未提交改动门在看着）。若交付前又有人动了包内文件，
   必须重建包并让我复跑 `e5`/`e12`，才能再说「可以交付」。

## §4 未验证清单（我做不到，或不在此范围）

1. **真实 GitHub 上的自动并入**：三条 cron 的行为、冲突分支推送、issue/summary 都需要真实跑一次才能确认；
   交付说明自己也写「这套修复还没在真实 GitHub 上跑过一次」。我只能证明代码形状与行为级 fixture。
2. **真机安装 1.6.19**：包能装、能原地升级、网关免密、主题/单位/说明这几项在 NAS 应用中心里的真实表现，
   需要在设备上装（Phase F 明确不动设备）。设备现在跑的仍是 1.6.17.1。
3. **FnDepot 收录**：`valid_sources.txt` 由中心仓库每天 16:00 UTC 生成，收录与否要等它跑一次（且要先 push）；
   `download_url` 指向的 Release 资产要等 push + 打 tag + 发 Release 之后才存在。
4. **Release/上架动作本身**：本阶段没 push、没打 tag、没发 Release（我也不允许做），这几步只有用户决定后才能做。
5. **`/v1` 在网关 socket 上免 API key 的影响面**：我只能证明「uid 0 或应用自身 uid 连 socket 打 `/v1` 不带头也 200，
   TCP 仍 401」；真机上有没有第三个用户能碰到这个 socket，取决于 NAS 的权限模型，需要真机确认。
6. **第二轮平台真机**（Windows 控制台、非 UTF-8 环境）：e10/e11 在本地复算过形状，真 Windows 以 CI 为准。

## §5 有意口径差异（写进交付说明用）

1. **网关 socket 上的 `/v1` 也被免 API key**：`_panel_ok()` 的首行就是 `_key_ok()` 的前置，所以 peer 校验通过后
   连 `/v1` 也不需要 API key（TCP 直连仍 401 并有提示）。Lead 裁决保持现状，指定原句：
   「API key 仍然保护 TCP 入口；网关 socket 上的面板会话同时放开 `/v1`（`_key_ok()` 首行 `_panel_ok()` 的直接后果），
   属有意设计」。
2. **`verify-fpk.sh` 的「包就是这棵树构建的」在 HEAD 无 tag 时跳过**：不是漏测，是 tag 门；
   打上 `fnos-1.6.19` 后同一命令会真跑（70 → 71）。
3. **`create tarball` 的 `checksum` 派生自 app.tgz 的成员 mtime**：所以同一个源树两次构建的 checksum 可能不同，
   而「包内容是否一致」要用 payload 逐字节比对（E5/E12 就是这么做的）。
4. **设备断言不用 mtime**：用户可能随时安装/升级，服务也在持续写数据目录；e8 只做「逐字节一致 + 数据目录可读」。
5. **`fnos/manifest` 里的 `version = 1.6.10` 是占位值**（构建时被 `write_manifest` 覆写），静态读仓库时会看到它。

## §6 交付物与指纹（本报告写就时）

| 文件 | 行数 / 字节 | sha256 |
|---|---|---|
| `tests/_test_phase_e_verify.py` | 3060 行 | `5f4ffb33c46f9ba29ee1b0448af788300541c088dcc7800a1596aa34e8a60e23` |
| `dist/WorkBuddy2API-Hub_1.6.19_all.fpk` | 601800 B | `c482c9fca2032d2aeee9e54b2dedc37139de9c669be883e85b18ce7d1ff89f0e` |

- 本报告：`docs/phase-f-verify.md`（自有 sha256 不写在正文里——写进来就会因为这一行立刻失效）。
- 工作树状态（`git status --porcelain`，HEAD = `db9e58b`）：`M README.md`（Lead 的交付文档）、
  `M docs/phase-f-plan.md`（Lead 已更正的方案书）、`M tests/_test_phase_e_verify.py`（我的套件）、
  `?? docs/phase-f-delivery.md`（Lead 的交付说明）。包内文件（`server/**`、`ui/**`、`fnos/**`、`scripts/**`）
  在这个窗口里**没有被任何人改过**——e5 的逐字节比对与 e8 的未提交改动门就是这条的看门人。
- 我不 `git commit`、不 push、不打 tag、不动设备、不重建包（`dist/`、`build/` 的单写者是 Lead/packager）。
