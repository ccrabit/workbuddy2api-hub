# Phase F · WP-F4：FnDepot 上架材料与路径说明

任务：`task-24`（owner `credits-engine`）· 工作树 `/tmp/wb-f4`（branch `phase-f/fndepot`）
规格：`docs/phase-f-plan.md` §1.6（FnDepot 要求）+ §2.1（版本契约：本次版本键 `1.6.19`）
权威原文：中心仓库 `EWEDLCM/FnDepot` 的 README「外部应用源 V2 编写说明」与 `scripts/generate_sources.py`
（本地取证副本 `/tmp/fndepot/`，本机日期 2026-10-10）

---

## 1. 交付物

| 文件 | 字节 | 用途 |
| --- | --- | --- |
| `fnpack.json` | 1758 | 仓库根目录的 V2 源文件（客户端只认这个文件名与大小写） |
| `fndepot/ICON.PNG` | 7666 | 应用图标，`fnos/ICON_256.PNG` 的逐字节副本（256×256 PNG，< 500KB） |
| `fndepot/README.md` | 4940 | 给用户看的安装说明（添加源 / 打开 / 首次使用 / 升级卸载 / FAQ） |
| `tests/_test_fndepot_source.py` | 19214 | 离线校验（含直接 import 中心仓库的校验器） |
| `docs/phase-f-fndepot-submission.md` | 本文档 | 上架机制、我们的处境、建议路径、占位替换清单 |

本版 `fnpack.json`（含占位数字）sha256 = `6aefbbbd198e07208e9ca6901bc91a23c72b5675b68689f5654254fccd5d9e0e`。
替换 sha256/size 之后这个值必然变化，它是「被审过的这一版」的指纹，不是发布指纹。

图标用的是 `fnos/ICON_256.PNG`（256×256，比 `fnos/ICON.PNG` 的 64×64 更耐放大），副本名按规范与中心仓库
习惯写成 `ICON.PNG`。**没有预览图**：手上没有真实截图，规范说最多读 8 张，我们就省略 `preview_urls`，
不编造（`fndepot/Preview/` 留空，将来有真图再加）。

## 2. 「上架」到底是怎么发生的（取证结论）

### 2.1 用户侧两种添加方式（不依赖任何收录机制，今天就能用）

1. **GitHub 仓库根地址**：客户端读**默认分支根目录**的 `fnpack.json`，文件名大小写必须完全正确，
   不探测 `fndepot.json` 之类的别名；API 不可用时兼容试 `main`/`master`。
2. **JSON 直链**：任意文件名的 HTTP/HTTPS JSON（结构符合 V1/V2 即可）。

外链 URL 只允许 `http`/`https`；仓库模式读不到文件就是源同步失败。

### 2.2 自动收录（`valid_sources.txt`）

中心仓库的 `.github/workflows/update-sources.yml` 每天 **`0 16 * * *`（16:00 UTC = 北京 00:00）**
跑 `scripts/generate_sources.py`（`GITHUB_TOKEN`=`secrets.MY_PAT_TOKEN`），把合格仓库写成根目录的
`valid_sources.txt`；当前 62 条。名单同时是官方客户端的「外部源推荐列表」，所以进名单 ≈ 被人看到。

**召回（三条，取并集）**，见 `generate_sources.py:329-360`：

| # | 途径 | 关键限制 |
| --- | --- | --- |
| 1 | 仓库搜索 `fndepot` / `fn depot`（每词 ±`fork:true`，各 3 页 × 100） | 脚本只保留 **`full_name` 里含 `fndepot`** 的仓库；**描述/topic 里含不算**（`generate_sources.py:344`） |
| 2 | 代码搜索 `filename:fnpack.json`（±`fork:true`） | **只取第一页 100 条**（`generate_sources.py:353-357`） |
| 3 | 脚本里的 `WHITELIST` | **当前为空**（`generate_sources.py:21-22`） |

**质检（进名单的硬门槛）**，`generate_sources.py:197-258`：

- 仓库 **6 个月内必须有过 push**（`DEAD_REPO_MONTHS = 6`，`generate_sources.py:14, 206-211`），否则判「死仓库」；
- 根目录 `fnpack.json` ≤ 2 MB（`MAX_FILE_SIZE`），UTF-8 可 `json.loads`；
- `parse_and_fingerprint()` 通过：`schema_version` 必须是 `"2"`（数值 `2` 也过，因为比的是 `str(value)`）；
  `source_info.name`/`author` 非空；`author` 不得冒名（`FORBIDDEN_AUTHORS = {"fndepot"}`）；`apps` 非空且 ≤ 5000；
  **且至少有一个应用能过 `validate_v2_app()`**（全不过 → 整源剔除，`generate_sources.py:190-193`）。
- `BLACKLIST` 当前一条：`Brian099/fn_fpk_packages`。

**查重（血缘 + `appname|version` 重叠）**，`generate_sources.py:260-323`：

- 重叠率分母是**较小集合**；名称指纹 = `app_key.lower().replace(" ","")`，版本指纹 = `name|版本`（去掉前导 `v`）；
- 血缘判定：一方 `parent.full_name` 是另一方，或两者同父 → 「血缘」；
- 「血缘」门槛：名称重叠 ≥ 50% **或** 版本指纹重叠 ≥ 30%；非血缘门槛：名称 ≥ 85% **且** 指纹 ≥ 70%；
- 淘汰规则：**血缘对里 Fork 永远输给非 Fork**；否则 **`created_at` 更晚的输**。

### 2.3 一条重要的现实观察

现有 62 条里 59 条的仓库名**就叫 `FnDepot`**（`https://github.com/<user>/FnDepot`），个别名字不含
「fndepot」的（`RROrg/fn-apps`、`rockchild2332/fnos-apps-fndepot`、`jiumian8/jiumianFnDepot`）只能靠
代码搜索那条进来。**也就是说：名字含 `fndepot` 几乎是进名单的充分条件，而代码搜索是又窄又不透明的后门。**

另外，中心仓库自己的 `fnpack.json` 只放作者自己的应用（`fntermx`/`flatcms`/`flatnas`/`picoclaw`），
第三方**不走 PR 进中心源**，只可能进 `valid_sources.txt`。所以我们**不需要**（也不应该）给中心仓库提 PR。

## 3. 我们的处境：三个不利条件

| 条件 | 事实 | 后果 |
| --- | --- | --- |
| 仓库名 | `ccrabit/workbuddy2api-hub` 含「workbuddy」不含「fndepot」 | 召回第 1 条**必然不中** |
| Fork 身份 | 它是上游 `ardeyouxipianyi/workbuddy2api-hub` 的 fork | ① 代码搜索默认不索引 fork，要靠 `filename:fnpack.json fork:true` 那条查询才可能被搜到；② 一旦上游也发布同名 `appname|version` 的 FnDepot 源，血缘查重里 **Fork 永远输** |
| 活跃度 | 判死仓库线是 6 个月 | 长期不发版就会被踢出下一次名单 |

结论：**只在 `ccrabit/workbuddy2api-hub` 根目录放 `fnpack.json`，自动收录基本靠运气**；但对「用户手动添加
仓库地址/JSON 直链」这条路径是完全够用的，而且这条路径不依赖中心仓库任何机制。

## 4. 建议路径

### 路线 A（推荐）：另建一个非 fork、名字含 `fndepot` 的仓库

例如 `ccrabit/WorkBuddy2API-FnDepot`（放在自己的账号下，**不是 fork**），内容就是本 WP 的
`fnpack.json` + `fndepot/**`；**FPK 不入 git**，`download_url` 用主仓库 Release 资产的绝对 URL。
这样：命中召回第 1 条（名字含 fndepot）、没有 fork 血缘判负、6 个月活跃要求只要两个仓库都保持活跃即可。
代价：多一个仓库要维护，版本发布时两处都要更新（`fnpack.json` 与 Release）。

> 这是**用户动作**，不是我们能自己做的：`docs/phase-f-plan.md` §2.4 已记录，我们的 PAT 是细粒度且无
> administration 权限（建仓库、改 `has_issues` 都是 403）。

### 路线 B（兜底，且可以现在就成立）：用户手动添加

把 `fnpack.json` 留在主仓库根目录，用户在 FnDepot 里添加：

```text
https://github.com/ccrabit/workbuddy2api-hub          # 仓库根地址（默认分支根目录有 fnpack.json）
https://raw.githubusercontent.com/ccrabit/workbuddy2api-hub/main/fnpack.json   # JSON 直链兜底
```

前提两条：① 默认分支（`main`）根目录确实有 `fnpack.json`；② **发布前把占位数字换成实测值**（见 §5）。
这条路径不经过 `valid_sources.txt`，所以不受 fork / 命名 / 6 个月活跃度的任何约束。

### 路线 C：A + B 同时做

主仓库保留 `fnpack.json`（供直链兜底与「用户手输仓库地址」），独立 fndepot 仓库承担自动收录。
两份内容必须一致（同一版本键、同一 URL/哈希），建议发布流程里对两个仓库都跑
`python3 tests/_test_fndepot_source.py`。

## 5. 发布前必须替换的占位（本阶段只出本地测试包，Release 还不存在）

本版 `fnpack.json` 里有 **3 处值需要在正式发布时替换**（第 4 处仅在约定变化时才动）：

| # | 位置 | 当前值 | 替换为 |
| --- | --- | --- | --- |
| ① | `apps.workbuddy2api.releases["1.6.19"].packages.all.sha256` | 64 个 `0` | `sha256sum dist/WorkBuddy2API-Hub_1.6.19_all.fpk` 的输出 |
| ② | 同分支 `.size` | `0` | `stat -c %s dist/WorkBuddy2API-Hub_1.6.19_all.fpk`（字节整数，不能写 `"20 MB"`） |
| ③ | `releases["1.6.19"].updated_at` | `2026-10-10T16:56:21+08:00`（写本材料的时间） | 实际发布时间（带时区偏移的 ISO 8601） |
| ④ | `packages.all.download_url` | `.../releases/download/fnos-1.6.19/WorkBuddy2API-Hub_1.6.19_all.fpk` | 仅当 Release tag 或资产名与约定不同才改 |

替换与自检：

```bash
sha256sum dist/WorkBuddy2API-Hub_1.6.19_all.fpk
stat -c %s dist/WorkBuddy2API-Hub_1.6.19_all.fpk
python3 tests/_test_fndepot_source.py          # 两条占位 NOTE 消失、FAIL=0 才算替换干净
```

> ⚠️ **替换前不要把这份 `fnpack.json` 交给用户添加**：规范说 `sha256` 「存在时客户端强制校验」，
> 全 0 会让下载完的 FPK 校验失败、安装直接报错。
> 如果确实要先发一版给用户试，正确做法是**删掉** `sha256` 与 `size` 两个键（规范里它们是「强烈建议」，
> 不是必填），等实测值出来再补回来。注意：删键会让 `tests/_test_fndepot_source.py` 的 [6] 段变红
> （那里无条件断言两个键存在且格式合法），所以删键要连同测试一起改，并在这里记一笔。

## 6. 验收对照（`docs/phase-f-plan.md` §4.6）

| 要求 | 状态 | 证据 |
| --- | --- | --- |
| 通过中心仓库 `validate_v2_app()` / `parse_and_fingerprint()` | ✅ 已跑 | `python3 tests/_test_fndepot_source.py` → `using centre repo validator: /tmp/fndepot/generate_sources.py`，`PASS=77 FAIL=0 SKIP=0`；指纹 = `{workbuddy2api}` / `{workbuddy2api|1.6.19}` / 源版本 `v2` |
| `download_url` 可访问 | ⏳ 待 Release | 本阶段不推 origin、不发 Release，URL 指向将来的 `releases/download/fnos-1.6.19/…` |
| `size` = 实际字节数、`sha256` 与文件一致 | ⏳ 待 Lead 的包 | 见 §5，数字由 Lead 构建 `dist/WorkBuddy2API-Hub_1.6.19_all.fpk` 后给出 |

## 7. 需要 Lead / 用户决策的点

1. **建独立 fndepot 仓库**（路线 A）——需要用户操作（PAT 无 administration 权限）。
2. **是否发布 `fnos-1.6.19` Release**并给出实测 `sha256`/`size`；给出后我 5 分钟内替换并复跑测试。
3. **Issues 是否打开**：`bug_report_url` 指向 `ccrabit/workbuddy2api-hub/issues`，但该仓库的 Issues 需要
   用户在 Settings → General → Features 里打开（同样是 403 约束）。
4. **预览图**：要不要补真截图（补了再填 `preview_urls`，最多 8 张；没真图就保持省略）。
5. `fnos/manifest` 的 `version` 目前是 `1.6.10`，而 FnDepot 版本键按 §2.1 固定为 `1.6.19`。测试对这条
   只打 NOTE（构建脚本会注入版本，`fnos/manifest` 不归我改）。如果 Lead 期望两处字符串一致，需要
   packager/Lead 在自己的写域里处理。

## 8. 本 WP 没做、也不该做的事

- 没 commit、没 push、没打 tag、没发 Release（`docs/phase-f-plan.md` §2.4）。
- 没碰 `README.md`、`wb_proxy.py`、`dashboard.html`、`scripts/`、`.github/`、`fnos/**`。
- 没给中心仓库提 PR、没跑 `generate_sources.py` 的 `main()`（它需要 PAT 且会发网络请求）。
- 没有伪造截图、没有伪造 sha256/size（占位值可以一眼认出，并且已列进 §5 的替换清单）。
