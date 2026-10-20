# WorkBuddy2API-Hub fnos-1.7.17（飞牛原生 fpk）

本次发布对应上游 `v1.7.17`（`ardeyouxipianyi/workbuddy2api-hub`）。合并基是
`fe30fa0`（v1.7.13），所以这一个包覆盖了上游 **v1.7.14 / v1.7.15 / v1.7.16 /
v1.7.17** 四个 release：**76 个提交、59 个文件、+6758 −489**。
包名 `WorkBuddy2API-Hub_1.7.17_all.fpk`，`appname` 仍是 `workbuddy2api` ——
覆盖安装即可，数据目录 `/vol1/@appdata/workbuddy2api`（账号、用量、设置）不变。

发布不经 CI：包在维护者机器上用 `scripts/build-fpk.sh` 构建、用
`scripts/gh-release.py` 上传，所以**本 Release 的附件与本机 `dist/` 里的文件逐字节相同**。

## 文件与校验

| 文件 | 字节数 | sha256 |
| --- | --- | --- |
| `WorkBuddy2API-Hub_1.7.17_all.fpk` | `905495` | `358fe211c5b8b463001fedec3dec6bffc4be9323d38760058c7bf22bb4f248d9` |
| `WorkBuddy2API-Hub_1.7.17_all.fpk.sha256` | `99` | — |

校验：`sha256sum -c WorkBuddy2API-Hub_1.7.17_all.fpk.sha256`

## 安装 / 升级

1. 应用中心 → 手动安装 → 选择本 Release 的 `.fpk`（覆盖安装即可，端口仍是 8788）；
   也可以装好 FnDepot 后添加源 `https://github.com/ccrabit/FnDepot`，从里面直接更新。
2. 升级前建议备份 `/vol1/@appdata/workbuddy2api/`（至少 `accounts/` 与 `usage/`）。
3. 卸载默认保留数据目录。

## 这一版治的是「断流」

- **首字节之前断流自动重开一次**（#522）：同账号、同出口重试，复用已经发给客户端
  的响应头；出口维度的成功记账从「拿到响应头」挪到「流真正读完」，所以半路死掉的流
  不会再把出口记成健康的。
- **流式 usage 按 OpenAI 契约放到末尾空 choices 帧**：严格客户端（以及架在中间的
  网关）不会再因为一个同时带 `choices` 的 usage 块提前结束，也不会再丢掉计费。
  缓存命中数（`prompt_tokens_details.cached_tokens`）照旧透传。
- **合成 chunk 用动态唯一 id**，不再和真实 chunk 撞 id。

## 其他上游改动

- 模型级 5xx（`11134` / `11102` / `11150` / `11158` / `11129`）不再熔断整池，只影响
  当次请求；`11158`（免费账号不可用）会在模型清单上标注，状态落
  `accounts/model_entitlements.json`，冷却到 04:00 清掉。
- `/v1/models` 可按 API Key 的模型限制过滤；一键部署区分 `WB_DEPLOY_MODE=local|lan|public`；
  OpenRouter 估价支持模型级校准系数；成长任务支持手动领取；面板改密结果以服务端为准；
  身份请求头的 `X-Private-Data` 可选。
- DSH 一键配置改写 profile 补丁层并放宽限流重试（修「对话到一半链接中断」的那种假象）。
- 一批移动端看板布局修正（卡片换行、表格横向滚动、按钮尺寸）。

## 飞牛侧（本 fork 相对上游多出来的部分）

- 统一网关免密入口（`--unix-socket` + `--base-path`）、面板主题与移动端适配、
  账号导入导出与 cockpit 看板导出。
- **流式空闲心跳**（`WB_STREAM_KEEPALIVE_SECONDS`，默认 10 秒，`0` 关闭，上限 300）：
  上游安静超过间隔就补一个 `: keepalive` 注释帧，避免反向代理/中间设备按「没字节」
  把长回答判死。本版修掉了它的一处自我干扰——心跳线程原先在收尾帧之前就停了，
  导致最后的 finish / usage 帧写不出去。
- **打包**：模型目录存档仍指向可写数据目录 `${TRIM_PKGVAR}/catalog`（v1.7.5 起上游
  默认落在只读载荷目录，在 NAS 上会静默失效），安装/升级时创建并 `chmod 700`，
  `catalog/` 不打进包；新增的 `wb_entitlements.py` 已进入载荷与守卫名单（`wb_proxy.py`
  顶层 import，漏它就是装完启动即 ImportError）；`tools/` 与 `ops/` 不进包。
- 阿里云那套 systemd 更新服务（`ops/aliyun/`、`WB_UPDATE_INSTALL_ENABLED`）在飞牛上
  保持关闭：本包没有 systemd path unit，面板的「安装更新」按钮按设计禁用。

## 顺手修掉的上游 bug（两处，都有套件钉住）

1. **无错误体的 5xx 会把请求炸掉**：`http_error_detail()` 在 `HTTPError(..., fp=None)`
   时从 urllib 拿回的是 `reason` 文本（不是 bytes），`raw.decode()` 抛
   `AttributeError` —— 账号没记账、出口退避没记、客户端只看到 500，而不是正常的
   「换个账号重试」。上游自带的 `_test_breaker_fairness.py` / `_test_egress_backoff.py` /
   `_test_pool_backoff.py` 在干净上游树里就红着，根因就是这里。
2. **聊天流的心跳抢在收尾之前停**：`_chat_stream_response` 里 `keepalive.stop()` 落在
   尾部写入之前，导致 finish / usage 帧与 `[DONE]` 前的 flush 被丢弃。

## 验证数字

- `python3 tests/run_all.py --jobs 4`：**199 passed, 0 failed, 0 skipped**
  （`_test_phase_e_verify.py` PASS=372 FAIL=0 SKIP=3）
- `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.7.17_all.fpk`：**70 passed, 0 failed**
  （1 条 SKIP 属正常：`fnos-<版本>` tag 打在合并提交上，回填提交在其之后）
- 载荷 **46 个文件 + 16 个目录**（1.7.13 是 45 个文件），manifest checksum
  `3564daec86061ad271a92acb5b821459`
- 冒烟（发布前，隔离端口 8799，不动设备上的 8788）：面板 `/` 200、`/panel/status` 200、
  `/v1/models` 18 个模型、非流式回复「连通」且带 usage、流式最后两帧是
  `choices: []` 的 usage 帧 + `[DONE]`（`credit` 有值），日志无报错
- 附件的 sha256 与仓库根 `fnpack.json`、`ccrabit/FnDepot` 源里登记的 `1.7.17` 条目一致

## 已知限制

- 上游 v1.7.6 起 `/v1/messages`（Anthropic 原生入口）默认关闭，需显式设
  `WB_ENABLE_ANTHROPIC_MESSAGES=1`；本包保持上游默认。
- 本包只面向飞牛 fnOS（`all` 平台，纯 Python 载荷），Windows/macOS 请用仓库里的便携包。
- 日志落库（SQLite）默认关闭；升级不会自动迁移历史 `usage/` 统计。
