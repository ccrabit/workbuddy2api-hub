# WorkBuddy2API-Hub fnos-1.7.30（飞牛原生 fpk）

本次发布对应上游 `v1.7.30`（`ardeyouxipianyi/workbuddy2api-hub`）。合并基是
`af37786`（v1.7.29），所以这一个包只覆盖 `v1.7.30` 一个 release：**34 个提交、
32 个文件、+4954 −427**。`v1.7.30` 就是上游 `main` 的头部，因此这棵树不含任何
「未发版提交」。

包名 `WorkBuddy2API-Hub_1.7.30_all.fpk`，`appname` 仍是 `workbuddy2api` ——
覆盖安装即可，数据目录 `/vol1/@appdata/workbuddy2api`（账号、用量、设置）不变。

发布不经 CI：包用 `scripts/build-fpk.sh` 构建、用 `scripts/gh-release.py` 上传，
**本 Release 的附件与本机 `dist/` 里的文件逐字节相同**。本轮起这个流程由
`scripts/auto-sync-upstream.sh`（cron `wb-auto-sync`，每天 04:17）无人值守跑：
无冲突的版本会被自动合并、构建、装机并发版；有冲突就停在 `exit 3` 并留报告，
由人接手——这一版就是「停在冲突、人工解决后发布」的第一次。

## 文件与校验

| 文件 | 字节数 | sha256 |
| --- | --- | --- |
| `WorkBuddy2API-Hub_1.7.30_all.fpk` | `1011173` | `77901158d6acef1e88efe2f45693cc54354662e301b3428310ef17074f2a9ab6` |
| `WorkBuddy2API-Hub_1.7.30_all.fpk.sha256` | `99` | — |

校验：`sha256sum -c WorkBuddy2API-Hub_1.7.30_all.fpk.sha256`

## 安装 / 升级

1. 应用中心 → 手动安装 → 选择本 Release 的 `.fpk`（覆盖安装即可，端口仍是 8788）；
   也可以在 FnDepot 里给 `https://github.com/ccrabit/FnDepot` 这个源点更新。
2. 升级前建议备份 `/vol1/@appdata/workbuddy2api/`（至少 `accounts/` 与 `usage/`）。
3. 卸载默认保留数据目录。

## 这一版做了什么

上游这 15 笔社区改动的主线是「判定别判错」和「面板别闪」：

- **调度器日志与区域风控闸门改取正在运行的 `wb_proxy`**（#594）：网关以
  `python[w] wb_proxy.py` 启动时主模块是 `__main__`，`wb_scheduler` 里裸写
  `import wb_proxy` 会再加载一份副本——副本的日志库是 `None`、暂停状态也是另一份，
  于是「调度器日志空白」「风控闸门看不到刚设的暂停」两个现象都来自这里。
- **签到不再把业务失败记成成功**（#596）：`200 + code 10001 +「请求处理中，请勿重复操作」`
  这类明确失败回执曾被判成签到成功，看板数字因此虚高。
- **一键签到按任务开关选号**（#598）：批量签到只挑 `tasksEnabled` 的号，停用账号
  不再被无差别签到。
- **Token 保活提前量改成 48 小时**（#600，`WB_KEEPALIVE_LEAD_HOURS` 可调）：写死的
  2 小时远小于 24 小时的巡检间隔，约 92% 的到期时刻要等过期后才补。
- **每日活跃网页会话跑完即释放**（#623）：上游对单账号活跃会话有 10 条硬上限，旧实现
  只建不收尾，攒满后建会话一律 429 / `10105`；现在成功轮次 stop、失败轮次 stop +
  delete，撞上限时自动清理最旧的一条。
- **面板闸门 fail-closed**（#606）：首帧不再闪出看板骨架，`?pwd=` 失败后也不会卡死；
  **面板 POST 的空 body 会被排空**（#608）：按钮发 `{}` 后没读完请求体，同一条
  keep-alive 连接上的下一个请求会 `501`，表现为偶发「无法连接反代」。
- 其余：下拉框改为自绘（#601）、一次流式回复只带一个 chunk id（#607）、每日活跃
  建会话失败后按 `phase` 补退避（#605）、Codex 远程压缩 v2（#610）、账号级并发上限
  与会话粘滞键（#612，两个开关默认关）、静态 API Key 账号（#620）、账号行显示会员
  档位胶囊（#621）。
- **Pro Only 标注改由目录 `modelTiers` 驱动**（#609）：上游因此**删掉了
  `wb_entitlements.py`** 与其套件——`ready()` 早已按 `modelTiers` 在本地拦掉
  PRO-only 模型，运行时那条通道几乎不再触发。

飞牛侧（本 fork 相对上游多出来的部分）：

- **跟着上游删掉 `wb_entitlements.py`**：载荷守卫名单与 `PKG_MODULES` 都不再列它
  （名单里留着已删除的模块会让构建直接红），`wb_proxy.py` 的 import 与
  `release/portable.txt` 的清单项同步去掉；本层的 `wb_export.py` 保留。
- **面板闸门两段都留**：先执行上游的「摘掉 `html.wb-panel-session`」（否则闸门永远
  出不来），再走本层的「网关模式下把闸门整个摘掉并提示从应用中心重开」——飞牛网关
  已经替我们对端做了认证，老标签页不该突然弹出没人设过的密码框。
- 统一网关免密入口（`--unix-socket` + `--base-path`）、流式空闲心跳
  （`WB_STREAM_KEEPALIVE_SECONDS`，默认 10 秒）、可写 `catalog/` 目录、以及
  `scripts/auto-sync-upstream.sh` 的无人值守发布链路都在。

## 验证数字

- `python3 tests/run_all.py --jobs 4`：`234 passed, 0 failed, 0 skipped`
- `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.7.30_all.fpk`：`70 passed, 0 failed`
  （1 条 SKIP 属正常：`fnos-<版本>` tag 打在合并提交上，而回填提交在其之后）
- 载荷：51 个文件 + 16 个目录，manifest checksum `58784a7e78875964dda6d4071d5f8df5`
- 装机：`cmd/main install` → `cmd/main start` → `/health` 由 `wb-proxy/1.7.29` 变为
  `wb-proxy/1.7.30`（失败会自动回滚到备份的 1.7.29 并保留数据目录）
- 附件 sha256 与仓库根 `fnpack.json` 里登记的 `1.7.30` 条目一致

## 已知限制

- 上游 v1.7.6 起 `/v1/messages`（Anthropic 原生入口）默认关闭，需显式设
  `WB_ENABLE_ANTHROPIC_MESSAGES=1`；本包保持上游默认。
- 本包只面向飞牛 fnOS（`all` 平台、纯 Python 载荷），Windows/macOS 用仓库里的便携包；
  飞牛上「面板一键更新」按设计仍然关闭（没有 systemd path unit、不是便携包、
  没配外部执行者），升级走应用中心或 FnDepot。
- 账号级并发上限与会话粘滞键默认关闭，要在设置页显式打开。
