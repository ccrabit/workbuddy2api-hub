# WorkBuddy2API-Hub fnos-1.8.0（飞牛原生 fpk）— 数据看板已修

对应上游 `v1.8.0`（`ardeyouxipianyi/workbuddy2api-hub`，该 tag 就是上游 `main` 的头部）。
包名 `WorkBuddy2API-Hub_1.8.0_all.fpk`，`appname` 仍是 `workbuddy2api` —— 覆盖安装即可，
数据目录 `/vol1/@appdata/workbuddy2api`（账号、用量、设置）不变。

> **这个包在本轮重打包了一次（同一版本号、新字节）**：第一次打包之后发现「数据看板在宽屏下
> 只剩一列」，定位到是本仓库自 `fnos-1.7.30` 起带进来的样式缺陷（见下），修好后重新构建并覆盖
> 了同名资产。校验时请以下表的 sha256 为准。

## 本版修掉的问题（重点）

**宽屏下「数据看板」只剩一列** —— KPI 卡片一张占一行、行高巨大，「请求数 / 生成速度 / 积分消耗」
被拉开到屏幕各处，左侧导航却正常。根因：上游 `v1.7.30` 在统计条上新增的
`@media (max-width: 860px)` 与本包的移动端兜底规则在同一位置合并时少了一个收尾的 `}`，于是它把
**后面所有规则**（整个 `#pageAnalytics` 看板设计、`.wb-help` 使用说明）都吞进了「窄屏才生效」的
分支。浏览器不报错，只是宽屏下全部失效（`fnos-1.7.24` 的样式表是 `670/670` 配平，
`fnos-1.7.30` 起变成 `722/721`，所以 1.7.30 / 1.7.33 都带着它）。

修法：补回那个 `}`，让 `#pageAnalytics`（六列 KPI 栅格、Bento 面板）、`.wb-help`、
`#cockpitRealm`、`#cards` 都回到嵌套深度 0；移动端断点规则本身没动。另外新增
`tests/_test_dashboard_css.py`（4 项）钉住「每个 `<style>` 块的括号必须等量」「关键字面规则必须
在深度 0」「深度大于 0 的规则只能待在 `@media` / `@keyframes` / `@supports` 里」——这类缺陷不会让
任何断言变红（字符串还在，只是位置错了），必须单独钉一层。

## 文件与校验

| 文件 | 字节数 | sha256 |
| --- | --- | --- |
| `WorkBuddy2API-Hub_1.8.0_all.fpk` | `1027104` | `3f98610c77d0375c909be14d15972c9752f98846c5f27aeb8dd1de63580d329f` |
| `WorkBuddy2API-Hub_1.8.0_all.fpk.sha256` | `98` | — |

校验：`sha256sum -c WorkBuddy2API-Hub_1.8.0_all.fpk.sha256`

## 安装 / 升级

应用中心 → 手动安装 → 选这个 `.fpk`（覆盖安装即可，端口仍是 8788）；或在 FnDepot 客户端里点更新
（源 `https://github.com/ccrabit/FnDepot`）。已经装过**旧字节**的 1.8.0 的机器不会自动收到更新
（版本号相同），需要手动覆盖安装一次。

## 本版包含（上游 v1.8.0）

- **`#647`** 国际版沙箱证书失败时降级到活跃上报，不再因为一个证书问题把整段日常任务全灭
- **`#644`** `stderr` 日志通道不再阻塞请求线程（日志写不动时不会拖住整条请求）
- **`#643`** 桌面 chat 可选协议一致性
- **`#640`** 更新检查超时放宽到 10 秒

## 飞牛侧（本 fork 相对上游多出来的部分，全部保留）

- 统一网关免密入口（`--unix-socket` + `--base-path`）、面板主题与移动端适配、账号导入导出与
  cockpit 看板导出；页面里每个 `fetch()` 都经 `wbUrl()` 前缀包装（有套件钉住）。
- 流式心跳可用 `WB_STREAM_KEEPALIVE_SECONDS` 覆盖上游默认的 15 秒（`0` 关闭、上限 300 秒）。
- 可写模型目录存档：`WB_PROXY_CATALOG_DIR` 指向 `$TRIM_PKGVAR/catalog`（安装/升级时创建并
  `chmod 700`），`catalog/` 不打进包。
- 打包：`tools/`、`ops/`、`catalog/`、`logs/`、`tests/`、`docs/` 一律不入包；载荷守卫名单里是
  `wb_proxy.py` 顶层 import 的全部模块（漏一个是装完启动即 ImportError）。
- 面板「安装更新」在飞牛上保持关闭（`install_enabled()` 的三条判据都不成立）；升级走应用中心或
  FnDepot，**不要**在命令行手工替载荷再手工起服务。

## 验证数字

- `python3 tests/run_all.py --jobs 4`：`237 passed, 0 failed, 0 skipped`
- `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.8.0_all.fpk`：`70 passed, 0 failed`
- 载荷：51 个文件 + 15 个目录，manifest checksum `d3739a61a5faa8e4b7651499d83957e5`；
  包内 `server/dashboard.html` 的样式表已是 `722/722` 配平
- 附件的 sha256 与仓库根 `fnpack.json` 登记的 `1.8.0` 条目一致

## 已知限制

- 上游 v1.7.6 起 `/v1/messages`（Anthropic 原生入口）默认关闭，需显式设
  `WB_ENABLE_ANTHROPIC_MESSAGES=1`；本包保持上游默认。
- 本包只面向飞牛 fnOS（`all` 平台，纯 Python 载荷），Windows/macOS 请用仓库里的便携包。
