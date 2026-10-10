# Phase G 独立验收 —— 自检段（WP-G2a / task-35）

> 写者：verifier（独立验收）。写域：`tests/_test_release_engineering.py`、`tests/_test_release_assets.py`、
> `tests/_test_release_pipeline.py`、`tests/_test_phase_e_verify.py`、`docs/phase-g-verify.md`。
> 本文件先落 **task-35 的自检段**；Phase G 的终验（task-34：发布资产定稿后）在本文件后续 §2.x 继续追加。
> 状态：task-35 完成（`run_all` 已回绿）。基线 `HEAD` = `6d7a64d`。
> 纪律：未 `git commit` / 未 push / 未打 tag / 未动设备 / 未重建 fpk / 未改任何产品代码。

## 0. 结论摘要

| # | 项 | 判定 | 数字（改动前 → 改动后） | 证据 |
|---|---|---|---|---|
| G1 | `python3 tests/run_all.py --jobs 4` | **通过** | 118 passed / 4 failed → **122 passed / 0 failed / 0 skipped**（53.5s，exit 0） | §2.0 |
| G2 | `tests/_test_release_engineering.py` | **通过** | `Ran 6 tests` / `ERRORS=2` → **`Ran 8 tests` / OK** | §2.1 |
| G3 | `tests/_test_release_assets.py` | **通过** | `Ran 60 tests` / `ERRORS=2` → **`Ran 62 tests` / OK** | §2.1 |
| G4 | `tests/_test_release_pipeline.py` | **通过** | `Ran 21 tests` / `FAILED (failures=6, skipped=4)` → **`Ran 21 tests` / OK** | §2.1 |
| G5 | `tests/_test_phase_e_verify.py` | **通过** | `PASS=324 FAIL=19 SKIP=3` → **`PASS=349 FAIL=0 SKIP=3`**（exit 0；run_all 内 `PASS=341 FAIL=0 SKIP=3`） | §2.2 |
| G6 | 有牙证明（旧现实放回去必须变红） | **通过** | 3 个套件各恰好 1 条新断言变红、我的套件 3 条；无连带 | §2.3 |
| G7 | 只改验收侧，产品代码零改动 | **通过** | 我改的 4 个文件全在 `tests/`；`dist/**`、`fnpack.json`、`dashboard.html`、`wb_proxy.py`、`.github/**`、`scripts/**`、`fnos/**` 我一个字没动 | §5 |

**红线**：没有为了变绿而放宽任何断言。4 个套件里被改写的是「断言对象」——从「某个自建 workflow 文件存在且内容正确」改成「那份能力现在由谁保证（本地脚本 / runbook / 树状态）」；旧现实一旦放回去，对应断言按 §2.3 变红。

## 1. 复现入口

```bash
cd /vol2/1000/AgentWork/2api/workbuddy2api-hub
python3 tests/run_all.py --jobs 4                                   # 全量：122 passed / 0 failed
python3 tests/_test_release_engineering.py                          # Ran 8 tests / OK
python3 tests/_test_release_assets.py                               # Ran 62 tests / OK
python3 tests/_test_release_pipeline.py                             # Ran 21 tests / OK
python3 -u tests/_test_phase_e_verify.py                            # PASS=349 FAIL=0 SKIP=3
python3 -u tests/_test_phase_e_verify.py e13 e16                    # 只跑改写过的两段（49/0/0）
WB_PUBLISHED_ASSET=/path/to/WorkBuddy2API-Hub_1.6.19_all.fpk ...    # e8/e14/e15 的发布件副本（非默认路径时）
```

有牙证明的复现（不写回主树，全部在 `/tmp` 的副本里做）：

```bash
rm -rf /tmp/wb-g-teeth && mkdir -p /tmp/wb-g-teeth
cd /vol2/1000/AgentWork/2api/workbuddy2api-hub
tar cf - --exclude=./dist --exclude=./build --exclude=./.git/index.lock . | (cd /tmp/wb-g-teeth && tar xf -)
cd /tmp/wb-g-teeth && git checkout -- .github/workflows     # ← 把 5 个自建 workflow「放回去」= 旧现实
for s in _test_release_engineering.py _test_release_assets.py _test_release_pipeline.py; do
  python3 tests/$s; echo "$s exit=$?"; done
python3 -u tests/_test_phase_e_verify.py e13 e16
```

## 2. 逐项结论

### 2.0 `run_all --jobs 4`（G1）

```
  [PASS] _test_release_engineering.py           OK                                                     0.1s
  [PASS] _test_release_assets.py                OK                                                     0.7s
  [PASS] _test_release_pipeline.py              OK                                                     3.2s
  [PASS] _test_phase_e_verify.py                PASS=341 FAIL=0 SKIP=3                                49.6s
  122 passed, 0 failed, 0 skipped  (/vol2/1000/AgentWork/2api/workbuddy2api-hub)
  total 53.5s with --jobs 4
```

原始日志 `/tmp/wb-g-runall.log`（exit 0）。改动前同一命令是 `118 passed, 4 failed`，29 条红全部可归因于 task-31 删除 5 个自建 workflow（packager 的归因基线：把 5 个 workflow 恢复到副本后旧套件 = `PASS=351 FAIL=0 SKIP=3`、内部 run_all `122/0/0`；我用自己的 `/tmp/wb-g-teeth` 副本独立复现了「恢复 = 红」这一半，见 §2.3）。

### 2.1 三个发布侧套件（G2–G4）：断言对象从「workflow 文件」搬到「保留的能力」

| 套件 | 旧断言（钉在已删文件上） | 现在断言什么 |
|---|---|---|
| `_test_release_engineering.py` | `test_release_checksums_workflow_hashes_every_asset`、`test_tests_workflow_asserts_tag_against_source` 读 `release-checksums.yml` / `tests.yml` | 8 条：`.github/workflows/` **只剩**上游 `release.yml`；`release.yml` 只认 `v*` 且不含 `fnos-`；tag 门现在在 `scripts/build-fpk.sh`（`head_release_tag` / `^fnos-[0-9]+(\.[0-9]+){2}$` / `--print-version`）；**真跑** `scripts/gh-release.py sha256 <文件>` 断言输出与 `hashlib` 一致（校验和副产物改由本地工具产出）；runbook `docs/phase-g-local-release.md` 就是发版清单（7 步命令 + 「只有 `release.yml`」+ `cron:` 无输出） |
| `_test_release_assets.py` | `test_dropping_a_leg_narrows_what_the_gate_requires`、`test_the_repository_matrix_is_the_expected_three` 读 `tests.yml` | 矩阵没了，留下**解析器契约**：仓库里不再有矩阵文件（`sorted(listdir) == ["release.yml"]`）；被删矩阵块的逐字副本存为常量 `LEGACY_MATRIX`（只作文本，绝不写回 `.github/`），继续断言「三条腿都点名」「少一条腿会收窄门的要求」；`git show HEAD:.github/workflows/tests.yml` 取不到时 `skip`，取到时要求常量逐字来自它 |
| `_test_release_pipeline.py` | `WorkflowGateTests`（6 条静态 workflow 门）+ `TagAssertWorkflowTests`（4 条全 skip） | `PhaseGRepositoryTests`(6)：只剩 `release.yml`；`.github/` 下无 `on: schedule`/`cron:`；本地工具覆盖发版每一步（6 个子命令 + 无 token 泄漏 + 目标仓库）；**真跑** `gh-release.py` 无参 → rc=2、`--help` → rc=0；树扫描证明没有任何文本把上游 tag 镜像进本 fork（并断言同一正则能抓到 phase F 之前那段 mirror 步骤 = 自灵敏度）；runbook 即清单。`TagNamespaceGateTests`(4)：用真 `build-fpk.sh` 的 fixture 断言 `fnos-<source>` → 包版本、`fnos-9.9.9` → 被抓、`release-1.6.19` / `v1.6.19` **不是**本 fork 的发布 tag（原来这 4 条在「没有 tag」时全 skip，现在真跑） |

### 2.2 我的验收套件（G5）

`python3 -u tests/_test_phase_e_verify.py` → **PASS=349 FAIL=0 SKIP=3**（exit 0，日志 `/tmp/wb-g-full2.log`）。分段：

| 段 | PASS/FAIL/SKIP | 本次是否改动 |
|---|---|---|
| e1 run_all 全量套件 | 10 / 0 / 0 | 否 |
| e2 网关免密口径 | 14 / 0 / 0 | 否 |
| e2b peer uid 矩阵 | 4 / 0 / 1 | 否 |
| e3 挂载前缀契约 | 33 / 0 / 0 | 否 |
| e4 每 M tokens 积分 | 26 / 0 / 0 | 否 |
| e5 最终 fpk | 60 / 0 / 0 | **是**（§2.4-①） |
| e6 真机只读探针 | 7 / 0 / 0 | 否 |
| e7 免密防线加固面 | 10 / 0 / 0 | 否 |
| e8 交付纪律 + 设备 | 15 / 0 / 2 | **是**（§2.4-③） |
| e9 cockpit 导出 | 35 / 0 / 0 | 否 |
| e10 平台预演 | 8 / 0 / 0 | 否（派生红自动转绿，见下） |
| e11 shallow clone 预演 | 11 / 0 / 0 | 否 |
| e12 已发布错包反向取证 | 13 / 0 / 0 | 否 |
| e13 版本与 tag 契约 | 32 / 0 / 0 | **是**（16 条 workflow 静态门整段改写） |
| e14 FnDepot 源 | 32 / 0 / 0 | **是**（§2.4-②） |
| e15 交付说明一致性 | 22 / 0 / 0 | **是**（§2.4-④） |
| e16 合并正确性审计 | 17 / 0 / 0 | **是**（状态感知，见下） |

两条派生红（e10 的「子进程退出码 0 / FAIL==0」、e1 的「本套件在 run_all 内算 passed」）是**根因消失后自动转绿**的，没有放宽：e10 的子进程跑的就是同一个套件，e13/e14/e16 转绿后它自然绿（子进程计数 `PASS=204 FAIL=0 SKIP=12`）。

e16 的两条 workflow 断言改成**状态感知**：Phase G 的删除还没进 HEAD（工作树 `D .github/workflows/…` 未提交），所以 `git diff upstream/main HEAD` 仍会看到那 5 个文件。断言写成「HEAD 上被改过内容的上游 workflow 只可能是 `tests.yml`（`fnos-*` 那一处有记录的例外）」+「每条差异要么是只有本 fork 有的文件、要么是那个例外」，删除进 HEAD 之后两条都自动成立，**不靠跳过、不靠写死 SHA**。

### 2.3 有牙证明（G6）

在 `/tmp/wb-g-teeth`（仓库副本 + `git checkout -- .github/workflows` 把 5 个旧 workflow 放回去 = 旧现实）实跑：

| 套件/段 | 退出码 | 红的是什么 | 红了几条 |
|---|---|---|---|
| `_test_release_engineering.py` | 1 | `FAIL: test_only_upstreams_release_workflow_is_left` | 恰好 1 |
| `_test_release_assets.py` | 1 | `FAIL: test_the_repository_has_no_ci_matrix_to_wait_for` | 恰好 1 |
| `_test_release_pipeline.py` | 1 | `FAIL: test_only_upstreams_release_workflow_is_left` | 恰好 1 |
| `_test_phase_e_verify.py e13 e16` | 1 | `` `.github/workflows/` 只剩上游的 release.yml ``、派生的「packager 发布流水线套件独立重跑 rc=0」、e16 的「5 个自建 workflow 一个都没回来」 | 3 |

原始输出（每个套件尾部三行）：

```
FAIL: test_only_upstreams_release_workflow_is_left (__main__.LocalReleaseTests.test_only_upstreams_release_workflow_is_left)
Ran 8 tests in 0.055s
FAILED (failures=1)

FAIL: test_the_repository_has_no_ci_matrix_to_wait_for (__main__.MatrixLegsTests.test_the_repository_has_no_ci_matrix_to_wait_for)
Ran 62 tests in 0.716s
FAILED (failures=1)

FAIL: test_only_upstreams_release_workflow_is_left (__main__.PhaseGRepositoryTests.test_only_upstreams_release_workflow_is_left)
Ran 21 tests in 3.398s
FAILED (failures=1)
```

要点：三条新断言**各自只被对应的旧现实打红**，没有连带（恢复 `tests.yml` 不会让「无 cron」那条红，因为 tests.yml 本来就没有 schedule；恢复 `sync-upstream.yml` 也不会让 mirror 扫描红，因为 phase F 已经把镜像步骤删掉了）。

### 2.4 包/文档锚点改成状态感知（不许削弱）

Phase G 之后 `dist/` 里的包**不再等于** fnos-1.6.19 的发布件（本轮实测：`dist/WorkBuddy2API-Hub_1.6.19_all.fpk` = 592233 B / sha256 `095dbc11…`，载荷 39 个文件，与 **HEAD 的树**逐字节一致；已发布资产副本 = 577842 B / `3d341706…`，载荷 40 个文件，与 **fnos-1.6.19 的树**逐字节一致）。四处锚点按「包是谁构建的」判定，全部保留红路径：

- **① e5（包 ↔ 它的构建提交）**：载荷与 tag 树一致 → 直接过；不一致但与 **HEAD 的树**一致 → 登记 R27 并断言「候选包与它自己的构建提交逐字节一致」；两者都不一致 → **红**（真漂移）。
- **② e14（fnpack 指纹 vs Release 资产）**：改为两条独立断言——「已发布资产的 payload == fnos-1.6.19 的树」（强，实测 0 处不同）+「本机 dist 要么等于发布件、要么是与 HEAD 一致的候选包」，并把差异登记成 R27。
- **③ e8（设备锚点）**：设备装的是**发布件**，所以锚点优先取已发布资产副本（`WB_PUBLISHED_ASSET`）；没有副本时只接受「载荷仍等于它 tag 那棵树」的 dist 包，否则登记 R29 并 `gate`，**不拿候选包冒充锚**（实测设备 35 个源文件与发布件 payload 逐字节一致，设备多出的 23 个 `__pycache__/*.pyc` 按设计忽略）。
- **④ e15（交付说明指纹）**：文档记的是发布前那次构建（577330 B / `71edade7…`），dist 已重建 → 登记 R28；同时把**发布侧**的数字钉在手上的发布件副本上（577842 B / `3d341706…` 必须逐字出现在文档里）。若文档既不匹配磁盘、发布侧数字又核不上任何artifact，仍然红。

## 3. 登记项（R27 起，不是代码缺陷，只登记）

| # | 登记项 | 事实 | 归属 |
|---|---|---|---|
| R27 | `dist/` 里的 1.6.19 包已是「新树」的候选包 | 与已发布资产逐文件比较：内容不同 5 个；发布件有而候选包没有 1 个（`server/fnpack.json`）；差异来自树已前移，且 `scripts/build-fpk.sh:245` 新增 `--exclude='./fnpack.json'`（有意：根 `fnpack.json` 是 FnDepot 源清单，不再跟着 app 走） | packager（知悉即可；交付物是「候选包」，不是发布件） |
| R28 | 交付说明 §1 的本机构建指纹已被重建取代 | 文档 577330 B / `71edade7…` vs 磁盘 592233 B / `095dbc11…`；设备上装的那份不受影响 | Lead（提交前回填；e15 已把发布侧数字钉在发布件副本上） |
| R29 | 设备锚点不能再用 dist 里的包 | 设备 = 1.6.19 发布件；`dist/` 那一版是新树候选包 ⇒ 锚点改取已发布资产副本（`WB_PUBLISHED_ASSET`，默认 `/tmp/wb-published/WorkBuddy2API-Hub_1.6.19_all.fpk`） | 本套件（已改） |
| R30 | Phase G 的 workflow 删除尚未进 HEAD | `git status` 里 5 个 `D .github/workflows/*.yml` 未提交，所以 e16 的 diff 仍看得到它们；e16 已写成状态感知（删除进 HEAD 后自动成立） | Lead（提交时机） |

## 4. 未验证 / 边界

1. **CI 已不存在**：Phase G 的决定是不再有任何 GitHub 自动化（`.github/workflows/` 只剩上游 `release.yml`，只在 `v*` tag 触发）。所以本阶段没有「等 CI 结果」这一步；等价门改由本机 `run_all --jobs 4` 承担（§2.0）。
2. **发布动作本身没法在这里验**：`gh-release.py release-create/release-upload/release-edit/tag-create` 需要真 token 与网络，我只验了「子命令齐全 / 无参退回 usage / `sha256` 离线可跑且与 hashlib 一致 / runbook 把它写成清单」。真发一次 Release 属用户步骤（`docs/phase-g-local-release.md` §1）。
3. **平台腿退化为本机预演**：Windows/无 AF_UNIX 的判定由 e10（子进程删掉 `socket.AF_UNIX` 跑整套）与 e11（depth-1 浅克隆）承担，不再是 CI 矩阵；两者都绿。
4. **设备只读**：只证明设备 `server/**` 含它自己那一版发布件 payload 的每个源文件且逐字节一致、设备版本 1.6.19 未变；谁何时安装、有没有第三方动过设备，本机取不到证据。

## 5. 交付物与指纹

| 文件 | 行数 | sha256 |
|---|---|---|
| `tests/_test_release_engineering.py` | 142 | `7d906312adf885d66ea8b1eb742d16f7cc8a221fe554c777bb5b7f821160f087` |
| `tests/_test_release_assets.py` | 892 | `1fbc66d04e38d08d7b343cd6f570042f216f6ef70e31b66e19a82393f808880c` |
| `tests/_test_release_pipeline.py` | 575 | `090fcaaa3dbc519c9c3ac8990a10231d8e4eed29d3912b745a5d90b3124069e2` |
| `tests/_test_phase_e_verify.py` | 3929 | `ceb1c32c30f11a19e0fb727ef9849c47f47a2bd5950bda69df60e96d8dd038a4` |
| `docs/phase-g-verify.md`（本文件） | — | 收口消息里给出（写在文件里会立刻失效） |

`git status --porcelain`（本阶段全部改动，**我只碰 tests/ 与 docs/**）：

```
 D .github/workflows/build-fpk.yml         # task-31（packager）
 D .github/workflows/docker-publish.yml    # task-31
 D .github/workflows/release-checksums.yml # task-31
 D .github/workflows/sync-upstream.yml     # task-31
 D .github/workflows/tests.yml             # task-31
 M .gitignore                              # 别人
 M README.md                               # packager
 M docs/phase-f-verify.md                  # 我（Phase F 报告，早前）
 M docs/phase-f-version-policy.md          # packager
 M fnos/README.md                          # packager
 M scripts/build-fpk.sh                    # packager
 M tests/_test_phase_e_verify.py           # 我（task-35）
 M tests/_test_release_assets.py           # 我（task-35）
 M tests/_test_release_engineering.py      # 我（task-35）
 M tests/_test_release_pipeline.py         # 我（task-35）
 M tests/run_all.py                        # 我（task-30）
?? docs/phase-g-local-release.md           # packager
?? docs/phase-g-plan.md                    # Lead
?? docs/phase-g-release-body.example.md    # packager
?? scripts/gh-release.py                   # packager
```

未 `git commit` / 未 push / 未打 tag / 未动设备 / 未重建 fpk；`dist/**`、`fnpack.json`、`dashboard.html`、`wb_proxy.py`、`.github/**`、`scripts/**`、`fnos/**` 我一个字节没改。
