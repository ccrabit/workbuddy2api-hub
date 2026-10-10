# 版本号与发布 tag 约定（Phase F）

本文是本仓库**唯一的版本号规则出处**。`scripts/build-fpk.sh`、`.github/workflows/build-fpk.yml`、
`.github/workflows/sync-upstream.yml`、`.github/workflows/tests.yml` 与 `fnos/README.md` 都按这里
的口径实现；改动其中任何一处，请先改这里。

## 1. 契约（一句话）

**这个 fork 的版本号就是上游自己的三段版本号，发布 tag 是 `fnos-<那个版本>`。**

上游 release `v1.6.19` → 我们的 tag `fnos-1.6.19` → 包名 `WorkBuddy2API-Hub_1.6.19_all.fpk` →
`manifest` 里 `version = 1.6.19` → Release 标题 `WorkBuddy2API-Hub 1.6.19`。同一个数字，五处一致。

没有第四段（`1.6.19.3` 这种），也没有自己的发布计数器。

## 2. 版本号从哪来

`bash scripts/build-fpk.sh --print-version` 是唯一权威实现（`derive_version()`），实测行为：

| 现场 | 输出 | 说明 |
| --- | --- | --- |
| HEAD 上有 annotated tag `fnos-1.6.19` | `1.6.19` | **发布版本**：tag 就是版本，不看别的 tag |
| 同上，但用 `--alpha` | `1.6.19-alpha0` | 已经发布过的状态做试验包，只加后缀 |
| `fnos-1.6.19` 在 HEAD 的前一个提交 | `1.6.19-alpha1` | 后缀数字 k = 距该发布过了多少提交 |
| HEAD 只有历史 tag `v1.6.17.1` | `1.6.17-alpha17` | 四段 tag 不再算发布；base 取最近的 `fnos-*`/`vX.Y.Z` |
| 没有任何 tag，也没有 upstream remote | `1.6.10-alpha0` | 最后兜底：`fnos/manifest` 里的占位版本 |
| 本地无 tag，upstream remote 上有 `v1.6.19` | `1.6.19-alpha0` | 兜底第二级：`git ls-remote --tags upstream` |
| 任意现场 + `VERSION=1.6.19` | `1.6.19` | 显式指定最高优先（手工发版用） |

兜底顺序（只在没有 `fnos-*` tag 时走）：**最近一个 `fnos-*` tag 版本 → 上游 remote 上最新的
`vX.Y.Z` → `fnos/manifest` 占位版本**。前两级只用来给**过程包**起名字；发布包永远来自 tag 或
显式 `VERSION=`。

查上游要网络，所以是「本地能找到就别问远端」：本地 `git tag --list 'v*'` 有三段 tag 就不发
`ls-remote`，离线也不会挂住。

## 3. 为什么放弃第四段

Phase E 的规则是「上游三段 tag + 第四段（本基线上的第几次发布）」，比如 `1.6.17.1`。两个问题：

1. **它依赖「这次 checkout 能看到哪些上游 tag」。** CI 全新 clone 只看得到本仓库的 tag，于是
   推送 `v1.6.17.1` 时脚本把基线算成 `v1.6.10`、序号 3，构建出了 **1.6.10.3**——比设备上已装的
   1.6.17.1 还小，应用中心不会提示升级（Release `407525712`，附件
   `WorkBuddy2API-Hub_1.6.10.3_all.fpk`）。
2. **它对读数字的人没有意义。** `1.6.19.7` 既不是上游的版本，也不是任何标准；飞牛比较版本号的
   规则没有公开文档，自编号码等于自己给自己加一层解释成本。

新规则对第一个问题的答案是：**版本不再从「可见 tag 集合」推导，只从 HEAD 上的 tag 取**。同一
提交在任何环境（全新 clone、shallow clone、别的机器）都得到同一个版本。

## 4. 为什么发布 tag 用 `fnos-` 前缀

上游有自己的发布工作流：它监听 **push 到 `v*` tag** 并据此创建 draft release。我们继续用
`v1.6.19` 这类 tag 会有两个后果：

- 我们的 tag 会连带触发上游的发布流程；
- 两个仓库各自有同名/同前缀的 `v*` tag，`git fetch upstream --tags` 之后互相覆盖（本地 tag 与
  远端 tag 打架，`git fetch` 会拒绝更新）。

所以本仓库的发布 tag 一律 `fnos-<版本>`，与上游的 `vX.Y.Z`、`vX.Y.Z.N` 完全错开。这也意味着
**上游的 tag 绝不推到本仓库**：不镜像、不推送，需要知道上游最新版本时按需 `ls-remote`。

## 5. 发版流程

**自动**（`sync-upstream.yml`，每天北京时间 11:17 / 17:23 / 23:41 各试一次，GitHub 定时任务
常晚点甚至丢失，冗余三次）：

1. fetch upstream（`git fetch --tags --prune upstream`，**不推任何 tag 到 origin**）；
2. `HEAD..upstream/main` 为 0 就结束；否则 `git merge --no-edit upstream/main` 成功则推送到本
   仓库分支；
3. 取 `upstream/main` 上最新的三段 `vX.Y.Z` tag 作为候选版本，与本仓库**已发布**版本
   （`git ls-remote --tags --refs origin` 里最大的 `fnos-*`）比较；不更新就结束；
4. 打 annotated tag `fnos-<版本>` 并推送，然后显式 `uses: ./.github/workflows/build-fpk.yml`
   构建（用 `GITHUB_TOKEN` 推的 tag 不会触发别的 workflow，所以必须显式调用）。

**手工**：

```bash
git tag -a fnos-1.6.19 -m "WorkBuddy2API-Hub 1.6.19 (upstream v1.6.19)"
git push origin fnos-1.6.19        # build-fpk.yml 会核对 tag 与 --print-version
```

或在没有 tag 的情况下显式给版本：`VERSION=1.6.19 bash scripts/build-fpk.sh`。

**彩排**：tag 名带 `-ci` 后缀（例如 `fnos-1.6.19-ci`）时 `tests.yml` 的 tag 断言会跳过 tag 与
源码版本的比较（源码一致性检查仍然跑）。

## 6. 历史四段 tag 怎么办

`v1.6.10.1`、`v1.6.10.2`、`v1.6.17.1` 这些**保留不动**：删掉会让已有 Release 失去标签，而且它
们的存在本身无害。它们现在有两重身份：

- `tests.yml` 的 tag 断言仍然接受 `v<源码版本>` 与 `v<源码版本>.<序号>`，所以旧 tag 可以重新
  校验；
- `build-fpk.sh` **不再**把它们当发布：HEAD 上只有 `v1.6.17.1` 时得到的是过程版本
  `1.6.17-alpha17`，不再是 `1.6.17.1`。

已知的坏资产：Release `v1.6.17.1` 的附件是错版 `WorkBuddy2API-Hub_1.6.10.3_all.fpk`，需要重新
构建覆盖或改发新版本——这属于运维动作，不改变本约定。

## 7. 设备升级路径

设备当前装的是 `1.6.17.1`（旧的四段版本）。新包 `1.6.19` 数字更大，应用中心会提示升级；升级方式
和在应用中心里卸载旧包（向导里选**保留数据**）再装新包一样，数据目录 `/vol1/@appdata/workbuddy2api`
不受影响。装包前建议备份：

```bash
tar czf ~/workbuddy2api-backup.tgz -C /vol1/@appdata workbuddy2api/accounts workbuddy2api/settings.json
```

更早的旧包（`1.6.10.11`）同样可以一步升到 `1.6.19`（数字更大即可）。

## 8. 门禁

| 门 | 位置 | 覆盖 |
| --- | --- | --- |
| 版本契约（行为） | `tests/_test_release_pipeline.py` `VersionContractTests` | tag 即版本、浅克隆、历史四段 tag 不再算发布、`--alpha` 只加后缀、兜底链三级、断网/无 remote |
| 有牙证明 | 同上 `test_the_contract_fails_on_a_script_without_the_fnOS_namespace` | 把脚本改回旧命名空间后，同一断言必须失败 |
| 工作流（静态） | 同上 `WorkflowGateTests` | `build-fpk.yml` 认 `fnos-*` 且核对 `--print-version`；`sync-upstream.yml` 三条 cron、**不推上游 tag**、只发更新版本、冲突分支与 summary |
| 有牙证明 | 同上 `test_the_static_check_rejects_the_old_mirror_step` | 把旧的镜像步骤拼回去，静态门必须失败 |
| tag 断言（行为） | 同上 `TagAssertWorkflowTests` | 把 `tests.yml` 里那段 run 抽出来真的跑：`fnos-<源码版本>` 通过，`fnos-9.9.9`/`release-<版本>` 失败，历史 `v*` 仍通过 |
| 发布工程钉子 | `tests/_test_release_engineering.py` | tag 门禁接受 `fnos-`、触发条件保持上游原样、checksums、Docker、README 套件数 |
| 包身份 | `scripts/verify-fpk.sh` | `manifest` 版本必须是**三段数字**（四段或 `-alpha` 一律失败）；HEAD 上有 `fnos-<版本>` tag 时还要求「包就是这棵树构建的版本」，没有 tag 则跳过并打一行 `SKIP` 说明 |

修前/修后证据：`tests/_test_release_pipeline.py` 在 Phase E 的树（`git archive HEAD`）上
**19 项里 16 项失败**，在改完的树上 19 项全绿。

## 9. `tests.yml` 的触发条件（Lead 已裁决）

问题：上游的触发条件是 `on: push: tags: ["v*"]`，而本仓库的发布 tag 是 `fnos-X.Y.Z`。若原样保留，
推 `fnos-1.6.19` 不会启动这个 workflow，「tag 必须等于 `wb_proxy.py` 里的源码版本」这条断言
对我们的发布 tag 实际上不会运行，只在历史 `v*` tag 上生效（发布包那时只由
`build-fpk.sh --print-version` + `build-fpk.yml` 的门核对）。

三个选项：① `on.push.tags` 加 `"fnos-*"`；② 保持不动、接受上面那个洞；③ 把 tag↔源码版本的比较
搬进 `build-fpk.yml`。

**Lead 裁决（2026-10-10，组装时执行）：取 ①。** `tests.yml` 的 `on.push.tags` 现在是
`["v*", "fnos-*"]`，`tests/_test_release_engineering.py::test_tests_workflow_asserts_tag_against_source`
也改成同时断言两个名字（原来钉的是 `tags: ["v*"]`）。理由：这道门的意义就是「一个发布不能带
与代码不符的 tag」，而本仓库真正会推的发布 tag 正是 `fnos-*`；只留 `v*` 等于让这道门对我们自己
的发布永不生效。代价（下次合并上游时那一行可能冲突）是已知且可解的：冲突就取两边的并集。
