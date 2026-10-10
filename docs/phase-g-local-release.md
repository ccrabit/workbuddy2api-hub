# 本地发布 Runbook（Phase G）

> 本文是「怎么写一个版本、怎么把它上传成 Release、怎么回填 FnDepot 源」的操作手册。
> 照着从头到尾跑一遍即可完成一次发布，命令都在这台飞牛 NAS 上实测过。
> 规格来源：`docs/phase-g-plan.md`（G-D1 ~ G-D6）。裁决原文：用户要求「不用自动运行构建脚本了，
> 以后还是本地更新版本上传吧，清理相关的文件及缓存；但是要上架 fndepot 商店」，并且明确选择
> 连 `tests.yml` 也一起删（GitHub 上不留任何自动运行）。

## 0. 现在是什么状态

| 项目 | 状态 |
| --- | --- |
| 本仓库自建 workflow | **全部删除**（`sync-upstream.yml`、`build-fpk.yml`、`release-checksums.yml`、`docker-publish.yml`、`tests.yml`） |
| `.github/workflows/release.yml` | **保留**（上游文件）。只在 `v*` tag 上触发，我们的 tag 是 `fnos-*`，且不再镜像上游 tag ⇒ 永不触发；留着是为了下次并入上游时不再冲突 |
| GitHub Actions 上的自动运行 | 无。没有 `schedule`、没有 `push` 触发、没有 `workflow_dispatch` 兜底 |
| 版本号 | 上游最新 release tag 的三段数字 `X.Y.Z`（例：上游 `v1.6.19` → 我们的 `1.6.19`） |
| 发布 tag | `fnos-X.Y.Z`（换命名空间的原因见 `docs/phase-f-version-policy.md`） |
| 包名 / `appname` | 文件 `WorkBuddy2API-Hub_<版本>_all.fpk`；`appname` 仍是 `workbuddy2api`（它决定应用目录、数据目录、socket 与网关前缀，不能改） |
| 发布动作 | 全部在本机做：本地构建 → 本地校验 → 本地打 tag → 用 `scripts/gh-release.py` 上传资产 |

两个网络事实（本机实测，2026-10-10）：

- `api.github.com` 与 `uploads.github.com` 都能连（TLS 1.3，握手正常）。
- `git ls-remote origin` 也能连（15 秒内返回）。所以 tag 可以优先用 `git push` 推；万一哪次 `git`
  卡住，用 `scripts/gh-release.py tag-create` 走 API 打 tag（见 §4）。

## 1. 一页速查

```bash
cd /vol2/1000/AgentWork/2api/workbuddy2api-hub
VERSION=1.6.20                                  # 上游最新 release tag 的三段数字
TAG="fnos-${VERSION}"
FPK="dist/WorkBuddy2API-Hub_${VERSION}_all.fpk"
VERSION_COMMIT="$(git rev-parse HEAD)"           # 这次发布用的提交

# 1) 本地测试全绿（0 failed / 0 skipped）
python3 tests/run_all.py --jobs 4

# 2) 构建（显式给 VERSION，别让脚本自己猜）
PACKAGER=ccrabit PACKAGER_URL=https://github.com/ccrabit/workbuddy2api-hub \
  VERSION="${VERSION}" bash scripts/build-fpk.sh

# 3) 校验（期望 "71 passed, 0 failed"；若 tag 还没打，会有一条 SKIP → "70 passed, 0 failed"）
bash scripts/verify-fpk.sh "${FPK}"

# 4) 旁置校验和（格式与 Release 上的 .sha256 资产一致）
python3 scripts/gh-release.py sha256 "${FPK}" > "${FPK}.sha256"

# 5) 打 tag 并推送（tag 必须指向上面构建用的那个提交）
git tag -a "${TAG}" -m "WorkBuddy2API-Hub ${VERSION} (upstream v${VERSION})" "${VERSION_COMMIT}"
git push origin "refs/tags/${TAG}"

# 6) 上传 Release 资产（同名资产会被替换）
python3 scripts/gh-release.py release-upload "${TAG}" "${FPK}" "${FPK}.sha256"

# 7) 发布说明（有 Release 就改正文，没有就新建）
python3 scripts/gh-release.py release-edit "${TAG}" docs/phase-g-release-body.example.md
# 新版本： python3 scripts/gh-release.py release-create "${TAG}" <正文文件> --name "WorkBuddy2API-Hub ${TAG}"

# 8) 回填 fnpack.json 的 sha256 / size / updated_at（见 §6），再核对一遍
python3 scripts/gh-release.py release-get "${TAG}" | head -40
```

## 2. 前置条件

1. 工作树干净、测试全绿：`git status --porcelain` 只看得到你有意修改的文件。
2. `python3` 可用（构建脚本用 `python3`/`tar`/`find`；GNU tar 与 GNU findutils 必需，macOS 的 BSD
   tar 会被 `verify-fpk.sh` 拒绝）。
3. token：`/root/.gh-token`（`chmod 600`，93 字节）或环境变量 `WB_GH_TOKEN`。脚本按
   「环境变量优先，其次 `--token-file`」读取；token **绝不写进仓库**，也绝不出现在任何提交里。
   token 需要 `repo` scope（细粒度 token 需要 Contents: Read and write + 对 Releases 的写权限）。
4. 你要发布的那个提交必须已经在 origin 上——Release 的资产挂在 tag 上，而 tag 指向提交。

## 3. 构建与校验

```bash
PACKAGER=ccrabit PACKAGER_URL=https://github.com/ccrabit/workbuddy2api-hub \
  VERSION=1.6.20 bash scripts/build-fpk.sh
```

- 必须显式传 `VERSION`。脚本的版本派生只在「HEAD 上有 `fnos-X.Y.Z` tag」时才等于那个 tag，
  否则给的是过程版本 `X.Y.Z-alpha<提交数>`；本地发布要的是一个正式版本号。
- 产物：`dist/WorkBuddy2API-Hub_<版本>_all.fpk`，脚本会打印字节数与 manifest 的 `checksum`。
- `verify-fpk.sh` 从包里解出 `app.tgz`，逐条核对 manifest、资产清单、payload 内容与仓库一致，
  并断言 `accounts/`、`usage/`、`tests/`、`docs/` 四个目录没有进包：

  | 情形 | 预期 |
  | --- | --- |
  | 构建用的提交上正好有 `fnos-<同一个版本>` tag | `71 passed, 0 failed` |
  | 还没有 tag（先构建后打 tag 的常规流程） | `70 passed, 0 failed`，其中 1 条打印 `SKIP`（无法比对「包就是这棵树构建的版本」） |

  两条路径都必须 `0 failed`；有 `failed` 就不要继续发布。

`dist/` 里放着历史测试包（`1.6.17.1`、`1.6.10.13`、`1.6.10.2`），它们不是本次发布的产物，别删也别上传。

## 4. tag

```bash
VERSION_COMMIT="$(git rev-parse HEAD)"     # 构建用的那个提交
git tag -a "fnos-${VERSION}" -m "WorkBuddy2API-Hub ${VERSION} (upstream v${VERSION})" "${VERSION_COMMIT}"
git push origin "refs/tags/fnos-${VERSION}"
```

- 同一个版本需要**重指**到一个新提交时（例如发布后才又改了一处文档）：

  ```bash
  git tag -f -a "fnos-${VERSION}" -m "WorkBuddy2API-Hub ${VERSION} (upstream v${VERSION})" "${VERSION_COMMIT}"
  git push --force origin "refs/tags/fnos-${VERSION}"
  ```

- 如果 `git` 连不上远端，用 API 打 tag（同样支持重指）：

  ```bash
  python3 scripts/gh-release.py tag-create "fnos-${VERSION}" "${VERSION_COMMIT}" \
      --message "WorkBuddy2API-Hub ${VERSION} (upstream v${VERSION})"
  python3 scripts/gh-release.py tag-create "fnos-${VERSION}" "${VERSION_COMMIT}" --force   # 重指
  ```

  重指会动到已有 Release 的 `target_commitish`，但**不会**重跑任何 workflow（仓库里已经没有任何
  会跑 tag 的本仓库 workflow）。

## 5. 上传 Release 资产

```bash
python3 scripts/gh-release.py release-upload "fnos-${VERSION}" "${FPK}" "${FPK}.sha256"
```

- 默认就是「覆盖」语义：同名资产先 `DELETE` 再上传。
- 想改成「已存在就报错」：加 `--no-clobber`。
- 一个 Release 上应该恰好两个资产：`WorkBuddy2API-Hub_<版本>_all.fpk` 与
  `WorkBuddy2API-Hub_<版本>_all.fpk.sha256`。`.sha256` 的内容是
  `<64 位十六进制>  <文件名>`（两个空格），和 `sha256sum -c` 兼容。
- 上传后用 `release-get` 核对：`size` 与本地 `stat -c %s` 一致、`state` 是 `uploaded`。

`scripts/gh-release.py` 的子命令：

| 子命令 | 作用 |
| --- | --- |
| `sha256 <file>` | 打印 `<sha256>  <basename>`，直接重定向就是 `.sha256` 资产 |
| `release-get <tag>` | 打印该 tag 的 Release JSON（不存在时退出码 3） |
| `release-create <tag> <正文文件> [--name] [--draft]` | 建 Release（正文 `-` 读 stdin） |
| `release-upload <tag> <文件...> [--no-clobber]` | 上传资产，默认覆盖同名 |
| `release-edit <tag> <正文文件> [--name]` | 替换 Release 正文（和标题） |
| `tag-create <tag> <sha> [--message] [--force]` | 走 git data API 打注解 tag，`--force` 重指 |

全局参数：`--repo`（默认 `ccrabit/workbuddy2api-hub`，也可用 `$WB_GH_REPO`）、
`--token-file`（默认 `/root/.gh-token`）、`--api`、`--upload`。
退出码：`0` 成功、`2` 用法错、`3` 找不到（HTTP 404）、`4` 其它失败。

## 6. 回填 `fnpack.json`

Release 上传成功后，把 `fnpack.json` 里对应版本的数字改成新包的数字（**这一步是本地文件改动，
和发布是同一次提交**）：

```jsonc
"releases": {
  "1.6.20": {                                   // 版本号 = 上游三段数字
    "changelog": "……",
    "updated_at": "2026-10-11T10:00:00+08:00",  // 上传完成的时间
    "packages": {
      "all": {
        "download_url": "https://github.com/ccrabit/workbuddy2api-hub/releases/download/fnos-1.6.20/WorkBuddy2API-Hub_1.6.20_all.fpk",
        "sha256": "<新包的 sha256>",
        "size": 123456                          // 字节数，必须与 Release 上的资产一致
      }
    }
  }
}
```

- `sha256` 用 `python3 scripts/gh-release.py sha256 dist/WorkBuddy2API-Hub_<版本>_all.fpk` 取第一列。
- `size` 用 `stat -c %s dist/WorkBuddy2API-Hub_<版本>_all.fpk`。
- `download_url` 里 tag 必须是 `fnos-<版本>`（不是 `v<版本>`），路径中的文件名要与资产名逐字符一致。
- **这份文件不在包里**：`scripts/build-fpk.sh` 的载荷排除式带 `--exclude='./fnpack.json'`。原因是它
  自指——包内副本里的 `sha256` / `size` 只能描述「装着它自己的那个包」，回填之后必然过期，而
  `verify-fpk.sh` 的 `every packaged file is byte-identical to the tree` 会因此永久报一条假失败
  （曾经的现象：每次回填后 `69 passed, 1 failed`，失败项 `not in the tree, or different: fnpack.json`）。
  服务端不读它（`grep -rn fnpack wb_proxy.py` 为空），FnDepot 客户端读的是仓库根这份。所以**回填只改
  仓库根文件，已经建好的 `.fpk` 不受影响，也不需要为了消掉这条而重建包**。

## 7. FnDepot（外部源）

- 中央仓库的扫描器只认名字里含 `fndepot` 的**非 fork** 仓库（依据：`generate_sources.py` 的仓库搜索
  只保留 `full_name` 含 `fndepot`、代码搜索 `filename:fnpack.json` 且排除 fork）。所以 FnDepot 源放在
  单独的新仓库（如 `ccrabit/FnDepot`），不是这个 fork。
- 源里 `download_url` 指向本仓库 Release 的**绝对 URL**，即
  `https://github.com/ccrabit/workbuddy2api-hub/releases/download/fnos-<版本>/WorkBuddy2API-Hub_<版本>_all.fpk`。
- 发布后自检：`curl -sIL <download_url> | head -1` 应是 `HTTP/2 200`（或 302 到
  `objects.githubusercontent.com`），且 `Content-Length` 与 `size` 一致。
- 该仓库的维护与校验由 Phase G 的 G4 负责（credits-engine）；本仓库只负责把包和数字产出来。

## 8. 故障排查

| 现象 | 原因 / 处理 |
| --- | --- |
| `error: no token: set $WB_GH_TOKEN or create /root/.gh-token` | token 文件不存在或不可读；`chmod 600 /root/.gh-token`，或 `export WB_GH_TOKEN=...` |
| `HTTP 401` | token 失效或复制时带了换行；重新签发 |
| `HTTP 403 ... Resource not accessible by integration` | token 权限不足（需要 `repo` scope / 细粒度需 Contents+Releases 写权限），或目标仓库不属于该 token |
| `HTTP 404 ... releases/tags/fnos-...` | tag 没推到 origin，或这个 tag 还没建 Release（用 `release-create`） |
| `HTTP 422 ... Reference already exists` | tag 已存在；要么改版本号，要么 `tag-create --force` / `git push --force` |
| 上传卡住或超时 | 先 `python3 -c "import socket,ssl; ..."` 测 `uploads.github.com:443`；确认能连再重试（§0 有实测样例） |
| `.github/workflows/release.yml` 报「找不到 tests.yml 工作流」 | 它读的是被删掉的 `tests.yml`，只在 `v*` tag 上才会跑；别推 `v*` tag（我们的命名空间是 `fnos-*`），这条就永远不会发生 |
| `scripts/verify-fpk.sh` 有 failed | 包与树不一致；重新构建，别手工改包 |
| 回填 `fnpack.json` 后 `verify-fpk.sh` 报 `every packaged file is byte-identical to the tree`（`not in the tree, or different: fnpack.json`） | Phase G 之前的老症状：载荷里曾带着根 `fnpack.json` 的副本，所以每次回填都让包内副本过期。现在它被排除在载荷外（见 §6），**回填仓库根文件不会再影响已建好的包**；若仍报这条，说明包是旧脚本建的，重新构建一次即可 |
| `python3 tests/run_all.py` 有红 | 先修测试再发布（删掉 workflow 之后测试口径的对齐由 verifier 在 Phase G task-34 收尾） |

## 9. 发布后的验收清单

- [ ] `python3 tests/run_all.py --jobs 4` → `0 failed / 0 skipped`
- [ ] `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_<版本>_all.fpk` → `0 failed`
- [ ] `git ls-remote --tags origin "refs/tags/fnos-<版本>"` 指向本次发布的提交
- [ ] `release-get fnos-<版本>`：两个资产、`state=uploaded`、`size` 与本地一致
- [ ] `fnpack.json` 的 `sha256` / `size` / `updated_at` 与 Release 一致
- [ ] 载荷 39 个文件、包内没有 `server/fnpack.json`：`tar -xzOf dist/WorkBuddy2API-Hub_<版本>_all.fpk app.tgz | tar -tzf - | grep -c 'server/fnpack.json'` 应输出 `0`
- [ ] FnDepot 源的 `download_url` HTTP 200，且能下载到与 `sha256` 相符的文件
- [ ] `ls .github/workflows/` 只有 `release.yml`；`grep -rn "on: schedule\|cron:" .github/` 无输出

## 10. 不做的事（Phase G §5）

- 不恢复任何 CI（包括 `workflow_dispatch` 兜底）；GitHub 上没有自动构建、自动同步、自动测试。
- 不改 `appname`、不改免密网关口径。
- 不动设备（不安装/卸载/升级飞牛应用）。
- 不 vendor 第三方 `shuangji66/FnDepot`，不回补 Phase D 已删模块。
