# Phase G · WP-G4 — FnDepot 源仓库内容（`ccrabit/FnDepot`）

规格：`docs/phase-g-plan.md` §2 G-D5、§4.5。owner：credits-engine。日期：2026-10-11。
**状态：源内容已就绪并通过中心仓库校验器；仓库尚未创建，等 classic token 后由 Lead 建仓并推送。**

---

## 1. 交付物（暂存目录 `/tmp/fndepot-src/`）

这是新仓库 `ccrabit/FnDepot`（非 fork、公开）的**根目录**内容，逐字节可直接推送：

| 文件 | 字节 | sha256 |
|---|---|---|
| `fnpack.json` | 2056 | `730bc97e1002c8bae5623ff23f0492b6708db21a7eec2b61521469ac86513cd9` |
| `ICON.PNG` | 7666 | `bccc12d59a41f36d3c2b0c721a6ad1dae35a09e3f574cd7973a39c4fa009b403` |
| `README.md` | 2191 | `add8011d210f7dfcae7c84b1f7516e7c8a11d1fce82446849a12e79d61c26b2d` |

- `ICON.PNG` = 主仓库 `fndepot/ICON.PNG` 的逐字节副本（= `fnos/ICON_256.PNG`，256×256 PNG，7666 B，远低于中心仓库建议的 500 KB）。
- `README.md` = 面向飞牛用户的简体中文安装说明（430 个汉字），四节：这是什么 / 安装与打开 / 导入账号 / 常见问题，另附源码与反馈链接。**不含任何未实现的承诺**。
- `fnpack.json` = 本源的唯一清单文件，V2 结构，只有一个应用 `workbuddy2api`、一个版本 `1.6.19`。**未放 `preview_urls`**（没有真实截图，不编造；README 里也没有截图引用）。

### 1.1 `fnpack.json` 内容要点

```
schema_version           "2"（字符串，不是数字）          [中心 README:132]
source_info.name         "WorkBuddy2API-Hub FnDepot 源"
source_info.author       "ccrabit"                       ← 本源维护者，非 FnDepot/官方
source_info.homepage     https://github.com/ccrabit/workbuddy2api-hub
apps.workbuddy2api       键 == FPK manifest 的 appname（逐字符，区分大小写）
  display_name           "WorkBuddy2API-Hub"             == fnos/manifest display_name
  desc                   账号池网关 + 统一网关免密入口 + 看板（中文）
  platform               ["all"]                         单包多架构
  categories             ["AI赋能","系统工具"]            首项=主分类，共 2 项（≤2）
  icon_url               "./ICON.PNG"                    相对 JSON 所在地址
  readme_url             "./README.md"
  bug_report_url         https://github.com/ccrabit/workbuddy2api-hub/issues
  maintainer(_url)       ardeyouxipianyi（上游作者）
  distributor(_url)      ccrabit（本源发布者）
  run_as                 "package"                       == fnos/config/privilege defaults.run-as
  install_type           ""（存储空间）
  is_docker              false（布尔）
  service_port           "8788"
  releases["1.6.19"].packages.all.download_url
      https://github.com/ccrabit/workbuddy2api-hub/releases/download/fnos-1.6.19/WorkBuddy2API-Hub_1.6.19_all.fpk
      sha256  e65dcb844df7ede523e990c33e3e661e27d6c73e0a9770592d76e006d610505d
      size    626248
  releases["1.6.19"].updated_at  2026-10-11T00:40:00+08:00
```

`sha256`/`size` 是 **task-32 重建并覆盖后的真实资产值**（不是占位），与主仓库根 `fnpack.json` 完全一致。

---

## 2. 中心仓库校验器实跑输出（原文）

命令：

```bash
GITHUB_TOKEN=offline-verify python3 /tmp/fndepot-verify.py
```

（脚本用 `importlib` 直接加载中心仓库的 `/tmp/fndepot/generate_sources.py`，只调它的 `is_forbidden_identity()` / `validate_v2_app()` / `parse_and_fingerprint()`，**没有另写一套校验逻辑**；该模块在导入时 `GITHUB_TOKEN` 缺失会 `exit(1)`，所以给一个假值。）

```text
validator module : /tmp/fndepot/generate_sources.py
json.load        : OK
schema_version   : '2' type = str
apps keys        : ['workbuddy2api']
required fields present: True
is_forbidden_identity(author           = 'ccrabit'           ) = False
is_forbidden_identity(maintainer       = 'ardeyouxipianyi'   ) = False
is_forbidden_identity(distributor      = 'ccrabit'           ) = False
is_forbidden_identity(source_info.name = 'WorkBuddy2API-Hub FnDepot 源') = False
validate_v2_app  : (True, 'ok')
parse_and_fingerprint:
  is_valid       : True
  names          : {'workbuddy2api'}
  sigs           : {'workbuddy2api|1.6.19'}
  source_ver     : v2
files:
  ICON.PNG         7666 B  sha256=bccc12d59a41f36d3c2b0c721a6ad1dae35a09e3f574cd7973a39c4fa009b403
  README.md        2191 B  sha256=add8011d210f7dfcae7c84b1f7516e7c8a11d1fce82446849a12e79d61c26b2d
  fnpack.json      2056 B  sha256=730bc97e1002c8bae5623ff23f0492b6708db21a7eec2b61521469ac86513cd9
README.md CJK chars: 430
RESULT: all_validator_checks_ok = True
```

`validate_v2_app()` = **True**、`parse_and_fingerprint().is_valid` = **True**（题目要求的 `True/True`）。
`python3 -c "import json;json.load(open('/tmp/fndepot-src/fnpack.json'))"` 通过（严格 JSON、无注释、无尾逗号、无 BOM）。

### 2.1 类型与取值逐条对照（实跑）

```text
== 与 FPK manifest 交叉 ==
apps 键 'workbuddy2api'  == manifest.appname 'workbuddy2api'  -> True
display_name 'WorkBuddy2API-Hub' == manifest.display_name 'WorkBuddy2API-Hub' -> True
service_port '8788'             == manifest.service_port '8788' -> True
run_as       'package'          == privilege.defaults.run-as 'package' -> True

== 类型/取值逐条对照 ==
  schema_version '2'                    str=="2"                           OK
  platform       ['all']                list⊆{all,x86,arm} 非空              OK
  categories     ['AI赋能', '系统工具']       list⊆九类, 1..2 项, 首项主分类             OK
  install_type   ''                     str ∈ {"","root"}                  OK
  run_as         'package'              str ∈ {package,root}               OK
  is_docker      False                  bool                               OK
  service_port   '8788'                 str                                OK
  icon_url       './ICON.PNG'           相对 ./ + 文件存在                       OK
  readme_url     './README.md'          相对 ./ + 文件存在                       OK
  preview_urls   None                   省略(无真实截图)                          OK
```

九类白名单（中心 README:189-197）：影音娱乐、系统工具、编程开发、AI赋能、生活服务、智能智控、教育学习、游戏地带、硬件驱动 —— 我们用的两项都在其中，且不含「全部」。

---

## 3. 已发布资产的独立复核（sha256 / size 是可信锚）

不看任何人的口头结论，直接读 GitHub API（只读）：

```text
tag_name : fnos-1.6.19 | id: 408987082 | draft: False | published: 2026-10-10T14:03:36Z
asset    : WorkBuddy2API-Hub_1.6.19_all.fpk           size=626248   digest=sha256:e65dcb844df7ede523e990c33e3e661e27d6c73e0a9770592d76e006d610505d
           url=https://github.com/ccrabit/workbuddy2api-hub/releases/download/fnos-1.6.19/WorkBuddy2API-Hub_1.6.19_all.fpk
asset    : WorkBuddy2API-Hub_1.6.19_all.fpk.sha256    size=99       digest=sha256:9f95041280d56899eb411d333c3755a56e5b79162c0a96db145e47a125f21933
```

`size=626248` 与 `digest=sha256:e65d…505d` 与 `fnpack.json` 里的 `packages.all` 逐字符一致，也与 `browser_download_url` 完全一致 ⇒ 版本键、下载地址、哈希、大小四者自洽。

---

## 4. 与主仓库根 `fnpack.json` 的关系

两处清单**同时存在**，内容 25 个叶子字段里 20 个完全相同，差异只有 5 处，全部是路径/文案类：

| 字段 | 新源仓库 `ccrabit/FnDepot` | 主仓库 `ccrabit/workbuddy2api-hub` |
|---|---|---|
| `apps.workbuddy2api.icon_url` | `./ICON.PNG` | `./fndepot/ICON.PNG` |
| `apps.workbuddy2api.readme_url` | `./README.md` | `./fndepot/README.md` |
| `apps.workbuddy2api.releases.1.6.19.changelog` | 「首个飞牛上架版本…」 | 「同步上游 v1.6.19 及其后 79 个提交…」 |
| `source_info.name` | `WorkBuddy2API-Hub FnDepot 源` | `WorkBuddy2API-Hub 源` |
| `source_info.description` | 「…外部应用源（第三方自建…）」 | 「…外部源（第三方自建…）」 |

两者都指向同一个 Release 资产、同一个 `appname`、同一个版本键 —— **版本升级时要同时改两处**（见 §6 待办）。

---

## 5. 收录判定（靠哪条召回路径、什么时候扫、怎么判）

### 5.1 召回路径

中心仓库扫描器 `/tmp/fndepot/generate_sources.py` 的召回只有两条路：

1. **仓库搜索（`:336-350`）**：4 个 query（`fndepot` / `fn depot` / 各带 `fork:true`）× 最多 3 页 × 100，但**只保留 `full_name` 里含 `fndepot` 的仓库（`:344`）**。
2. **代码搜索（`:353-357`）**：`filename:fnpack.json&per_page=100` 与 `filename:fnpack.json+fork:true&per_page=100`，各只取首页 100 条；`WHITELIST = []`（`:21-22`）。

**我们走的是路径 ①**：新仓库名 `ccrabit/FnDepot` 含 `fndepot`，命中 `:344` 的过滤器。实测（2026-10-11，只读 API）：

```text
repo query 'fndepot'  total_count=99   通过 ':344' 过滤后保留 97 个
repo query 'fn depot' total_count=98   通过 ':344' 过滤后保留 96 个
当前 valid_sources.txt = 62 行；其中含 fndepot 的 61/62，以 /FnDepot 结尾的 59/62
```

即「名字里带 fndepot」几乎是进名单的充分条件，而我们的 `ccrabit/workbuddy2api-hub`（fork、名字不含 fndepot）**不能**依赖这条路。

### 5.2 扫描时间

中心仓库 `.github/workflows/update-sources.yml`：`- cron: '0 16 * * *' # 每天北京时间 00:00 运行` ⇒ **每天 16:00 UTC（次日 00:00 +08）重跑**，产出并提交 `valid_sources.txt`。所以推送内容后最快在下一个 16:00 UTC 之后可见。

### 5.3 判据（收录与否都要如实记录）

下一个 16:00 UTC 之后，用下面两条一起看，并在 `docs/phase-g-fndepot.md` 追加结论：

```bash
# ① 行数是否变化（基线 62 行）
curl -s https://raw.githubusercontent.com/EWEDLCM/FnDepot/main/valid_sources.txt | wc -l
# ② 是否出现我们（这一步是最终判据）
curl -s https://raw.githubusercontent.com/EWEDLCM/FnDepot/main/valid_sources.txt | grep -c 'ccrabit/FnDepot'
```

- 行数变化 **且** `grep` 命中 ⇒ 收录成功（实测时记下新行数）。
- 行数变化但没命中 ⇒ 被**查重剔除**（见 5.4）或 `fetch_repo_data()` 抓取失败（网络/2 MB 上限/仓库 6 个月无活动），要去看中心仓库那次 Actions 的日志确认是哪一种。
- 行数没变 ⇒ 本次扫描没跑到（或 push 尚未生效），等下一个周期再看，不要急着改源内容。

### 5.4 残留风险：与主仓库根 `fnpack.json` 的查重撞车（需 Lead/用户决策）

`process_overlap()`（`:267-323`）的规则是：

- 血缘对（互为 parent 或同 parent）：`name_rate ≥ 0.50` **或** `sig_rate ≥ 0.30` 判高风险，此时 **fork 输给非 fork**（`:306-307`）；
- 非血缘对：`name_rate ≥ 0.85` **且** `sig_rate ≥ 0.70` 判高风险，此时**创建时间更晚的一方输**（`:308-310`）。

两个仓库的指纹完全相同（`names={workbuddy2api}`，`sigs={workbuddy2api|1.6.19}` ⇒ 两个重叠率都是 1.0），但 `ccrabit/workbuddy2api-hub` 的 parent 是 `ardeyouxipianyi/workbuddy2api-hub`，与将来新建的 `ccrabit/FnDepot`（无 parent）**不构成血缘** ⇒ 若两者同时被召回，会走「非血缘」分支，**后建的 `ccrabit/FnDepot` 反而是输家**。

实测（2026-10-11）主仓库现在**没有**被召回：`filename:fnpack.json` total_count=41、`filename:fnpack.json+fork:true` total_count=14，两者的首页里都没有 `ccrabit/workbuddy2api-hub`。所以当前无撞车。**但如果 GitHub 之后把 fork 里的这份文件索引出来，撞车就会发生。**

处置建议（按优先级）：

1. 建仓推送后**下一个扫描周期核对 5.3 的两条判据**；一旦出现「行数变化但没命中」，把主仓库根的 `fnpack.json` 删掉（用户改用新仓库地址或 `https://raw.githubusercontent.com/ccrabit/FnDepot/main/fnpack.json` 直链），下次扫描即可恢复收录。
2. 或者提前把主仓库根 `fnpack.json` 的**版本键改成一个不会被中心仓库解析成同一签名的形态**（例如去掉 `releases`），但那样主仓库那份就不能再当"可添加的源"用，得不偿失。
3. 不要靠改 `source_info.name` 规避：中心 README:506 明确写了名称/作者/homepage 不是唯一身份，查重看的是 `appname` 与 `appname|version`（`:280-281`）。

---

## 6. 待办（Lead / 用户）

1. **建仓并推送**（需用户提供可建仓的 classic token；当前 PAT 建仓 403）：建 `ccrabit/FnDepot`（非 fork、公开、默认分支 `main`），把 `/tmp/fndepot-src/` 的 3 个文件放到**仓库根目录**（`fnpack.json` 必须在根、文件名与大小写完全一致，中心 README:72）。推完可在中心客户端用仓库地址 `https://github.com/ccrabit/FnDepot` 立即手动添加试用，不必等自动收录。
2. **下一个 16:00 UTC 后核对 5.3**，把结果追加回本文档。
3. **版本升级时的同步点**：以后每发一个包，要同时改「新仓库 `ccrabit/FnDepot/fnpack.json`」与「主仓库根 `fnpack.json`」的 `download_url`/`sha256`/`size`/`updated_at`/`changelog`（`docs/phase-g-local-release.md` 的 runbook 已含主仓库那一处，新仓库这一处需要手工同步）。
4. 是否补真实截图（补了再加 `preview_urls`，≤8 张，中心 README:171）。

## 7. 本 WP 的边界（没做、也不该做）

- 没有建仓库、没有 push、没有改主仓库根 `fnpack.json`、没有碰 `tests/**` 或任何产品代码、没有 commit。
- 没有伪造 `preview_urls` 或截图；没有把 `source_info.author` 写成 FnDepot/官方身份（中心 README:207-211 要求维护者与实际主体一致）。
- 没有改中心仓库的任何内容（`generate_sources.py` 只读引用，未修改）。

## 8. 收尾实况（Lead，2026-10-11 00:55 +08）

用户提供了只有 `repo` scope 的 classic token（`/root/.gh-token-classic`，`GET /user` → 200、`X-OAuth-Scopes: repo`）。第 6 节待办 1 已执行：

- **仓库已建**：`ccrabit/FnDepot`（id `1413442080`，`fork: false`、公开、默认分支 `main`、`has_issues: true`，`created_at 2026-10-10T16:54:17Z`），描述与 homepage 指向主仓库，topics = `fn-nas, fndepot, fnos, nas, workbuddy2api`。
- **3 个文件已推到根目录**：commit `a8dcecf79175e458e9232c56b67d28be9501179e`（`fnpack.json` 2056 B / `ICON.PNG` 7666 B / `README.md` 2191 B，权限 644）。
- **独立复核**：`GET /repos/ccrabit/FnDepot/contents/{fnpack.json,ICON.PNG,README.md}` 均 200；`raw.githubusercontent.com/ccrabit/FnDepot/main/fnpack.json` 与 `/tmp/fndepot-src/fnpack.json` **逐字节相同**（sha256 `730bc97e…`）；用中心仓库自己的 `generate_sources.py` 对**线上那份**跑 `validate_v2_app` → `(True, 'ok')`；`download_url` 指向 `https://github.com/ccrabit/workbuddy2api-hub/releases/download/fnos-1.6.19/WorkBuddy2API-Hub_1.6.19_all.fpk`，`sha256 = e65dcb84…`、`size = 626248`，与 Release 资产一致。
- **立即试用**：飞牛客户端可直接把 `https://github.com/ccrabit/FnDepot`（或 raw 直链）加为外部源，不必等自动收录。

**仍未做**：自动收录（中心仓库 16:00 UTC 扫描 → 2026-10-12 00:00 +08 出结果，提醒已设）；若「行数变化但没命中我们」，按第 5.4 节的预案删掉主仓库根 `fnpack.json`（注意主仓库 `tests/_test_fndepot_source.py` 有 77 条断言钉着那个文件，删它要同步改测试）。
