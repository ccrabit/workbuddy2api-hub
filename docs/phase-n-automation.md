# 自动同步上游任务（`wb-auto-sync`）

一个 cron 任务：每天定时把上游 `ardeyouxipianyi/workbuddy2api-hub` 的最新 release
并进本 fork、构建飞牛包、发布到 GitHub + FnDepot，并把**这台机器**上装着的
workbuddy2api 升到新版本。

- 驱动脚本：`scripts/auto-sync-upstream.sh`
- 机械修补：`scripts/auto_sync_fixups.py`（README 套件数、载荷守卫名单、工作流政策、
  `fnpack.json` / `EXPECTED_VERSION`、交付文档里的设备版本声明）
- 自检套件：`tests/_test_auto_sync.py`
- 日志与报告：`logs/auto-sync/<时间戳>.log`、`<时间戳>.md`（`last.log` 指向最近一次）

## 计划时间与安装窗口

```
17 4 * * * cd /vol2/1000/AgentWork/2api/workbuddy2api-hub && \
  HOME=/root PATH=/var/apps/nodejs_v24/target/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  ./scripts/auto-sync-upstream.sh >> logs/auto-sync/cron.log 2>&1
```

选凌晨 4:17：避开 FnDepot 中心仓库每天 03:26 的扫描，也避开白天用模型的时间。

**为什么要刻意挑时间**：这台机器上跑的这个服务本身代理着本机模型的出站流量。
装新版本要 `stop` → 换文件 → `start`，**这几秒里模型会断**。脚本保证三件事：

1. 停之前先把 `server/`、`config/`、`ui/` 和 `manifest` 打包备份到
   `/vol1/@appcenter/install-backup-<时间戳>/`；
2. 起之后不是「进程在」就算成功，而是轮询 `/health` 直到 `Server: wb-proxy/<新版本>`
   （最多 45 秒）；
3. 起不来就**自动回滚**（从备份 tarball 恢复 + 再 `start` + 再验 `/health`），
   回滚也失败才报错退出。

被中断也别怕：任何一次运行都不会把服务留在停止状态——脚本最后一步永远是
`cmd/main start`。想手工救回来：`/var/apps/workbuddy2api/cmd/main start`。

## 一次运行做什么

1. `git fetch upstream --tags`；
2. 版本号取上游**最新 release tag** 的三段号（`v1.7.29` → `1.7.29`）；
3. 如果 `fnos-<版本>` 已经包含 `upstream/main` → 什么都不做，退出码 2；
4. 新建 `auto/upstream-<版本>` 分支并 `git merge --no-commit --no-ff upstream/main`；
   **有冲突就在这里停**（退出码 3，报告里列出冲突文件）——冲突要人来判断，脚本不猜；
5. 机械修补（见上）；
6. `scripts/build-fpk.sh` → `scripts/verify-fpk.sh` → `gh-release.py sha256`；
7. **装机**（可用 `--no-install` 跳过）：备份 → 停 → 换 `server/` `config/` `ui/`
   `cmd/` `wizard/` → 改 `manifest` 的 `version` / `checksum` → `cmd/main install` →
   `cmd/main start` → 等 `/health` 报新版本；
8. `tests/run_all.py --jobs 4` 必须 **0 failed 且 0 skipped**（跳过 JS 套件不算绿，
   `node` 不在 PATH 上会直接失败而不是静默跳过）。**放在装机之后**是因为交付文档的
   门会用「设备当前装的是 X」去比对机器上实际跑的版本；
9. tag `fnos-<版本>` → 推 `main` + tag → 建 Release + 上传 fpk 与 `.sha256` →
   下载回来 `cmp` 逐字节比对 → 推 `ccrabit/FnDepot` 源；
10. 写运行报告。

## 退出码

| 码 | 含义 | 要做的事 |
|----|------|----------|
| 0 | 发布完成 | 无 |
| 2 | 已是最新 | 无 |
| 3 | 合并冲突，需要人 | `git checkout -b auto/upstream-<版本>` 后手工合并（参照 `docs/phase-f-delivery.md` 的历史记录） |
| 4 | 套件红了，没发布 | 看 `logs/auto-sync/<时间戳>.log.suite` 尾部 |
| 5 | 构建或校验失败 | 看 `.build` / `.verify` |
| 6 | 推送/发布失败 | 多半是 token 或网络 |
| 7 | 装机失败（已尝试回滚） | 先 `cmd/main start`，再看 `install-backup-*/` |

## 手工跑

```bash
cd /vol2/1000/AgentWork/2api/workbuddy2api-hub
./scripts/auto-sync-upstream.sh --check        # 只报「有没有新版本、合并会不会冲突」
./scripts/auto-sync-upstream.sh --no-install   # 同步+发布，不动这台机器
./scripts/auto-sync-upstream.sh                # 全流程（含装机）
```

`--check` 不动任何东西，也不会重启服务。

## 不做的事

- 不解决合并冲突（要判断「两边都留」还是「取上游」）；
- 不写 Release 正文的散文部分（自动正文只有指纹、上游提交清单与验证数字）；
- 不改 `appname` / 网关口径 / `WB_UPDATE_INSTALL_ENABLED`（飞牛上面板「安装更新」
  继续关闭，升级只走应用中心或 FnDepot）；
- 不 vendor 任何第三方 FnDepot 内容。

## 关掉它

```bash
crontab -l | grep -v auto-sync-upstream.sh | crontab -
```
