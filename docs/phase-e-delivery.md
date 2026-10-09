# Phase E 交付说明（飞牛 fnOS 原生包 1.6.17.1）

> 本阶段交付物：`dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk` + 本文档。
> **未提交、未打 tag、未推远端、设备未动**（设备上仍跑 `1.6.10.11`）。本包是测试包，未经真机安装验证。

## 1. 包指纹

| 项 | 值 |
|---|---|
| 文件 | `dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk` |
| 字节数 | `412737`（403.1 KiB） |
| sha256 | `5edc6c972e206181b4efeb49fd1c804a5ccb232b6c63a0ce5ed76498d64bbc27` |
| manifest `checksum`（app.tgz md5） | `7d66e48d4d7738192c0cf7499eb06666`（注意：这是**包内 `app.tgz`** 的 md5，`manifest` 里声明的就是它；fpk 文件本身的 md5 是 `d45e598420425a9f992895445f3ef1ff`） |
| 旁置校验文件 | `dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk.sha256`（内容即上面的 sha256 + 文件名两列） |
| 版本 | `1.6.17.1`（= 上游最新三段 tag `v1.6.17` + 本基线第四个发布号 `1`） |
| 平台 | `all` |
| distributor | `ccrabit`（取自 `origin` owner；`PACKAGER` 可用环境变量覆盖） |

构建与校验命令：

```bash
bash scripts/build-fpk.sh                     # 产出 dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk（+ .sha256）
bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk
```

校验结果：`bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk` → **71 passed, 0 failed**（`PASS`/`FAIL` 计数，末尾打印，有 FAIL 即退出码 1）。包内 `manifest` 的 `version` 实测为 `1.6.17.1`、`display_name` 为 `WorkBuddy2API-Hub`、`appname` 为 `workbuddy2api`（构建时由脚本覆盖 `1.6.10`，verify 有断言）。

## 2. 命名：产品名改、appname 不改

| 类别 | 值 |
|---|---|
| 产品名（给人看） | **WorkBuddy2API-Hub** —— manifest `display_name`、`ui/config` 的 `title`、`.sc` 的 `title`/`desc`、fpk 文件名、Release 标题、CI artifact 名 |
| 标识符（给系统看） | `workbuddy2api` —— manifest `appname`、`WorkBuddy2API.sc` 文件名与 `[WorkBuddy2API]` 段名、`TRIM_APPNAME`、`workbuddy2api.Application`、网关前缀 `/app/workbuddy2api` |

**appname 为什么必须保持 `workbuddy2api`**：它决定应用目录 `/vol1/@appcenter/workbuddy2api/`、数据目录 `/vol1/@appdata/workbuddy2api/`、unix socket 路径与网关前缀。改了等于另起一个新应用，老用户的数据留在旧目录里读不到，入口地址也会变。构建脚本与 verify 脚本都会断言这两者，防止后来者手滑。

## 3. 安装与备份提醒

- 本包**没有装到设备上**。安装属于设备写操作，本阶段明令不做；要装请由人显式执行。
- 设备现状（只读记录）：应用 `/vol1/@appcenter/workbuddy2api/`、数据 `/vol1/@appdata/workbuddy2api/`、socket `/vol1/@appcenter/workbuddy2api/app.sock`、端口 `8788`、网关前缀 `/app/workbuddy2api`；在装版本 `1.6.10.11`（**小于**本包 `1.6.17.1`）。
- 覆盖安装前先备份数据目录：`/vol1/@appdata/workbuddy2api/`（账号池、usage、pricing.json 都在这里）。升级路径在沙箱里演练过（install → start → 导入账号 → upgrade → stop → uninstall 两分支），但**真机升级不可回退**，备份是唯一的后悔药。
- 卸载会走 `wizard/uninstall` 的「保留数据」分支——除非你明确选删除数据。

## 4. 本阶段交付的功能

1. **上游 v1.6.17 同步**：合并上游 `v1.6.17` 及其后 6 个提交（合并提交 `9dff35f`），重复能力以上游为准。
2. **飞牛网关免密口径（本仓库这一层）**：走网关 unix socket 时，只要 peer 校验通过（uid 0 = 网关，或应用自身 uid）即视为已登录，**不再要求 `X-Trim-Username`**；该头只用来显示用户名，没带就只显示入口提示。直连 TCP 端口仍然要求面板密码，伪造头（非网关 uid）仍然拒绝。
3. **挂载前缀支持**：看板在 `/app/workbuddy2api/` 下通过 `<base href>` 与 `window.__WB_BASE__` 把请求都打在网关前缀上。
4. **cockpit 兼容导出（WP-E5，我们独有的增量）**：`wb_export.py`（新）+ `POST /accounts/export`（`format=native|cockpit`，缺 `format` → 400），cockpit 产物是裸数组 + snake_case OAuth 行；`GET /accounts/export` 保持上游行为逐字节不变。看板入口由 WP-E6 提供。
5. **上游新模块进包**：`wb_pricing.py`、`wb_atrest.py`、`wb_modelsdev.py`、`wb_prompt.py`、`wb_ipintel.py`、`wb_probes.py`、`wb_catalog.py`、`wb_fingerprint.py`、`wb_identity.py`、`wb_webagent.py`、`wb_webtools.py`、`wb_export.py` 与 `pricing/pricing.json` 全部随包；源码 `docs/`、`tests/`、`accounts/`、`usage/` **不进包**。
6. **打包与校验脚本强化**：包身份（文件名/版本/manifest/界面三处一致）、载荷模块完整性（按工作树推导，上游加模块自动跟上）、四个禁止目录逐个断言（`accounts/`、`usage/`、`tests/`、`docs/`）、包内 `server/**` 与仓库逐字节一致、两种免密形态的沙箱回归。
7. **CI 适配新树**：`build-fpk.yml` 的 Release 标题与 artifact 名改用产品名；`sync-upstream.yml` 明确「本 fork 不是镜像，冲突绝不自动解决」策略。
8. **文档**：`README.md` 新增飞牛包章节与 changelog 条目（套件数按扫盘实测回填）；`fnos/README.md` 补命名说明、版本规则、免密真值表与断言数。

## 5. 测试路线

```bash
python3 tests/run_all.py --jobs 4                     # 全量套件
bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.6.17.1_all.fpk   # 包级验收（71 项断言）
```

- `scripts/verify-fpk.sh` 在 `mktemp` 沙箱里按飞牛 appcenter 的真实目录形状解包、启动、导入账号、升级、停止、卸载，并额外做包身份/载荷/逐字节核对。
- 免密两项：`real_gateway_signon`（带 `X-Trim-Username`）与 `real_gateway_signon_without_session_header`（**不带**该头）都要求 `200 + via_gateway + authenticated`。
- 逐字节一致性会列出前几个漂移文件名；**先让所有写者停笔，再构建最终包**，否则必然漂移（演练时踩过一次：构建后 `dashboard.html` 又被改）。

## 6. 已知限制

- 设备上仍是 `1.6.10.11`，本包**未在真机装过**；真机免密 E2E 是按 `AF_UNIX` + 应用目录形状在沙箱里等价复现的。
- 版本第四位规则：上游出 `v1.6.18` 后基线整体上移，`1.6.17.x` 不会超过 `1.6.18.1`；`sync-upstream.yml` 每天自动把上游并进默认分支，**冲突时中止并由人裁决，standing rule 是上游优先**。
- appname 一旦改动即等于换应用（见 §2），本阶段不做迁移方案。
- Phase D 的超集功能（任务中心队列、事件链、模型锁池、积分构成 FEFO 明细等）仍留在 `phase-d/snapshot`，不在本包内；唯一被移植回来的是 cockpit 兼容导出（WP-E5/E6，见 §4.4）。
