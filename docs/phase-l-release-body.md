# WorkBuddy2API-Hub fnos-1.7.24（飞牛原生 fpk）

本次发布对应上游 `v1.7.24`（`ardeyouxipianyi/workbuddy2api-hub`）。合并基是
`af706fc`（v1.7.17），所以这一个包覆盖了上游
**v1.7.18 / v1.7.19 / v1.7.20 / v1.7.21 / v1.7.22 / v1.7.23 / v1.7.24**
七个 release：**58 个提交、56 个文件、+6313 −489**。`v1.7.24` 就指向上游 `main`
的头部，因此这棵树不含任何「未发版提交」。

包名 `WorkBuddy2API-Hub_1.7.24_all.fpk`，`appname` 仍是 `workbuddy2api` ——
覆盖安装即可，数据目录 `/vol1/@appdata/workbuddy2api`（账号、用量、设置）不变。

发布不经 CI：包在维护者机器上用 `scripts/build-fpk.sh` 构建、用
`scripts/gh-release.py` 上传，所以**本 Release 的附件与本机 `dist/` 里的文件逐字节相同**。

## 文件与校验

| 文件 | 字节数 | sha256 |
| --- | --- | --- |
| `WorkBuddy2API-Hub_1.7.24_all.fpk` | `953846` | `646a6d27c13cf78b291ee464029b63b2d72f8182c32788bc023c6db82e415ca5` |
| `WorkBuddy2API-Hub_1.7.24_all.fpk.sha256` | `99` | — |

校验：`sha256sum -c WorkBuddy2API-Hub_1.7.24_all.fpk.sha256`

## 安装 / 升级

1. 应用中心 → 手动安装 → 选择本 Release 的 `.fpk`（覆盖安装即可，端口仍是 8788）；
   也可以装好 FnDepot 后添加源 `https://github.com/ccrabit/FnDepot`，从里面直接更新。
2. 升级前建议备份 `/vol1/@appdata/workbuddy2api/`（至少 `accounts/` 与 `usage/`）。
3. 卸载默认保留数据目录。

## 这一版主要多了「可运维」

- **国际版每日活跃全部可配**：`schedule.daily_chat` 支持 1–24 个 `HH:MM` 时段（改完 30 秒内
  生效，留空跟随签到整点）；并发数 1–10（默认 1）；重试等待改线性 `base × N`
  （默认 120 / 240 / 360 秒，原来是 120 / 240 / 480）；当天已成功就 `skipped`，不再重复
  发桌面腿或新建网页会话；失败后可按模型组合回退（默认关）；可发随机提示词
  （默认关，内置 300 条 + 自定义最多 200 条）。
- **API Key 可按账号限制**：每条 Key 新增 `accounts` 白名单，粘性绑定不能绕过，
  `/u/<ref>` 定址到名单外返回 403；留空保持不限制。
- **`/v1/models` 可只列可用模型**（默认关）：国际版 PRO ONLY 模型只在池里有付费账号时
  才出现，调度侧也拒绝把它派给免费账号，不用等上游回 11158。
- **思考档位映射**（默认开）：请求的 `reasoning_effort` 不在模型目录声明的档位里时，
  改写为默认档位，避免整请求被上游拒绝。
- **面板可改全局提示词与出站身份版本号**：`prompt.text` 支持追加/替换 system、保存即生效；
  身份版本号列出各端当前值与默认值，修改需要面板密码。
- **账号新增 `tasksEnabled`**：`enabled` 只管 API 取号，签到 / 成长任务 / 连登管家 /
  猫猫旅行 / 国际版活跃按这个开关选号；面板账号行有「任务开/关」胶囊。
- **流式断流不再伪造 `[DONE]`**：改发标准 error 帧（`upstream_stream_error`）并关连接，
  严格客户端能看出这是错误而不是正常结束。
- 其它：热力图按本地日刷新；11-128 的身份句 + 品牌组合指纹改写为中性句；
  成长任务补「无畏契约拼豆专家」；修全量刷新积分的 `NameError`（漏 `import random`）、
  修「数据用途声明」文案反了、修模型清单「消费倍率」列截断。

## 飞牛侧（本 fork 相对上游多出来的部分）

- 统一网关免密入口（`--unix-socket` + `--base-path`）、面板主题与移动端适配、
  账号导入导出与 cockpit 看板导出。
- **流式空闲心跳**（`WB_STREAM_KEEPALIVE_SECONDS`，默认 10 秒，`0` 关闭，上限 300）：
  上游安静超过间隔就补一帧 `: keepalive` 注释，避免反向代理按「没字节」把长回答判死。
  本版顺手收紧了一处并发瑕疵：上游把断流收尾改成 error 帧后仍是直写 `wfile`，而心跳线程
  要到 `finally` 才停 —— 一帧 `: keepalive` 可能插进错误帧中间；现已改走同一个加锁写出口。
- **打包**：模型目录存档仍指向可写数据目录 `${TRIM_PKGVAR}/catalog`（v1.7.5 起上游默认落在
  只读载荷目录，在 NAS 上会静默失效），安装/升级时创建并 `chmod 700`，`catalog/` 不打进包。
- **新增五个模块进载荷与守卫名单**：`wb_tiers.py`、`wb_webprompts.py`（`wb_proxy.py` 顶层
  import）、`wb_update_portable.py`（`wb_update_request` 顶层 import）、`wb_update_apply.py`、
  `wb_update_external.py` —— 漏一个是装完启动即 ImportError。`tools/` 与 `ops/` 不进包。
- **面板「安装更新」在飞牛上保持关闭**：`install_enabled()` 现在认 systemd unit、
  外部执行者环境变量或便携包标记，飞牛三条都不成立，所以按钮不会去下「便携 zip」覆盖
  fpk 装的只读载荷；升级仍走应用中心或 FnDepot。

## 验证数字

- `python3 tests/run_all.py --jobs 4`：**216 passed, 0 failed, 0 skipped**
  （`_test_phase_e_verify.py` PASS=377 FAIL=0 SKIP=3）
- `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_1.7.24_all.fpk`：**70 passed, 0 failed**
  （1 条 SKIP 属正常：`fnos-<版本>` tag 打在合并提交上，回填提交在其之后）
- 载荷 **51 个文件 + 16 个目录**（1.7.17 是 46 个文件），36 个 python 文件 parse 通过，
  manifest checksum `fc5a7fc10c428d9f5b3b2e37574b9ad8`
- 冒烟（发布前，隔离端口 8799，不动设备上的 8788）：`/health` 200、面板 `/` 200、
  `/v1/models` 18 个模型、非流式回复「连通」且带 usage；流式 154 帧，最后是
  `choices: []` 的 usage 帧（`credit` 有值）+ `[DONE]`，整条流**零心跳帧**（忙流不写注释，
  零开销）；日志无报错
- 附件的 sha256 与仓库根 `fnpack.json`、`ccrabit/FnDepot` 源里登记的 `1.7.24` 条目一致

## 已知限制

- 上游 v1.7.6 起 `/v1/messages`（Anthropic 原生入口）默认关闭，需显式设
  `WB_ENABLE_ANTHROPIC_MESSAGES=1`；本包保持上游默认。
- 本包只面向飞牛 fnOS（`all` 平台，纯 Python 载荷），Windows/macOS 请用仓库里的便携包
  （那边的「一键更新」是另一条路径，与飞牛无关）。
- 日志落库（SQLite）默认关闭；升级不会自动迁移历史 `usage/` 统计。
