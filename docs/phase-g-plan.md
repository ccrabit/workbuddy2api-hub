# Phase G — 停掉 GitHub 自动化、改本地发布、上架 FnDepot

权威规格（Lead 落盘）。任何与本文冲突的历史文档（`docs/phase-f-plan.md` §2.2/§5、`docs/phase-f-version-policy.md`
关于 CI 自动同步/自动构建的段落）以本文为准。

## 1. 用户指令（m06957 逐字）

> 不用自动运行构建脚本了，以后还是本地更新版本上传吧，清理相关的文件及缓存；但是要上架fndepot商店，
> https://github.com/shuangji66/FnDepot，比如这个第三方源就收录了

## 2. 冻结决策

| # | 决策 | 依据 |
|---|---|---|
| G-D1 | **删除我们自建的全部 GitHub Actions workflow**：`sync-upstream.yml`、`build-fpk.yml`、`release-checksums.yml`、`docker-publish.yml`、`tests.yml`。GitHub 上不再有任何自动运行。 | 用户 2026-10-10 选择「连 tests.yml 也删」。 |
| G-D2 | **保留上游自带、我们从未改过的 `release.yml`**（上游文件，只在被推 `v*` tag 时跑；我们的 tag 是 `fnos-*`，且已不再镜像上游 tag ⇒ 永不触发）。删它只会在下次并入上游时再冲突回来。 | 上游合并不造反；我们的 tag 命名空间已隔离。 |
| G-D3 | **发布改为本地流程**：本地构建 → 本地校验 → 本地打 tag/推 → 用本地脚本上传 Release 资产与 `.sha256` → 回填 `fnpack.json` 的 `sha256`/`size`/`updated_at`。版本号仍 = 上游最新 release tag 的三段 `X.Y.Z`。 | 用户「以后还是本地更新版本上传」。 |
| G-D4 | **重建并覆盖同版本 `fnos-1.6.19` 的 Release 资产**：用当前 main（含第二次合并 `5b5b5c1` 的 22 个上游提交 + R19/R25/R26 修复）构建，覆盖 Release `408987082` 的资产，并回填 `fnpack.json`；tag `fnos-1.6.19` **重指到最终提交**，使「tag ↔ 包 ↔ 资产」三者一致。 | 用户 2026-10-10 选择「B. 本地重建并覆盖同版本资产」。 |
| G-D5 | **上架 FnDepot 用新建的非 fork 仓库**（名字含 `fndepot`）。用户提供可建仓的 classic token 后由 Lead 建 `ccrabit/FnDepot` 并推内容；FPK 用**绝对 URL** 指向 `ccrabit/workbuddy2api-hub` 的 Release 资产。 | 中心仓库扫描器 `generate_sources.py`：仓库搜索路径只保留 `full_name` 含 `fndepot` 的仓库（61/62 个已收录源都是 `*/FnDepot`）；代码搜索路径 `filename:fnpack.json` 不含 fork，fork 版 `+fork:true` 只取首页 100 条。我们的 hub 仓库是 fork 且名字不含 fndepot ⇒ 不可依赖。实测当前 PAT 建仓 HTTP 403。 |
| G-D6 | `appname` 标识符仍是 `workbuddy2api`（改它会另起 `/vol1/@appdata/<app>` 数据目录）；显示名 `WorkBuddy2API-Hub`。 | 沿自 Phase E 冻结决策。 |

## 3. 工作包与写域

| WP | 内容 | 写域 | owner |
|---|---|---|---|
| WP-G1 | 删掉 G-D1 的 5 个 workflow；清理仓库与工作区缓存并补 `.gitignore`；新增**本地发布 runbook** + 本地上传脚本；改掉 README/fnos/README/docs 里对已删自动化的描述 | `.github/workflows/**`、`.gitignore`、`scripts/**`、`README.md`、`fnos/README.md`、`docs/phase-g-*.md`、`docs/phase-f-version-policy.md` | packager |
| WP-G2 | 让测试套件与「没有 CI」的现实一致（`_test_release_pipeline.py`、`_test_release_engineering.py`、`_test_phase_e_verify.py` 的 e13/e14/e15/e16/套件数断言），保持有牙（workflow 文件复活即红），并终验 G1/G4/G5 | `tests/**`（除产品代码）、`docs/phase-f-verify.md`、`docs/phase-g-verify.md` | verifier |
| WP-G3 | 重建并覆盖同版本发布（构建 → verify-fpk → 重指 tag → 上传资产与 `.sha256` → 回填 `fnpack.json` → 提交推送） | `dist/**`、`fnpack.json`、`docs/phase-f-delivery.md` | Lead |
| WP-G4 | 准备并推送 FnDepot 源仓库内容（根 `fnpack.json` + 应用图标/README/预览），过中心仓库校验器，并在次日扫描后核对 `valid_sources.txt` | `fndepot/**`（源仓库侧的 `fnpack.json` 与资产先落在本地临时目录） | credits-engine（Lead 建仓与推送） |

依赖顺序：**G1 → G3 → G4 → G2**（G2 是终验，必须在树定型之后）。

## 4. 验收标准

1. `.github/workflows/` 里只剩上游的 `release.yml`；仓库内**没有任何** `on: schedule` 的 workflow。
2. 本地发布 runbook 可照抄执行：文档里的每条命令都能跑通（Lead 亲自按它跑一遍 G3）。
3. `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.19_all.fpk` = 0 failed；Release 资产 sha256 == 本地包 sha256 == `fnpack.json` 里的值。
4. `python3 tests/run_all.py --jobs 4` = 0 failed、0 skipped；不因删除 workflow 而出现「跳过式绿」。
5. GitHub `ccrabit/FnDepot` 存在（非 fork、公开、根目录有 `fnpack.json`），中心仓库校验器 `parse_and_fingerprint()` / `validate_v2_app()` 都为 True；`valid_sources.txt` 收录情况在次日 16:00 UTC 扫描后核对并记录（收录与否都要如实报告）。
6. 工作区缓存清零：`git status --porcelain` 干净（`dist/` 与 `build/` 属 gitignore 的产物不算），`__pycache__`/`*.pyc`/`build/`/`suite-logs` 已清或已忽略。

## 5. 明确不做

- 不恢复任何 CI（含把 workflow 改成 `workflow_dispatch` 兜底）。
- 不改 `appname`、不改飞牛网关/免密口径、不动设备（设备只做只读核查）。
- 不 vendor 第三方源仓库内容（`shuangji66/FnDepot` 只作格式参考）。
- 不回补 Phase D 的 `wb_credits.py`/`wb_taskcenter.py`（沿 Phase E §5 决策）。
