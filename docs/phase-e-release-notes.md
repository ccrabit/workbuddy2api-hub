# WorkBuddy2API-Hub v1.6.17.1

飞牛（fnOS）原生应用包 + 网关免密修正版本。基于上游 `v1.6.17`（以及它之后的 6 个提交）构建，本层只加飞牛网关接入与打包，重复能力一律以上游实现为准。

## 这个版本有什么

### 1. 飞牛 fnOS 原生应用包

- 产出 `WorkBuddy2API-Hub_1.6.17.1_all.fpk`，可以直接在飞牛应用中心安装、升级、卸载（沙箱里按应用中心的真实目录形状与调用顺序演练过整条 install → start → 导入账号 → upgrade → stop → uninstall 路径）。
- 产品名统一为 **WorkBuddy2API-Hub**（App Center 显示名、看板标题、Release 标题、CI 产物名都叫这个），但应用标识 **`appname` 仍是 `workbuddy2api`**。
  - 这不是笔误：`appname` 决定应用目录 `/vol1/@appcenter/workbuddy2api/`、数据目录 `/vol1/@appdata/workbuddy2api/`、unix socket 路径和网关前缀 `/app/workbuddy2api`。改掉它等于另起一个新应用，老用户的数据会留在旧目录里读不到，入口地址也会变。所以「给人看的名」改了，「给系统看的标识」不动。

### 2. 应用中心统一网关里免密打开看板（口径修正）

应用中心把应用挂在前缀 `/app/workbuddy2api` 下、用 iframe 打开看板，请求走 `app.sock`。

- **旧行为的问题**：只有当请求带上 `X-Trim-Username` 才被认为已登录，而这个头由飞牛的会话注入；会话老化后不再注入 → 已经登录飞牛的人被弹回面板口令框。
- **现在的口径**：unix socket 上只要对端（peer uid）校验通过（uid 0 = 网关，或应用自身 uid）就视为已登录，**不再要求 `X-Trim-Username`**；该头只用来显示用户名，没带就只显示入口提示。
- **没有放松边界**：直连 TCP 端口仍然要面板口令；伪造该头的非网关 uid 仍然被拒绝。
- 看板同时适配了挂载前缀：页面用 `<base href>` 与 `window.__WB_BASE__` 把静态资源和接口请求都打在网关前缀上。

### 3. 看板增强

- token 单位按量级自动切换（K / M），大数字不再挤成一串。
- 模型矩阵新增「**每 M tokens 积分**」列，把积分消耗折算成可比单价，方便横向比模型。
- **cockpit 兼容导出**：`POST /accounts/export`，`format=native|cockpit`。cockpit 产物是裸数组 + snake_case OAuth 行，供外部工具直接消费；`GET /accounts/export` 保持原行为不变。

### 4. 上游整合

并入上游 `v1.6.11` – `v1.6.17` 以及 `v1.6.17` 之后的 6 个提交（合并提交 `9dff35f`），包含 Claude Code 兼容、临期积分优先分派、用量统计性能、账号熔断降权、时序图与导航等改动。与上游重复的功能一律以上游实现为准。

## 文件与校验

| 项 | 值 |
|---|---|
| 文件 | `WorkBuddy2API-Hub_1.6.17.1_all.fpk` |
| 大小 | 412737 字节（403.1 KiB） |
| sha256 | `5edc6c972e206181b4efeb49fd1c804a5ccb232b6c63a0ce5ed76498d64bbc27` |
| 包内 `app.tgz` 的 md5（即 `manifest` 里声明的 `checksum`） | `7d66e48d4d7738192c0cf7499eb06666` |
| 旁置校验文件 | `WorkBuddy2API-Hub_1.6.17.1_all.fpk.sha256` |

校验：`sha256sum -c WorkBuddy2API-Hub_1.6.17.1_all.fpk.sha256`，或直接与上表比对。

## 安装 / 升级

1. 在飞牛应用中心里选择「手动安装」，上传 `.fpk` 即可。已经装过本应用（设备当前为 `1.6.17.1`，同版本覆盖安装走的也是同一条路径；更早的 `1.6.10.x` 直接覆盖升级）时，应用目录与数据目录**都不变**。
2. 覆盖安装前建议先备份数据目录 `/vol1/@appdata/workbuddy2api/`（账号池、用量、定价缓存、设置都在这里）。升级本身不会清数据，但**升上去之后没有一键回退**，备份是唯一的后悔药。
3. 卸载时卸载向导会问是否删除数据，默认**保留**——除非你明确要清空。
4. 装好后从应用中心打开，或直接访问统一网关入口（前缀 `/app/workbuddy2api`）。面板端口仍是 `8788`。

## 验证数字

- 测试套件：`python3 tests/run_all.py --jobs 4` → **86 passed / 0 failed / 0 skipped**（新增 `tests/_test_release_pipeline.py`，8 项：四段 tag 定版、CI 当时的混合 tag 集合仍按 HEAD tag 定版、只有 release tag 的 shallow clone 仍报该 tag、alpha 与无 tag 仍能报版本、构建 workflow 传 `VERSION` 并断言、同步 workflow 镜像上游 tag、冲突路径在 Issues 关闭时仍然大声失败）。
- 包级验收：`bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk` → **71 passed / 0 failed**（含包身份三处一致、模块完整性、四个禁止目录、包内 `server/**` 与仓库逐字节一致，以及带/不带 `X-Trim-Username` 两种免密形态）。
- Phase E 独立验收清单（含平台预演与发布流水线复核）：**PASS = 261 / FAIL = 0 / SKIP = 2**（两条 SKIP 是「本机没有 AF_UNIX / 不是 root」这类环境项，非缺陷）。

## 已知限制

- **真机上的移动端渲染没有逐项验证**：布局自适应用的是沙箱里的浏览器等价复现，窄屏观感请在真机上再看一眼。
- **每日同步此前没有成功跑过一次**：2026-10-06 / 10-07 / 10-08 三次定时 run 全红，三次都是上游与飞牛层在同一批文件上**真实冲突**（`README.md`、`dashboard.html`、`tests/run_all.py`、`wb_proxy.py`）——按设计中止合并、交人裁决；而当时的冲突上报依赖 issue，仓库 **Issues 是关的**，`gh issue create` 直接失败，于是只剩一条没有任何解释的红 run。现在冲突路径不再依赖 Issues（见下节），但**冲突本身仍然要人工合并**：上游动到我们改过的文件，当天的同步就会停下，这正是「绝不在同步流程里自动解决冲突」的代价。
- **仓库 Issues 仍未启用**（Lead 的 token 没有仓库设置权限，勾选由仓库所有者做）：在此之前冲突以 `::error::` 注解 + 此次 run 的 summary（含冲突文件清单与手工合并命令）报出，不会静默；勾上之后同一段代码会自动开始建 issue，不需要再改 workflow。
- **日志窗口维持上游的终端配色**，未按看板主题适配。
- 版本号规则：上游出 `v1.6.18` 之后基线整体上移为 `1.6.18.x`，`1.6.17.x` 不会越过它。
- `appname` 不能改（见上），本版不提供改名迁移方案。

## 与上游的关系

本 fork **不是镜像**。默认分支上除了上游代码，还带着飞牛这一层（`fnos/**`、网关免密与挂载前缀改动、打包脚本、看板增强），因此上游一旦改动这些文件就会产生冲突。

冲突**绝不在同步流程里自动解决**：任其失败、开/更新 issue 交给人裁决，宁可这条同步 run 红掉，也不推一个半合并的仓库出去。standing rule 是「重复能力上游优先，飞牛层只保留上游没有的部分」。

## 发布流水线与版本命名（本次重新发布 `v1.6.17.1` 起）

`v1.6.17.1` 这一版暴露了一个只看单机看不出来的问题：**同一个提交在不同环境算出两个版本号**。

- 事故：tag `v1.6.17.1` 在 CI 里构建出的包叫 `1.6.10.3`（Release `407525712`，附件 `WorkBuddy2API-Hub_1.6.10.3_all.fpk`，411262 字节）。CI 日志原文 `==> building WorkBuddy2API-Hub (appname workbuddy2api) 1.6.10.3 (all) for ccrabit`。
- 根因：`scripts/build-fpk.sh` 原来把版本派生自「本 checkout 能看到的最新上游三段 tag」。本机 fetch 过上游的 `v1.6.17` 所以算对；CI 全新 checkout 只看到 fork 自己的 tag（origin 上只有 `v1.0.0` … `v1.6.10`、`v1.6.10.1/.2` 和我们的 `v1.6.17.1`），最新三段 tag 是 `v1.6.10` → 第四位 3 → `1.6.10.3`。这个号比设备已装的 `1.6.17.1` 还小，装了会被当成降级。
- 三条修复：
  1. `scripts/build-fpk.sh`：**HEAD 上的四段 tag 就是版本号**（release 模式第一优先，`v1.6.17.1` → `1.6.17.1`），不再问「本 checkout 看得到哪些远端 tag」；没有 tag 时才按旧规则派生，再退到 `fnos/manifest` 的 `version=`。alpha 模式行为不变。
  2. `.github/workflows/build-fpk.yml`：tag 触发时把 tag 显式作为 `VERSION` 传下去，并先跑 `--print-version` 与 tag 比对，不一致就 `::error::` + 非零退出，**拒绝发布一个 tag 名不出来的包**。
  3. `.github/workflows/sync-upstream.yml`：每次同步（不止发布那一次）把上游的三段 tag 全部镜像到 origin，这样任何 checkout 都能看到基线 tag；头部注释里那句「tag 与包版本总是一致」已改成它成立的前提。
- 顺带修：冲突路径原本只靠 `gh issue create` 报信，而仓库当时 **Issues 是关的**，于是 10-06 至 10-08 三次同步全红却一条 issue 都没有（`GraphQL: Resource not accessible by integration (createIssue)`）。现在这条路径**不依赖 Issues 是否打开**：先 `gh api … --jq .has_issues` 判断，开着就照旧建/更新 issue；关着（或建 issue 仍被拒）就输出 `::error::` 注解，并把冲突文件清单与手工合并命令写进该次 run 的 summary，然后照样非零退出。**要拿回 issue 那一半，只需在 Settings → General → Features 里把 Issues 勾上**，这一步会自动开始建 issue；至少不会再出现「红了但没人知道为什么」。
- 回归门：新增 `tests/_test_release_pipeline.py`，覆盖两种环境——① 复现 CI 当时的 tag 集合（三段 tag 只到 `v1.6.10`，另有 `v1.6.10.1/.2`，HEAD 上是 `v1.6.17.1`）：未修代码在此报 **`1.6.10.3`**，与 CI 日志逐字一致；② `git clone --depth 1 --branch v1.6.17.1` 的 shallow clone（除该 tag 外什么都看不见）：未修代码回落到 `fnos/manifest` 报 **`1.6.10`**。两种环境修后都必须报 `1.6.17.1`。另有静态断言盯住构建 workflow 的 `VERSION` 传递与相等断言、同步 workflow 的 tag 镜像、以及冲突路径的 `has_issues` / `::error::` / run summary / 中止前读取冲突路径。**修脚本前该套件 6 红，修后 8 项全绿。**
- 本次 Release 的处理：`v1.6.17.1` 这个 tag 被**重指到修好流水线的提交**，用修复后的流水线重新构建，并删掉那个 `1.6.10.3` 的错包附件。重指前核对过两件事：① 错包与本机包的 payload **26 个文件逐文件 md5 完全相同**（差别只有 `manifest` 的 `version`/`checksum` 两行，以及 tar 成员时间戳带来的字节差），② 新旧提交在 `dashboard.html`、`wb_proxy.py`、`fnos/**`、`pricing`、`LICENSE` 上**没有差异**——所以这个 Release 里的代码和你设备上已经装的那份是同一份，重新下载不会改变行为。包名与版本号保持 `1.6.17.1`，不需要卸载重装。
