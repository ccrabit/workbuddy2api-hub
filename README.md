# WorkBuddy2API-Hub — 国际版、国内版多账号网关中枢

> [!IMPORTANT]
> **项目进入低频维护（2026-10-23） / Low-frequency maintenance**
>
> 大幅降低更新频率与 Issue / PR 处理速度。请先阅读风险说明，再决定是否继续使用。
>
> Updates and responses to issues / pull requests will be significantly reduced. Read the risk notice below before continuing.

> [!WARNING]
> **WorkBuddy 上游正在收紧对非官方客户端的识别与拦截。**
>
> - **封禁**：2026-10-23 下午起，非官方客户端的识别与拦截明显收紧。
> - **维护者**：近期工作压力增大，无法保证及时更新与响应。
> - **可用性**：上游可能随时进一步收紧，导致本项目不可用。
> - **账号风险**：使用非官方客户端造成的风控、限流或封禁，由使用者自行承担。
>
> **Upstream enforcement** tightened detection and blocking of unofficial clients from the afternoon of 2026-10-23. The maintainer is under increased workload and cannot guarantee timely updates or replies. The upstream may tighten further at any time; rate limits, account restrictions or bans caused by using an unofficial client are the user's responsibility.

本项目仅用于协议学习、研究与个人自用。请优先使用官方客户端，不要使用主账号，不要共享账号，也不要用于商业转售。

This project is for protocol research and personal use only. Prefer the official client, do not use your primary account, and do not resell or share access.

<p align="center">
  <a href="https://github.com/ardeyouxipianyi/workbuddy2api-hub/releases"><img src="https://img.shields.io/badge/Release-v1.8.0-2496ED?style=flat-square" alt="Version 1.8.0"></a>
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/API-OpenAI_Compatible-412991?style=flat-square" alt="OpenAI API">
  <img src="https://img.shields.io/badge/Dual_Realm-Intl_&_CN-0DBD8B?style=flat-square" alt="Dual Realm">
  <img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Maintenance-Low--frequency-c96f3d?style=flat-square" alt="Low-frequency maintenance">
</p>

把腾讯 **[www.workbuddy.ai](https://www.workbuddy.ai)**（国际版）与 **[codebuddy.cn](https://www.codebuddy.cn)**（国内版）的原生服务封装成标准 OpenAI 兼容接口（Chat Completions / Responses），并提供默认关闭的实验性 Anthropic Messages 适配；同时补齐多账号调度与运维能力：

- **开箱即用**：绿色包自带精简 Python（Windows），双击脚本即启；
- **双区域独立路由**：国际版 / 国内版各自配置与调度，看板一键切换，状态落盘；
- **协议与风险**：默认支持 Chat Completions、Responses API（Codex）；Anthropic Messages（Claude Code / Anthropic SDK）经协议转换且缓存兼容性尚未验证，默认禁用，仅可显式选择启用；
- **模型目录对齐官方桌面端**：剔除补全通道与专线变体，能力与规格按桌面端宣告，上游新模型无需发版即进 `/v1/models`；
- **设备指纹隔离 (`derive_id`)**：以账号 UID 稳定派生机器码与会话标识，同一账号不漂移、不同账号互不关联；
- **账号接入**：看板点链接走浏览器 OAuth；Windows 上还能直接从运行中的桌面客户端导入（加密 token 就地解密），macOS / Linux 可手动粘贴解码密钥后导入；
- **每日自动化**：国内版签到 / 成长与积分任务 / 猫猫旅行；国际版每日活跃打卡（真跑完网页会话）；后台调度器按 09:00 & 21:00、22:00、01:00 排程；
- **限额护栏**：保留积分 · 每日 Token · 每日积分 · 按模型 Token 四条账号级护栏，单账号独立计数，本地 0 点解封（默认全部关闭）；
- **OpenRouter 价估算**：把 token 折算成等价花费（人民币 / 美元可切），逐条请求可悬停查看定价来源；
- **多 Key 与出口绑定**：每个 Key 可固定走国际版或国内版、可限定模型，用量按 Key 归属；
- **Web 看板**：指标卡片、模型性能与用量大表、请求流水、账号与任务管理一屏可查。

> ⚡ **Vibe Coding 产物**：本项目为 100% Vibe Coding 协同产物——人类开发者提出架构与业务意图，AI 助手端到端完成逆向分析、链路调度、WAF 指纹脱敏与界面编写。

> 📌 **提交代码贡献前**：请先查看并**严格遵循**贡献手册 [`CONTRIBUTING.md`](CONTRIBUTING.md)——提交格式、测试门禁与端到端冒烟要求都在那里（AI / 智能体请特别注意其中的硬性规则节）。

---

## 一、快速启动

### 1. 本机运行

**Windows** 双击 **`start-wb-proxy.bat`**：默认静默启动（`pythonw` 后台运行 + 独立日志窗口，关掉日志窗口不会停服务，用面板电源按钮或 `restart-wb-proxy.bat` 停止）；想用「前台控制台 + 关窗即停」，双击 **`start-wb-proxy-visible.bat`**。**macOS** 双击 **`start-wb-proxy.command`**（首次被 Gatekeeper 拦截时右键 →「打开」确认一次），或在终端执行 `./start-wb-proxy.sh [端口]`（默认 8788）。

启动后：**API 地址** `http://127.0.0.1:8788/v1`，**Web 看板** `http://127.0.0.1:8788/`。首次启动还没有账号，打开看板点「+ 添加账号 (OAuth)」完成授权即自动入库。

> 绿色包自带的精简 Python 运行时只覆盖 Windows；macOS / Linux 直接使用系统 Python，需要 **3.9+**（启动脚本找不到内置运行时会明确打印所用的解释器与版本）。Docker 部署自带基础镜像，不受影响。

> zip 解压后若提示权限不足，先执行一次：`chmod +x start-wb-proxy.sh start-wb-proxy.command start-wb-proxy-lan.sh start-wb-proxy-lan.command allow-firewall.command`

### 2. 面板访问密码

看板需要**面板访问密码**（默认 `admin`），它与 API Key 相互独立：密码只用于打开看板，可在「设置」页修改（或启动时 `--panel-password` 指定），以 PBKDF2-SHA256 摘要存于 `accounts/settings.json`（不存明文），登录态只留在浏览器会话里。

本机 / 受信局域网自用可带 `?pwd=面板密码` 免手输直接进面板（如 `http://127.0.0.1:8788/?pwd=admin`）；公网暴露时不要用——密码会留在浏览器历史与反向代理日志里。注意它和局域网共享的 `?key=` 不同：`?key=` 只把 API Key 存给 `/v1` 用，不会自动登录面板。**首次登录后请立即改掉默认密码。**

### 3. 局域网共享

- **Windows** 双击 `start-wb-proxy-lan.bat`（静默）或 `start-wb-proxy-lan-visible.bat`（前台窗口，关窗即停）；**macOS** 双击 `start-wb-proxy-lan.command`，或 `./start-wb-proxy-lan.sh [端口] [Key]`；
- **Base URL** `http://<本机局域网IP>:8788/v1`；带密钥直达面板 `http://<IP>:8788/?key=生成的Key`；
- **API Key**：首次启动生成高强度随机 Key，写入 `accounts/settings.json` 并打印在终端，重启复用；也可用第二个参数指定自己的 Key；
- **macOS 防火墙**：首次监听端口时选「允许」；macOS 15+ 还要在「系统设置 → 隐私与安全性 → 本地网络」允许终端，`./allow-firewall.command` 可查看状态并加白。

### 4. 多 API Key 与出口绑定

「设置」页可管理多个 Key，每个 Key 独立出口——不同客户端各用各的 Key，国内外流量互不干扰：

- **生成 / 绑定**：填名称点「生成随机 Key」；可固定走 🌐 国际版或 🇨🇳 国内版，不绑定则跟随看板顶部的全局出口开关；
- **模型限制**：可填允许的模型（如 `deepseek*`、`gpt-6-astra`，支持 `*`，逗号分隔），留空不限；不在列表里的请求本机直接返回 400，不送达上游、不消耗额度；
- **区域自检**：Key 绑定的出口与模型不匹配时（如国际版 Key 调国内独占的 `deepseek-v4-pro`）直接返回可读 400，而不是上游晦涩的 WAF 报错；
- **启停 / 删除**：可单独启停；删除后密钥立即失效，条目以只读形式留在「设置」页的「已删除」折叠区，历史用量仍显示它的名字；
- **用量归因**：「数据看板」页按 Key 列出请求数、Token、缓存命中、积分与模型分布，口径与账号表一致；
- **防冲突**：面板保存过 Key 后，启动参数里的 `--api-key` 自动失效。

### 5. Docker 部署

预编译双架构镜像（`linux/amd64`、`linux/arm64`）发布在 GHCR 与 Docker Hub，**无需克隆代码、无需本地编译**：

**方式一：一键脚本（推荐）**

```bash
# 官方源（可直连 GitHub 环境）：
curl -fsSL https://raw.githubusercontent.com/ardeyouxipianyi/workbuddy2api-hub/main/quick-deploy.sh | bash

# 国内网络 / NAS 加速（Connection reset 时用）：
curl -fsSL https://gh-proxy.com/https://raw.githubusercontent.com/ardeyouxipianyi/workbuddy2api-hub/main/quick-deploy.sh | sudo bash
```

NAS（如飞牛 fnOS）普通用户没有 Docker 权限时，把结尾的 `bash` 换成 `sudo bash`。再次运行同一条命令即平滑升级，账号与用量数据不受影响。

**部署模式**：默认 `lan`（`8788:8788`，局域网内可访问）。部署到公网服务器、或只想本机能连时，把环境变量放在管道后的 `bash` 前面：

```bash
curl -fsSL https://raw.githubusercontent.com/ardeyouxipianyi/workbuddy2api-hub/main/quick-deploy.sh | WB_DEPLOY_MODE=public bash
```

- `local` / `public` 只把宿主端口绑到 `127.0.0.1`，容器内仍是 `HOST=0.0.0.0`（Docker 转发需要）；
- `public` 请再套 Nginx / Caddy / Cloudflare Tunnel 并加 TLS，不要把 8788 直接开到公网；
- 已经存在的 `docker-compose.yml` 不会被自动改写端口映射，脚本只提示手动调整。

**方式二：NAS / 面板单文件 Compose**

在 NAS 或面板的 Compose 界面新建项目并粘贴以下内容保存启动，无需拉取源码：

```yaml
services:
  wb-proxy:
    image: ghcr.io/ardeyouxipianyi/workbuddy2api-hub:latest   # 或 ardeyouxipianyi/workbuddy2api-hub:latest
    container_name: wb-proxy
    restart: unless-stopped
    ports:
      - "8788:8788"          # 左侧宿主端口可自选；右侧必须与下面的 PORT 一致
    environment:
      - HOST=0.0.0.0
      - PORT=8788
      # - API_KEY=your_secret_key   # 留空则自动生成并打印在启动日志
      - TZ=Asia/Shanghai
    volumes:
      - ./accounts:/app/accounts    # 账号凭证与配置（更新/重建容器不丢）
      - ./usage:/app/usage          # 用量流水日志（更新/重建容器不丢）
```

更新：`docker compose pull && docker compose up -d`（重建容器）。面板的「安装更新」按钮在镜像部署里默认不可用——镜像里既没有 systemd unit，也没有让 `wb_update_portable.available()` 成立的应用内 `release-manifest.json`；需要注册外部执行者（见下一节），而它只替换应用层文件，不会重建镜像。

**无 systemd 部署的面板一键更新**：容器 / LXC / 便携版没有 systemd 时，面板默认不能安装更新。部署方可以注册一个外部执行者：

1. 让网关能写请求：挂载一个目录（例如 `/run/workbuddy2api-hub-updater`），设置 `WB_UPDATE_INSTALL_ENABLED=1`、`WB_UPDATE_REQUEST_DIR=<目录>`，并设置 `WB_UPDATE_EXECUTOR=external`（或在该目录放一个 `executor.json`）。
2. 执行者监听 `<目录>/request.json`，读取 `action` / `tag` / `version` / `pid` / `port` / `root`，执行下载 → 校验 `SHA256SUMS` → 备份 → 停进程 → 替换 → 等 supervisor 拉起 → 探针 `/health`；失败回滚。`action` 缺省为 `install`，`rollback` 表示用本地备份恢复旧版本（不下载）。参考实现：`wb_update_external.py --request-dir <目录>`（需要 supervisor 在网关退出后自动拉起）。
3. 执行者写 `<目录>/status.json`，`state` 使用 `queued` / `downloading` / `verifying` / `backing_up` / `stopping` / `applying` / `restoring` / `restarting` / `succeeded` / `restored` / `rolled_back` / `failed`，面板沿用现有状态机。

保留历史版本备份：设置页可选 0–3 份（默认 1），更新成功后把旧版本的程序文件留在 `updates/backup-<这次更新去的版本>/`（内容其实是更新前的版本），面板「版本回退」据此列出可回退的版本。`0` = 不留备份，回退不可用。

约束：`accounts/`、`usage/` 不参与替换；执行者必须有应用目录写权限；网关只写请求，不碰自己的代码。

**方式三：Watchtower 自动静默更新**

```bash
docker run -d --name wb-proxy-watchtower --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock \
  containrrr/watchtower:latest --interval 86400 --cleanup wb-proxy
```

**补充与排错**

- **持久化**：`./accounts` 与 `./usage` 由宿主机挂载，更新或重建容器都不丢数据；
- **docker run 快捷启动**：
  ```bash
  docker run -d --name wb-proxy --restart unless-stopped -p 8788:8788 \
    -v $(pwd)/accounts:/app/accounts -v $(pwd)/usage:/app/usage \
    ghcr.io/ardeyouxipianyi/workbuddy2api-hub:latest
  ```
- **鉴权**：容器以 `--lan` 启动，无显式 `API_KEY` 时自动生成 Key 写入 `./accounts/settings.json` 并打印在日志里：`docker compose logs wb-proxy | grep -i "api key"`；
- **镜像名要带 registry**：写成 `ardeyouxipianyi/workbuddy2api-hub` 会去 Docker Hub 找并报 `pull access denied`，正确写法是 `ghcr.io/ardeyouxipianyi/workbuddy2api-hub:latest`（GHCR 公开包，拉取无需登录）；
- **目录权限**：默认以 root（`0:0`）运行；想以宿主用户跑就设 `PUID` / `PGID`（或 `--user $(id -u):$(id -g)`），并确保两个挂载目录对该 uid 可写；
- **健康检查**：镜像自带 `HEALTHCHECK`（每 30s 探一次 `/health`），`docker ps` 的 STATUS 列会显示 healthy / unhealthy；
- **源码构建**：`docker compose -f docker-compose.build.yml up -d --build`。

### 6. 测试

```bash
python tests/run_all.py            # 全部套件
python tests/run_all.py realm      # 只跑名字里含 realm 的
```

- 238 个套件：177 个 Python + 61 个 JS；JS 需要 PATH 上有 `node`，缺失时会跳过并提示。
- `tests/_mobile_check.py` 是独立的 Playwright 手机/桌面布局检查器（需自行安装 Playwright），按需手动运行，不在上面的套件集里。
- 本仓库**没有 CI**：Phase G 起删掉了全部自建 workflow，上面这条命令改为在本地跑（发布步骤见 [`docs/phase-g-local-release.md`](docs/phase-g-local-release.md)）。唯一留下的 `.github/workflows/release.yml` 是上游文件，只在 `v*` tag 上触发——本仓库的发布 tag 是 `fnos-X.Y.Z`，所以它永不运行。tag 与源码版本是否一致，现在由本地发布流程里的 `scripts/verify-fpk.sh` 与 `tests/_test_release_pipeline.py` 兜住。

### 7. 飞牛 fnOS 原生应用包（本仓库新增）

上游之外的这一层飞牛 fnOS（trim）打包：应用以 **fnOS 统一网关的 iframe 入口**挂在应用中心里（网关前缀 `/app/workbuddy2api`、套接字 `app.sock`），已被网关校验过身份的 NAS 用户点开面板即免密进入——unix socket 上对端（`peer uid`）校验通过即视为已登录，`X-Trim-Username` 只用来显示用户名，会话头过期不会再把人弹回口令框；绕开网关直连 TCP 端口仍然要面板口令。

```bash
bash scripts/build-fpk.sh        # 产出 dist/WorkBuddy2API-Hub_<版本>_all.fpk + .sha256
bash scripts/verify-fpk.sh       # 在本地沙箱里跑完 安装/启动/导入账号/升级/卸载
```

- 包名与显示名是 **WorkBuddy2API-Hub**，而安装标识 `appname` 仍是 `workbuddy2api`：`/vol1/@appcenter/workbuddy2api/`、数据目录 `/vol1/@appdata/workbuddy2api/`、网关前缀 `/app/workbuddy2api` 都跟着 `appname` 走，改它等于另起一套目录、把已有账号留在旧目录里读不到。
- **版本号与上游一致**：包版本就是上游最新 release tag 的三段号（`v1.6.19` → `1.6.19`），本仓库自己的发布 tag 用 `fnos-X.Y.Z`（刻意离开 `v*`：上游的 `.github/workflows/release.yml` 以 `push: tags: ["v*"]` 触发并创建 Draft Release，继续用 `v*` 会双触发）。**发布全部在本地做**（Phase G）：手动并入上游 → `PACKAGER=... VERSION=X.Y.Z bash scripts/build-fpk.sh` 构建 → `bash scripts/verify-fpk.sh` 校验 → 打 `fnos-X.Y.Z` tag 推 origin → `python3 scripts/gh-release.py release-upload fnos-X.Y.Z dist/*.fpk dist/*.sha256` 上传资产 → 回填 `fnpack.json` 的 sha256/size/updated_at。完整命令、token 与排错见 [`docs/phase-g-local-release.md`](docs/phase-g-local-release.md)。
- 打包内容、真机安装与升级（含数据目录备份）、免密口径与排错见 [`fnos/README.md`](fnos/README.md)；上架飞牛第三方源（FnDepot）的材料与说明见 [`fnpack.json`](fnpack.json) 与 [`docs/phase-f-fndepot-submission.md`](docs/phase-f-fndepot-submission.md)。

---

## 二、核心特性

### 1. 模型列表对齐官方桌面端

对官方本地配置清单（50+ 底层模型）做清洗：剔除行内补全专用模型（`codewise-*`、`completion-gf`、`hunyuan-3b/7b` 等）与多云专线变体（`*-volc`、`*-lkeap` 等），严格对齐官方 Windows 桌面端，并宣告每个模型的上下文窗口、单次最大输出、视觉支持、工具调用与推理档位。

- **🌐 国际版（17 个）**：`hy4-preview-f`、`hy3`、`deepseek-v4.1-flash`、`gpt-6-astra`、`gpt-5.6-sol`、`gpt-5.6-terra`、`gpt-5.6-luna`、`gpt-5.5`、`gpt-5.4`、`grok-4.7`、`gemini-3.5-flash`、`glm-5.3-flash`、`glm-5.3`、`glm-5.2`、`kimi-k3`、`kimi-k2.6`、`kimi-k2.8-preview`
- **🇨🇳 国内版（14 个）**：`hy4-preview-f`、`hy3`、`deepseek-v4.1-flash`、`deepseek-v4-pro`、`glm-5.3`、`glm-5.3-flash`、`glm-5.2`、`glm-5.1`、`glm-5v-turbo`、`minimax-m3`、`kimi-k3-1`、`kimi-k2.8-preview`、`kimi-k2.7`、`kimi-k2.6`

清单与上游 `GET /v3/config` 的 `agents[cli].models` 保持同步（接口不可用时依次回落到桌面端缓存文件、内置快照）；过滤规则：去掉 5 个档位别名与 `auto`、去掉 `-sg` / `-x` 变体、同名的只留 0.00 倍率那一档。上游新上架的模型无需发版即出现在 `/v1/models`。

> 同名模型（如 `deepseek-v4.1-flash`）**暂未实现跨国内 / 国际账号的混合轮询**：两个区域作为独立出口分别配置与调度，请求只走当前所选网关。这是出站指纹对齐与账号防风控的取舍，待长期实测确认稳定后再补。

### 2. 设备指纹隔离（`derive_id`）

国际版与国内版共用同一套算法内核：以账号 UID 结合固定业务盐值单向哈希派生机器码与会话标识——同一账号每次出站都来自同一台虚拟设备（不随机漂移），不同账号之间彼此独立（阻断跨账号关联风控）。

### 3. 国内版自动化

- **每日签到**：一键完成国内版打卡领积分；
- **自动连续打卡与连登管家**：每日定时为国内版账号上报轻量会话事件（复刻客户端 `chat_request_send`），点亮官方成长中心连登天数与热力墙；自动闭环检查昨日漏签（有补签卡则自动补签保连登）、领取新手礼包/补偿、兑换 7d/14d/28d 连登档位奖励，并自动抽完抽奖次数；
- **成长任务与积分任务**：自动批量接取未接任务，构造规范行为事件上报点亮（画布创建、灵感案例、模板使用、模型体验、多轮对话等 14 项），并自动领奖入账；
- **猫猫日常**：自动检查旅行状态，在家自动派出、归来自动领奖。

### 4. 后台常驻调度器

常驻后台，按固定整点执行自动化运维排程：

- **每日 09:00 & 21:00**：国内版账号自动签到、对话活跃上报（点亮连登）与猫猫旅行闭环；国际版账号执行每日活跃打卡（领官方每日 30/50 积分福利）；
- **每日 22:00**：集中扫描全库账号，Token 剩余寿命不足 2 小时自动调用 Refresh Token 保活；
- **每日 01:00**：深夜时段执行夜猫子任务；
- 看板顶部另有「立即巡检保活」与「每日活跃打卡 (国际版)」可随时手动触发。

### 5. 限额护栏（设置 → 账号限额）

四条账号级护栏放在**同一张表**里，每行一条、每列一个作用域：

| 护栏 | 作用 |
| --- | --- |
| 保留积分 | 账号余额低于该值时不再接单，避免余额被用尽后触发上游的提醒短信 |
| 每日 Token 限额 | 账号当日消耗的 token 达到该值时暂停接单，请求自动切到其他账号 |
| 每日积分限额 | 账号当日消费的积分达到该值后只服务免费模型，需要花积分的模型自动切号 |
| 按模型每日 Token 限额 | 账号在单个模型上当日消耗的 token 达到该值时只禁该模型，同账号其他模型照常 |

- **全局默认 + 可选分版本**：每条护栏的「全局默认」同时作用于国际版与国内版；勾上「分别设置国际版 / 国内版」后可单独设值，某版本**留空即继承全局**（占位符会写出继承到的数字），取消勾选再保存等于清回继承。
- 每条填 `0` 表示关闭（默认值）；四条都按**本地时间 0 点**解封，只在请求路径生效（定时任务不受影响），且都是**单账号独立计数**。
- 免费 / 付费以**各出口自己的模型目录**为准，未知模型按付费处理；账号行会显示对应徽章与 `模型 · N tok 达限` 标记。
- 某个出口的全部账号都达额时，该出口的请求返回 `429`（文案说明本地 0 点恢复，`Retry-After` 指向 0 点）。
- 存储：`accounts/settings.json` 里的一组 `limits` 映射（`{"global": …, "intl": …, "cn": …}`，`null` 表示继承全局）；旧版写在外层的四个扁平键会在第一次读取时自动折入。

### 6. OpenRouter 价估算（等价 token 花费）

把每条请求的 token 消耗按 **OpenRouter 公布的模型价**折算成等价金额，回答「这些 token 放在 OpenRouter 上值多少钱」——与账号实际扣除的积分是两个口径，看板里并列显示：

- **总开关**（「设置 → 模型价格估算」，默认开启）：关掉后价格列、「API 等价花费」卡片、取价控件与未定价清单一起隐藏，后端也不再取价与折算；重新打开会立刻抓一次价并**补算关闭期间的请求**（历史日志一个字不改，金额始终是读时算的）。
- **计价口径**：输入按缓存命中 / 未命中两档单价拆分，输出单独单价，乘 token 数再按汇率折算；输出的 token 数取上游 `completion_tokens`（已包含推理 token，不另计）。按条件定价的模型（按输入长度或按 UTC 时段）按每条请求取最紧的那一档。
- **定价来源**：OpenRouter 模型目录的**模型级公布价**。OpenRouter 把它定义为该模型 top provider 的价——对多 provider 模型通常就是最低档（实测 `deepseek-v4.1-flash` 的模型级价只比 34 家 provider 的最低价高 5%）。这组数字只用于「这些 token 放在 OpenRouter 上值多少钱」的参考估算，**不等于 WorkBuddy 官方价，也不能用于结算**。每份价格按内容存成一条「定价策略」，每条请求只记引用了哪条策略，所以之后调价不会改写历史数字；`wb_pricing.py` 另内嵌一份快照作出厂价。
- **刷新**：「设置 → 定价刷新」默认每 5 分钟一次（填 0 关闭）；只有价格真的变了才写策略与时间轴，价格不动时每轮只是一次 HTTP GET。面板可看当前生效策略、上次 / 下次取价时间与失败原因，也能点「立即取价」。
- **新增模型自动取价**：候选清单 = 内置目录 ∪ 网关实时目录，上游新上架的名字 5 分钟内进入取价；两次取价之间就被调用也会按需补价（请求路径不发网络请求）。匹配顺序：面板手填覆盖 → 人工覆盖表 → 同名唯一命中 → 变体后缀继承（剥 `-lkeap` / `-taiji` / `-volc` / `-sg` 等，仍要求唯一命中），继承可在设置里整体关掉。
- **按模型校准**：在 `usage/pricing-markup.json` 写 `{"deepseek-v4.1-flash": 5.36}` 之类的系数，估算金额会乘以它；文件缺失或值非法时按 1.0。它只影响读时估算，不改写历史策略。
- **未定价可见**：`/pricing` 列出未定价模型及分类（别名 / OpenRouter 无对应 / 剥后缀后无唯一基准）与相似候选（仅建议，不自动采用），可在「设置 → 定价刷新」为某条手填 OpenRouter id 并登记（写 `pricing-overrides.json`，不改源码，登记后立即取价）。
- **展示位置**：数据看板「API 等价花费」卡片、各账号用量透视与模型性能表**最后一列**、网关页「估算价格」卡片、最近请求**最后一列**（悬停可看完整定价链：三档原始单价、汇率、匹配证据、策略 id 与补算标记 `*`）。
- **人民币 / 美元**一键切换（记在浏览器本地）；快照覆盖不到的模型显示 `—`，不猜数字。

### 7. 本地网络工具（可选，默认关闭）

Codex App 这类客户端会在 Responses 请求里声明 `web_search` / `web_fetch`，而上游没有对应的执行器——声明送上去只会拿到一句 unsupported call。打开「设置 → 本地网络工具」后，网关把那份声明换成自己的同名 function，拦下模型的调用并在本地执行（搜索在 DuckDuckGo / Bing / Wikipedia / Stack Overflow / Google News 之间自动轮换，抓页面抓模型给出的 URL），再把结果喂回模型，最多代跑 3 轮（`WB_MAX_WEB_ROUNDS` 可调，上限 8）；搜索过程会作为 `web_search_call` 卡片事件与 `url_citation` 引用回到客户端。

- 关闭时（默认）声明原样透传，客户端自己声明的搜索工具照常拿到调用；
- 打开后网关会主动出网抓取模型给出的 URL（字面私网地址与解析进内网的域名都会被挡；
  `WB_WEB_TOOLS_PROXY` 可以给这组工具单独指定出口代理），每轮代跑都会多跑一次上游、多消耗该账号额度；
- 某个搜寻引擎被限流／拦截时会自动轮换到下一家，只有全部不可用才把明确错误交给模型；常规引擎（DuckDuckGo / Bing）接手时对模型无感，Wikipedia / Stack Overflow / Google News 这类非常规来源会在结果里标明来源；
- 只影响声明了这两个工具的客户端，普通 `/v1/chat/completions` 客户端不经过这条路径。

### 8. 智能体一键配置

看板「智能体配置」页可检测本机已装的 AI 客户端，一键把它们的配置指向本网关，改前自动备份、随时字节级还原：

| 客户端 | 写入位置 | 协议 |
| --- | --- | --- |
| Claude Code | `~/.claude/settings.json` | 原生 Anthropic Messages（自动剥 `/v1` 后缀） |
| Codex CLI | `~/.codex/config.toml`、`~/.codex/auth.json` | Responses API |
| OpenCode | `~/.config/opencode/opencode.json` | OpenAI 兼容（`@ai-sdk/openai-compatible`） |
| DSH (DeepSeek Harness) | `~/.dsh/profiles/<profile>/cordis.patch.yml`（无 profile 时回退 `~/.dsh/settings.yaml`）、`~/.dsh/.credentials.yaml` | OpenAI 兼容 |
| Crush (Charm Crush) | `~/.config/crush/crush.json` | OpenAI 兼容 |
| ZCode | `~/.zcode/v2/provider_config.json` | OpenAI 兼容（`openai-chat-completions`；**配置前先退出 ZCode**，运行中它会重写该文件） |

用法：打开看板 →「智能体配置」→ 选 API Key（支持全局默认或绑定特定出口的多 Key）、默认模型与网关地址 → 在检测到的客户端卡片上点「一键配置」；随时可点「一键还原」。

- **模型清单可控**：「网关与账号」页的「网关模型清单」每行模型 ID 前有一个复选框，**默认全部勾选**（从没动过勾选时等价于全量），表头另有「全选 / 全不选 / 反选」三个批量动作；只有勾选的模型才会被一键配置写进 DSH / OpenCode / Crush / ZCode 这类把模型清单抄进自身配置的客户端（Claude Code / Codex 不读这份清单，不受影响）。一个都没勾时，这几家的「一键配置」会直接拒绝并提示先勾选。勾选结果存在 `accounts/settings.json` 的 `agent_models` 里（对所有版本视图生效；字段缺失 = 从未保存 = 全量，空数组 = 明确全不选，两者语义不同），改完需要重新一键配置并重启对应客户端才生效；
- **非侵入**：纯标准库实现的文本级 YAML / TOML / JSON / .env 编辑器，只增量插入或更新 `wb-proxy` 那段，绝不重排或抹掉用户的注释、缩进与其他 provider 配置；
- **可回滚**：写入前自动备份到 `accounts/agent-backups/<客户端ID>/`（每文件保留最新 10 份），首次接入的原件永久保留；多文件客户端（DSH、Codex）两阶段写入，任一文件失败立即回退；
- **还原**：byte-exact 回到首次接入前，网关新建的文件会被清理；若之后手动改过配置，看板会提示「检测到外部修改」，还原仍会覆盖回原件；
- **密钥安全**：API Key 只写进客户端自己的本地配置目录（权限仅限当前系统用户），单文件超过 8MB 拒绝编辑。

**DSH：思考档位、上下文窗口、识图与限流重试写在哪**（`~/.dsh/profiles/<profile>/cordis.patch.yml`）

当前 DSH 只在首次启动时导入一次 `~/.dsh/settings.yaml`，随后改名 `settings.yaml.imported`，之后不再读它；桌面版 / Web 版真正生效的是各自 profile 的 `cordis.patch.yml`。一键配置因此直接写这一层（`~/.dsh/settings.yaml` 只在它本来就有、或机器上还没有 profile 时写入）。给 DSH 写的每个模型条目都带上网关宣告的规格，DSH 会据此生成它自己的选择器：

```yaml
    wb-proxy:
      api: openai-completions
      baseURL: http://127.0.0.1:8788/v1
      compat: {thinkingFormat: openai, supportsReasoningEffort: true}
      retryPolicy:                     # 限流等待：见下「限流重试」
        mode: normal
        maxRetries: 8
        backoff: {initialDelayMs: 2000, maxDelayMs: 30000, jitterRatio: 0.1}
      models:
        - id: deepseek-v4.1-flash
          contextWindow: 1000000     # 客户端认为的上下文容量（压缩 / 截断按它算）
          maxTokens: 128000          # 单次输出上限
          input: [text, image]       # 输入模态：不写 image 就贴不了图
          reasoningEfforts:          # 会话里可选的思考档位：键=档位，值=发给网关的拼写
            low: low
            high: high
            max: max
```

- **识图**：DSH 只认模型条目里的 `input`（`inputModalities`）声明，不读 `supportsVision`，也不读 `/v1/models` 里的能力字段。所以网关宣告 `capabilities.vision` 的模型都会写上 `input: [text, image]`，纯文本模型（如 `glm-5.3-flash`）不写。缺了这一行，贴图会被 DSH 直接拒掉：`Model "<id>" does not support image input.`
- **思考程度在 DSH 里怎么选**：不在「设置 → 模型」页（DSH 有意不把 per-model 的档位放进 provider 级表单），而在**输入框旁的模型菜单**：菜单里有两行 `模型` 与 `推理等级`，点「推理等级」选档位；`/model` 弹窗只列模型、不列档位。选项完全来自上面的 `reasoningEfforts` —— 不声明就没有这一行（`/v1/models` 里的 `reasoning_efforts` DSH 不读，它只读 `id` / `name` / `contextWindow` / `maxTokens` / `input`）。
- **上下文长度怎么改**：`contextWindow` 就是 DSH 用的容量。改客户端侧就编辑这一行（或在 DSH 的模型编辑界面里填），改网关侧就改 `/v1/models` 宣告的 `context_length`；两条链路现在共用 `wb_modelsdev.lookup` 的同一套取值（上游值 > 内建知识表 > 本地缓存 > 1M 默认），不会再出现「网关宣告 1M、一键配置写 300k」这种对不上的情况。
- **上游钉死档位的模型**（目录里只有 `reasoning.effort`、没有 `supportedEfforts`）不写 `reasoningEfforts`：给了选择器也不会改变上游实际跑的档位。
- **限流重试（「对话到一半链接中断」的根因）**：DSH 对失败请求的重试由每个 provider 自己的 `retryPolicy` 决定，默认 normal 模式、最多 5 次、退避 500ms 起按 2 倍翻、封顶 10s——五次加起来不到 16 秒。WorkBuddy 的模型冷却（429）通常要一分钟，DSH 在冷却结束前就把重试次数用光，回合以 `RATE_LIMIT` 失败，客户端看到的就是对话中途断掉。一键配置因此给 `wb-proxy` 单独放宽成最多 8 次、退避 2s 起、封顶 30s（合计约 2 分半），足够熬过一次 60 秒冷却。字段名与取值范围按 `@deepseek-ai/dsh-llm` 的 `RetryPolicySchema`；不写 `retryableCodes`，沿用 DSH 默认（`EMPTY_RESPONSE` / `RATE_LIMIT` / `SERVER` / `TIMEOUT` / `TRANSPORT`，429 落在 `RATE_LIMIT`）。只影响 `wb-proxy`，其它 provider 仍是默认策略；已经接入过的机器重新点一次「一键配置」补上这段（幂等），重启 DSH 生效。
- **注意 profile 覆盖层**：`$DSH_HOME/profiles/<profile>/cordis.patch.yml` 里的 `- id: llm-pi-ai` 条目会**整体替换**该插件的配置（不是逐键合并）。一键配置现在直接更新 patch 层里的这一条：只替换 `wb-proxy` 那段，其他 provider（如 `qwen-token-plan-cn`）、其他条目与注释原样保留，所以不会再出现「写进 `settings.yaml` 被 patch 盖住、不生效」的情况。

**在另一台机器上接入（远程 / 非本机）**：看板的一键配置运行在网关进程里，改的是**网关所在机器**的配置目录——所以它只在网关本机、且用 `127.0.0.1` 打开看板时可用（远程访问、容器 / OpenWrt 部署下按设计隐藏入口）。客户端装在别的电脑（网关跑在服务器 / NAS / 路由器上）时，改用自带的配置器 CLI：它在**客户端所在的机器**上运行，写本机配置、只通过 HTTP 从网关取模型表：

```bash
# 1. 取配置器（网关直接提供该文件；也可从仓库 / 绿色包复制 wb_agents.py）
curl -fsSL http://<网关地址>:8788/agents/cli -o wb_agents.py

# 2. 一条命令接入（需要 Python 3.9+，Key 在「设置」页生成）
python wb_agents.py list                                   # 本机装了哪些客户端
python wb_agents.py apply --client codex --base-url http://<网关地址>:8788/v1 --key sk-xxxx
python wb_agents.py restore --client codex                 # 随时字节级还原
```

- 支持 `claude-code` / `codex` / `opencode` / `dsh` / `crush` / `zcode` 六个客户端，与看板共用同一套写入、备份与还原逻辑（`plan()` 同时驱动 `--dry-run` 与真实写入）；
- 默认带 Key 请求一次 `GET /v1/models`：既为 OpenCode / DSH / Crush / ZCode 填入模型表，也顺带验证 Key（401 = Key 被拒）；网关不可达或想完全离线时加 `--no-models`；
- 状态与备份存在该机器自己的 `~/.wb-agent-config/`（可用 `--state-dir` 覆盖），每台机器一份，`restore` 只对执行过 `apply` 的机器有效；
- `--dry-run` 只打印将要写入的内容、不落盘；Key 也可用环境变量 `WB_PROXY_API_KEY` 传入。

模块内部设计与新增客户端的方法见 **[docs/CONTRIBUTING-智能体配置.md](docs/CONTRIBUTING-智能体配置.md)**。

### 9. 剩余用量估算（数据看板 → 剩余用量估算）

上游按 **24 小时窗口**给「账号 × 模型」配额（用满时 429 / code 6004 会带上重置墙钟），但从不告诉你这个窗口的预算是多少。看板新增的「剩余用量估算」区块把它反推出来：

- **预算 = 撞线账号窗口用量的平均**：账号撞线（收到带重置时刻的 429）的那一刻，它在该模型上「自窗口起点以来的成功用量」就是预算的一个样本；按区域聚合、先按账号平均再跨账号平均。样本在 429 处理的那一刻就记进 `usage/limit-events.jsonl`（重试循环里只有最后一个账号会留下带归属的 429 用量行，光靠日志会漏掉大部分撞线），历史日志里带账号的 429 行作为补充，两者按「账号 + 模型 + 重置时刻」去重。
- **已用从每个账号自己的重置时刻起算**：窗口起点取该账号该模型最近一次重置时刻；重置时刻在未来的组合（正在冷却）剩余记 0 并显示恢复时间。
- **没有撞线记录的组合标「按 24h 估算」**：窗口起点未知时按最近 24 小时用量统计——窗口起点必然落在最近 24h 内，所以这是剩余量的**下界**（偏保守，不会高估）。
- 接口 `GET /usage/remaining`（需面板会话）返回 `budgets`（每个区域 × 模型的预算均值 / 区间 / 样本数）与 `rows`（每个账号 × 模型：已用、预算、剩余、窗口起点、是否冷却、是否估算），区块只读不写，不参与请求路径（唯一的请求路径接触点是撞线时记一行事件）。
- **查询侧不做重复计算**：每个「账号 × 模型」的用量缓冲是**时间戳 + 累计和**两个列表（窗口求和 = 两次二分 + 一次相减，O(log n)，内存约 16 字节/行），载荷再挂一个短 TTL（`WB_REMAINING_TTL`，默认 15 秒）并支持 `ETag` / `If-None-Match`：面板 5 秒一轮的轮询在 TTL 内直接拿上次算好的载荷（连日志尾部都不再扫），带条件请求时回 304。实测（2 万行缓冲）：单次重建 ~0.7ms（旧版逐行重算 ~1.8ms）、轮询一分钟 2.9ms（旧版 21.5ms）、缓冲内存 321KB（旧版 2.3MB）。

### 10. 积分获取历史（数据看板 → 积分获取历史）

「积分扣减历史」看的是花掉的部分，这一块补上进账的部分：上游对每个账号返回一份**积分包清单**（每日活跃奖励的 Bonus Pack、免费套餐、活动包…），每个包带面额、发放时间与到期时间。区块把全部账号的包摊平成一张表、新的在前：

- 列：时间（发放）/ 账号 / 区域 / 名称 / **来源** / 积分 / 剩余 / 到期 / 状态；
- 状态按「过期 > 用完 > 在扣减 > 可用」归类：**生效中**（上游标了 `in_usage`，当前正从它扣减）、**可用**、**已用完**、**已过期**；`no_expiry` 的包显示「不过期」；
- **来源**：上游自带的发放原因原样显示（如「Buddy 加油站签到」「成长计划奖励」「官方活动发放」）；国际版的 Bonus Pack 30/50 没有原因字段，按官方规则推断为「每日活跃奖励」（悬停里注明这是推断）。我们自己的**签到 / 每日活跃**记录也会按时间关联上去（取发放前 2 小时内最近的一次尝试，带成功 / 失败），悬停即可对上「本机动作：每日签到 10-10 00:07 成功」——一次发放到底由哪次动作带来，一眼可见；
- 摘要行给出笔数、合计面额、合计剩余与**快照时刻**。接口 `GET /accounts/credits/grants` 只读内存里的积分快照、**不发上游请求**——数字的新鲜度取决于最近一次「一键刷新积分」（签到与每日活跃打卡也会顺带刷新它），所以要看最新的包先点账号页那个按钮。

### 11. 单请求体体积限制（`WB_MAX_PAYLOAD_BYTES`）

针对携带超长历史、大内联附件或高分辨率图片的请求，网关默认对单次请求体做上限保护（默认 16MB = `16777216` 字节），以防止异常巨大的请求挤占内存。若请求体超过上限，网关在解析前即直接返回 HTTP 413（`payload too large` 并附带 `gateway_hint` 说明）。

如需调整上限（例如提升至 32MB）：
- 设置环境变量 `WB_MAX_PAYLOAD_BYTES=33554432`（单位为字节）；
- 此环境变量仅在进程启动时读取一次，修改后重启 `wb-proxy` 即可生效。

### 13. 流式响应空闲心跳（`WB_STREAM_KEEPALIVE_SECONDS`）

网关的流式响应（`/v1/chat/completions`、`/v1/responses`、`/v1/messages`）只在**上游吐字节**时才往客户端写。上游长思考、排队或卡住时，链路上任何「按多久没收到字节判活」的设备都会把连接掐掉 —— nginx 的 `proxy_read_timeout` 默认就是 60 秒，Lucky / 路由器 / Cloudflare 隧道同理 —— 客户端看到的是「回答到一半断线」，而服务端日志里只有一次 `client_aborted`。

本版起，三个流式出口在空闲时补一行 SSE 注释 `: keepalive`（注释行任何客户端都会忽略，不改协议，也不影响任何 SDK 的解析）：

- 默认 **15 秒**（上游 `SSE_HEARTBEAT_SECONDS`，v1.7.33 起就是这条实现）；一直在出字的流里**一次都不写**，所以既不增加延迟、也不会污染内容；
- `WB_STREAM_KEEPALIVE_SECONDS=0` 关闭（确认链路没有空闲超时，或要抓包看原始帧时用）；
- 上限 300 秒；空值 / 非法值回落到默认 15 秒；每次建流时读取，改完重启 `wb-proxy` 生效。

这套心跳是**产品侧**的修法：不用改 Lucky / nginx / 隧道配置，也不会因为换一条链路就复发。

---

### 12. 后台模型重定向（`WB_BACKGROUND_MODEL_NAMES` / `WB_BACKGROUND_MODEL_TARGET`）

桌面客户端（Codex 等）的模型选择器**只管主对话线程**。客户端内置的「模型路由配置」会把后台工作——记忆生成、环境建议、临时内容生成、自动化任务——送到自己硬编码的模型上，UI 里选什么免费模型都改不掉。这些请求带着同一把 Key 打到网关，于是在共享 Key 的部署里悄悄烧付费积分。

网关在唯一的 POST 分发点（选账号之前）把这类模型名改写成免费目标：

- `WB_BACKGROUND_MODEL_NAMES`：要拦截的模型名清单（逗号分隔，大小写不敏感），默认 `gpt-5.6-terra,gpt-5.6-luna,gpt-5.3-codex`；
- `WB_BACKGROUND_MODEL_TARGET`：改写目标，默认 `deepseek-v4.1-flash`。

改写只动 `model` 字段，请求体其余部分原样透传；命中与改写都会记一条 `alias: background model X -> Y` 日志，方便核对。OpenAI 形状的两个路由（`/v1/chat/completions`、`/v1/responses`）与 Anthropic 形状的 `/v1/messages` 都覆盖。不需要时把名单设为空即可关闭。

---

### 13. 自签证书 / TLS 解密代理（WB_CA_BUNDLE）

如果网关跑在公司代理、Clash/Surge 等 HTTPS 解密后面，或 macOS 上 Python 没有读到系统钥匙串里的根证书，上游请求会报 CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain，面板上的 OAuth 登录和账号测试会显示 502。把签发该证书的根证书导出为 PEM，然后设置 WB_CA_BUNDLE=/path/to/ca.pem（优先）或 SSL_CERT_FILE=/path/to/ca.pem，重启 wb-proxy。网关会在系统根证书之外追加这份 PEM，不关闭证书校验；证书错误也不再重试，日志和面板会直接给出这段提示。

---

### 14. 国内版上游地址（`WB_CN_CHAT_UPSTREAM`）

国内版对话侧默认发往 `https://copilot.tencent.com`。网关跑在海外出口后面（代理软件的全局模式、海外服务器）时，到它的 TLS 握手会被复位，日志里是 `SSL: UNEXPECTED_EOF_WHILE_READING` 或 `WinError 10054`，国内版账号的对话、刷新 token、模型目录、签到与成长任务全部失败。`www.workbuddy.cn` 提供同一套接口且海外可达（官方桌面端当前即以它为 endpoint，VSCode 身分本来也走它）。

- 设置 `WB_CN_CHAT_UPSTREAM=https://www.workbuddy.cn`，重启 `wb-proxy`；启动日志的 `realm` 行会显示新的出口，并多一行 `cn upstream: ... (WB_CN_CHAT_UPSTREAM)`；
- 只改「往哪发」：`X-Domain` 仍用账号登录时记下的 domain，计费侧（`www.codebuddy.cn`）不变；
- 不是 `http(s)://` 开头的值会被忽略并回落默认地址，启动日志给出提示；不设则行为与此前完全一致。

---

## 三、账号添加与管理

打开看板 `http://127.0.0.1:8788/`，在「账号」区域操作。若上游对某账号的单个模型返回 429，账号行会显示受限模型与预计恢复时间（浏览器本地时间），该账号仍可用于其他模型；模型冷却只在当前进程内保留，重启清空。

窗口探针管的是「已经撞到 429 之后」；想提前知道某条配额线有没有被打满，可在「设置 → 模型额度定时主动查询」勾选模型：网关每 6 小时为每个「账号 + 模型」发一个最小请求做体检，查到 429 就立刻记该模型的冷却并把重置时刻交给窗口探针，请求通了就说明还没到限额。一旦某个「账号 + 模型」已经有了登记的 429 记录，就停止定时查询（改由窗口探针负责），记录消失后自动恢复轮询；每次查询都会消耗该账号极少量额度，默认不勾选任何模型。

### 方式一：浏览器 OAuth 授权（推荐，免客户端）

1. 点「+ 添加账号 (OAuth)」；
2. 选择要登录的区域（国际版 / 国内版），点弹出的官方授权链接并在浏览器完成登录；
3. 程序自动检测回调，账号自动加入账号池，无需手动复制凭证。

### 方式二：从本机桌面客户端导入

1. 让 **WorkBuddy 桌面客户端保持运行并已登录**（Windows 上网关要从它的进程内存里取解码密钥，这一步不能省）；
2. 看板点「扫描桌面客户端账号」，弹窗列出本机已登录的国际版 / 国内版账号；
3. 若提示凭据已加密，先把解码密钥交给网关，再点账号行的「导入」：
   - **Windows**：点弹窗里的「回收密钥」（只读，实测 1 秒内完成）；
   - **macOS / Linux**：进程内存回收只在 Windows 上实现，弹窗里会直接给出输入框，粘贴密钥即可（见下）。

关于加密凭据：桌面客户端从 2026-09-24 起把 `accessToken` / `refreshToken` 存成 `$wbEncrypted` 信封，网关按客户端 `packages/at-rest-crypto` 的同一套方案（AES-256-GCM + `WB-AAD` 帧头）就地解密，导入的仍是可直接使用的 token；解码密钥编译在客户端原生模块里、磁盘上没有明文。Windows 上可以从**正在运行的**桌面端进程内存里找回（只读 `OpenProcess(PROCESS_VM_READ)` + `ReadProcessMemory`，不向客户端写任何东西）；macOS / Linux 上没有这条路，看板会显示输入框让用户**手动粘贴**一次——两种方式拿到的密钥都只留在网关进程内存、不落盘不写日志，且都要先过 keyblob 自检（protectorKeyId 对得上、能解出 32 字节主密钥）才生效。

手动粘贴接受两种写法（都不用自己换算）：64 位 hex 的保护密钥，或 44 字符 base64 的 `atRestSecretKey`。拿不到密钥时，macOS / Linux 上请直接用方式一走浏览器登录。提示权限不足时，以管理员身份启动网关再试一次。

---

## 四、客户端配置与接入

- **API 接口地址 (Base URL)**：`http://127.0.0.1:8788/v1`（局域网为 `http://<局域网IP>:8788/v1`）
- **API Key**：本机单机模式（未配置 Key 且未开 LAN）可留空或填任意字符；已在看板配置 Key 或 LAN 模式，请用看板「设置」页里绑好出口的 Key；
- **模型名称**：填 `/v1/models` 里列出的任意官方对齐模型 ID（如 `deepseek-v4.1-flash`、`gpt-6-astra`、`glm-5.3`）。

**Codex CLI / Claude Code（Responses API）**

```bash
export OPENAI_BASE_URL="http://127.0.0.1:8788/v1"
export OPENAI_API_KEY="你在看板设置中添加并绑定的API_Key"
```

**Claude Code / Anthropic SDK（实验性 Anthropic Messages 适配，默认禁用）**

> ⚠️ **积分风险：默认拒绝调用。** 网关对外接受 Anthropic Messages，但对内将请求转换为 WorkBuddy 的 `/v2/chat/completions`；`cache_control` 被忽略。已有 [#367](https://github.com/ardeyouxipianyi/workbuddy2api-hub/issues/367) 报告长会话缓存命中率仅约 11%，单次消耗超过 100 积分。该问题的因果机制仍待定位，故暂时默认禁用整个 Anthropic Messages 入口，而不假装完全兼容。禁用时 `/v1/messages`、`/messages` 及对应 `count_tokens` 入口返回 Anthropic 格式的 HTTP 400（`invalid_request_error`），请求不会转发至上游。

只有确认理解风险后，才在**网关服务端**显式设置 `WB_ENABLE_ANTHROPIC_MESSAGES=1` 并重启。Docker Compose 可在 `wb-proxy.environment` 中加入 `- WB_ENABLE_ANTHROPIC_MESSAGES=1`；其他环境则在启动网关前设置此环境变量。客户端配置示例：

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8788"
export ANTHROPIC_API_KEY="你在看板设置中添加并绑定的API_Key"
```

实验性适配包含 `system`、`text`、`image`、`document`、`tool_use`、`tool_result`、`tools` 与 `tool_choice` 等字段转换，并将响应包装为 Anthropic 的流式事件序列或非流式消息。这不是向上游的原生 Anthropic 透传。

已知边界：服务端工具（`web_search` 等）上游不支持，会被丢弃并在 system 里注明；`thinking` / `redacted_thinking` 历史块不回放；`top_k`、`cache_control`、`context_management` 与 `betas` 被忽略；`/v1/messages/count_tokens` 在显式启用后只提供网关的 CJK 感知估算值，**不是**官方分词器的精确值。

---

## 五、看板与接口一览

访问 `http://127.0.0.1:8788/` 使用集成看板：顶部页签默认是「网关与账号 / 数据看板 / 智能体配置 / 设置 / 运行日志」，每个主页面左侧有一条按页面区块现场生成的导航（点击直达、滚动高亮、地址栏带锚点，可收起成窄轨）。

账号多起来之后（国际版十几个），账号列表与「当前禁用」总览会把网关页挤下去。设置页的「账号独立成一个页签」默认关闭，账号区就留在「网关与账号」页（位置与拆分前一致）；打开后它们和签到记录一起成为独立的「账号」页：添加 / 导入 / 导出、启用停用、凭证与积分刷新、代理出口绑定都在那里，顶部页签变成「网关 / 账号 / 数据看板 / 智能体配置 / 设置 / 运行日志」。页内的「签到与活跃记录」读 `GET /activity/history`，可按**区间 / 任务 / 结果 / 账号**筛选（筛选在服务端做），一行一次真实尝试，列出 时间 · 账号 · 区域 · 任务 · 来源 · 结果 · 说明，最新在前；超过一页时用「加载更多」往下翻，上限 1000 行——「这个账号昨天到底签成了没有」不用再去调度器日志里翻。

「数据看板」页顶部可切换统计口径：**今日 / 本周 / 本月 / 全部历史 / 自定义**（本周自周一零点起算、本月自 1 号零点起算，任一侧留空表示不限），切换后 KPI 卡片、账号用量透视表与模型性能表一起切到同一窗口。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | / | Web 用量与任务监控看板 |
| POST | /v1/chat/completions | 标准 Chat Completions 接口 |
| POST | /v1/responses | Responses API 协议接口 |
| POST | /v1/messages | 实验性 Anthropic Messages 适配，默认禁用（HTTP 400）；需显式启用并承担缓存风险 |
| POST | /v1/messages/count_tokens | 实验性 Anthropic 计数估算接口，随 Messages 入口默认禁用 |
| GET | /v1/models | 官方对齐模型列表（含能力与规格宣告） |
| GET | /u/\<ref\>/v1/models | 定址账号的模型清单：\<ref\> 支持完整 uid / uid 前 8 位 / 昵称，过滤该账号禁用模型 |
| POST | /u/\<ref\>/v1/chat/completions | 定址调用：锁定该账号，不参与会话亲和 / 轮换 / 自动换号；账号不可用直接报错 |
| POST | /u/\<ref\>/v1/responses | 定址 Responses API，语义同上 |
| GET | /v1/balance-summary | 当前 API Key 所属区域的启用账号积分汇总；只读内存快照、不发上游请求，不返回账号身份 |
| GET | /pricing | 定价状态：当前生效策略、上次/下次取价时间、未定价清单（分类 + 候选） |
| POST | /pricing/refresh | 立即取一次价（需面板会话） |
| POST | /pricing/mapping | 手填 / 清除「模型 → OpenRouter id」运行期映射，随后自动取价（需面板会话） |
| GET | /agents | 客户端探测概览、支持的模型清单及网关连接地址 |
| GET | /agents/cli | 智能体配置器源码（供远程机器直接 `curl` 取用，免面板鉴权；与仓库内 `wb_agents.py` 逐字节一致） |
| POST | /agents/apply | 一键写入客户端配置并备份原件（需面板会话） |
| POST | /agents/restore | 一键还原客户端至首次配置前的状态（需面板会话） |
| GET | /tasks | 国内版成长任务、连续打卡与猫猫日常状态 |
| POST | /tasks/run | 触发国内成长任务全自动点亮与领奖 |
| POST | /tasks/travel | 触发猫猫日常旅行（派出 / 领奖） |
| GET | /scheduler | 定时调度器运行状态与排程日志 |
| POST | /scheduler/trigger | 手动立即执行后台巡检保活 |
| GET | /activity/history | 账号每日活动历史：签到与每日活跃的每一次真实尝试（`range` / `uid` / `task` / `result` / `limit`，最新在前） |
| GET | /accounts/credits/grants | 积分获取历史：各账号积分包（发放时间 / 面额 / 剩余 / 到期 / 状态），只读内存快照、不发上游请求 |
| GET | /usage/remaining | 剩余用量估算：每个账号 × 模型在当前 24h 窗口的已用 / 预算 / 剩余（预算取撞线账号的平均用量；需面板会话） |

---

## 六、版本更新记录 (Changelog)

<!-- 发版时：把下面的 Unreleased 段落整理成新版本号（## vX.Y.Z），整体移入 docs/CHANGELOG.md 顶部 -->

- **1.8.0.4 修正（Phase T）：1.8.0.3 的兜底救回了请求，但顺手把整天的系统提示换掉了**：1.8.0.3 装上去十分钟内就抓到一次真实 11128 —— `10:33:43` 的 `msgs=83` 请求三次换号（间隔 0.5 / 1.5 / 3.5 秒，全被拒）之后，`10:33:51` 的中性提示重试在 `10:33:56` 把它救回成 **200**（`tokens=207568`），用户侧不再以 400 结束。但那次兜底触发的是**进程级**降级窗口（照抄 403 内容审查的语义，到次日 00:00 CST 才复位），于是当天其余 `passthrough`/`append` 请求的系统提示全被换成 28 字中性提示 —— 对一个靠系统提示干活的编码 agent 来说这是悄无声息的降级。本版改成**只借这一条请求**：`PROMPT_DEGRADE.trigger()` → `build_upstream_body()` → 立刻 `reset()`（若进分支前窗口本来就是活的则不动，保住 403 那条保护），`custom` 模式依旧永不降级。同时修掉 dump 写不进去的隐患：应用以 `workbuddy2api`（uid 946）运行，`/tmp/wb-waf-dumps` 若是 root 建的 0755 目录就写不进、异常被吞（真机现场一条 dump 都没有），现在套件自己在 `mkdtemp` 里跑，`/tmp/wb-waf-dumps` 只留真机现场（宿主机上已改为 1777 供应用写入）。包版本 `1.8.0.4`，装机走应用中心 `update/task` RPC；装机后 `/health`、非流式（41/2/43 tokens）实测 200。
- **1.8.0.3 热修（Phase S）：换号真的换了，但三个账号都被同一条正文拒**：1.8.0.2 装到设备后换号日志终于出现（`09:22:56 ... rotating to another account (attempt 1/2)`、`(2/2)`），可客户端拿到的还是 400——三次尝试在 **1.3 秒**内打完，`open_upstream()` 的 `tried.add(account.uid)` 保证换到的是不同账号，而三个不同账号对同一条正文给出同一个判定，说明判定随**内容**走；同时 `usage.jsonl` 里 27–28 日 1829 条请求中 `n_msgs>=100` 的请求绝大多数 completed（最高 550 条消息 / 521k tokens），所以体积/条数也不是触发条件。本版三处改动：① 换号预算 `WAF_RETRY_ATTEMPTS_DEFAULT` 2 → 3；② 每次换号前按 `WAF_RETRY_DELAYS = (0.5, 1.5, 3.5)` 退避（`waf_retry_delay()`），不再一秒内连打三次，给抽样判定留出不同的采样点；③ 预算耗尽仍被拒、且提示模式是 `passthrough`/`append`（不是用户自定义提示）时，触发一次 `PROMPT_DEGRADE` 中性提示重试——403 内容审查的兜底早就这么做，这里只试一次。另外每次被拒把请求形状（`system` 头 8 KB + 尾 2 KB、逐条消息长度、正文 sha256、账号/`realm`/`product`/模型/流式）落到 `/tmp/wb-waf-dumps/`（`WB_WAF_DUMP_DIR` 可改，最多 24 份，**不写数据目录、不落 messages 原文**），下次现场直接比对。`tests/_test_waf_channel_retry.py` 9 → **13 项**（换号等待逐次拉长、预算耗尽降级重试、降级只试一次、dump 形状）。包版本进到 `1.8.0.3`，装机走应用中心 `update/task` RPC，装机后 `/health`、非流式（41/2/43 tokens）、流式（53 帧）实测均 200。
- **1.8.0.2 热修（Phase R）：修 1.8.0.1 那个「装了也不生效」的换号重试**：1.8.0.1 装到设备后，2026-10-28 08:52 两次真实 11128 仍然原样透传 400，日志里**一条换号记录都没有**。根因是 `upstream_error_code()` 走 `json.loads`，而 `http_error_detail(exc)` 只留 **600 字节**——上游错误信封自带 `displayMsg` + `displayTips`（en/zh/zh-hant）再加 `actions`，实测同款 `11101` 正文就是 **684 字节**，截断后 JSON 必然解析失败、code 变成 `None`，`WAF_TRANSIENT_ERROR_CODES` 永远不命中。现在解析失败时按头部正则 `_UPSTREAM_CODE_RE`（只扫前 512 字符）兜底——code 永远是信封第一个字段，403 的 `restriction_is_account_level` 早就这么做了；同一个兜底也让 5xx 的模型级错误、11140 的账号级限制在长正文上不再漏判。`tests/_test_waf_channel_retry.py` 5 → **9 项**（真实现场长度正文、半截 UTF-8/半截 JSON 正文、截断正文下预算依旧有界、`upstream_error_code` 直接断言）。包版本进到第四段 `1.8.0.2`（应用中心只按版本号判断升级）；装机走应用中心的 `update/task` RPC——`trim-cli app install-fpk` 对已装应用永远 `10236`（app already installed）、`trim-cli app update` 强制先做云下载 `10030`，细节见 `docs/phase-f-delivery.md` 顶部「装机路线」。装机后 `/health`、非流式、流式实测均 200。
- **1.8.0.1 热修（Phase Q）：11128 渠道校验 400 时换号重试**：上游 2026-10-27 下午起对 Web 凭证加抽样渠道校验（HTTP 400 `code=11128 Illegal API invocation from an unapproved channel`，issue #674/#675/#676/#677），同一会话 `msgs=95` 在 22:28:39 被拒、22:28:40 立刻成功——**判定是抽样，不是内容指纹**（21 次对照探针全部 200）。旧实现把 400 一律原样透传，于是一次抽样就打死整轮。现在 `open_upstream()` 的 400 分支先 `upstream_error_code()` 解析正文，命中 `WAF_TRANSIENT_ERROR_CODES = frozenset((11128,))` 且预算未用完时换号重试（`WB_WAF_RETRY_ATTEMPTS`，默认 2，`0` 关回旧行为），被拒账号**不记账、不冷却**（它没做错什么），预算用完仍把原始 400 交回客户端且正文可读；其它 400 一次出站、立即抛出。新增 `tests/_test_waf_channel_retry.py`（当时 5 项，现 9 项）。**包版本按用户要求改为第四段 `1.8.0.1`**：应用中心不会把「同版本号、新字节」当成升级、装不进去，所以 1.8.0 的「包版本 ≡ 上游最新三段 tag」政策本轮显式豁免（不是 Phase E 那个 ordinal 机制，上游下一个 release 回到三段号），`build-fpk.sh` / `verify-fpk.sh` 与相关套件的版本正则放宽为「三段 + 可选第四段」。装机走应用中心/`trim-cli app install-fpk`，数据目录不碰。
- **v1.8.0 发布**：汇总 v1.7.33 之后的 #640、#642、#643、#645/#647，并补齐 #578、#618、#625 的发布记录。完整变更、验证范围与已知限制见 **[docs/CHANGELOG.md](docs/CHANGELOG.md#v180)**；下一版的改动继续写在本段。
- **修复数据看板在桌面上只显示一列（1.8.1 热修）**：上游 v1.7.30 在统计条上加的 `@media (max-width: 860px)` 与本层的移动端兜底规则在同一位置合并时少了一个收尾的 `}`，于是它把**后面全部规则**（整个 `#pageAnalytics` 看板设计、`.wb-help` 使用说明）都吞进了「窄屏才生效」的分支。症状不是报错而是静默降级：宽屏下类看板没有六列栅格，KPI 卡片一张一行、行高巨大，「请求数 / 生成速度 / 积分消耗」被拉开到屏幕各处。修法是补回那个 `}`（让 `#pageAnalytics`、`.wb-help`、`#cockpitRealm`、`#cards` 都回到嵌套深度 0），并新增 `tests/_test_dashboard_css.py` 钉死三件事：每个 `<style>` 块的 `{`/`}` 必须等量、关键字面规则必须在深度 0、深度大于 0 的规则只能待在 `@media`/`@keyframes`/`@supports` 里面（漏一个括号就会在下一轮静默复发）。
- **飞牛 fnOS 这一层：并入上游 v1.8.0（Phase P）**：合并基从 `47775c5`（v1.7.33）推进到 `4f7ae6f`（`release: v1.8.0`，该 tag 就是上游 `main` 的头），共 **5 个提交、16 个文件、+823/-60**，全部是修 bug：国际版沙箱证书失败时降级到活跃上报（`#647`）、`stderr` 日志通道不再阻塞请求线程（`#644`，日志写失败不再拖住整条请求）、桌面 chat 可选协议一致性（`#643`，`/v1/chat/completions` 的 `protocol` 与客户端身份对齐）、更新检查超时放宽到 10 秒（`#640`）。新增套件只有 `tests/_test_daily_chat_activity_fallback.py` 一个，**不需要动打包侧**（没有新顶层模块，`build-fpk.sh` 的守卫名单与 `PKG_MODULES` 原样）。合并侧只有 `README.md` 一个冲突文件：套件数按合并后的树重算为 **236 = 175 Python + 61 JS**（上游侧那 11 行历史数字继续作废），变更记录段保留本仓库的 Phase 条目并新增本条。上一轮把流式心跳交给上游 `SSEHeartbeat` 之后，本层没有新的重复实现要合。
- **飞牛 fnOS 这一层：并入上游 v1.7.30–v1.7.33（Phase O）**：合并基从 `af37786`（v1.7.29）推进到 `47775c5`（`release: v1.7.33`，该 tag 就是上游 `main` 的头），共 **15 个提交、26 个文件、+3005/-1336**，覆盖 v1.7.31 / v1.7.32 / v1.7.33 三个 release。上游这一批的主线是「网页活跃的收尾与流式心跳转正」：每日活跃重构为「一个预算 + 一个候选序列」（`#632`），失败收尾登记保留并迁移旧配置（`#638`），登记表与被放弃的线程都加上界（内存不再随失败次数增长），网页会话收尾不再依赖卡住的那条线程；模型级 429 冷却窗口重启后能恢复、成功请求会解除凭证失效标记；`responses` 补发工具调用首段参数增量；面板校正调色对比度并提示 HTTP 入口；网关恢复模型别名并**自己补上了流式 SSE 心跳**（`#578`，`SSEHeartbeat`，默认 15 秒）。心跳这块因此由「本仓库独有」变成「上游实现 + 本仓库的旋钮」：删掉本层那份 `StreamKeepalive`，改用上游的 `SSEHeartbeat`（`with heartbeat:` 收尾、三个流式出口一致），只把 `WB_STREAM_KEEPALIVE_SECONDS` 保留成覆盖默认值的旋钮（0 关闭、上限 300 秒），并给上游的 `tests/_test_stream_keepalive.py` 追加了一节旋钮断言。合并侧 3 个冲突：`README.md`（套件数按合并后的树重算为 **235 = 174 Python + 61 JS**；上游侧那 11 行历史套件数全部作废；指针改为 `v1.4.5 ~ v1.7.33`）、`tests/_test_stream_keepalive.py`（add/add —— 两边都新增了同名文件，取上游那份当基线 + 追加本层的旋钮用例）、`wb_proxy.py`（6 段全是 `keepalive` ↔ `heartbeat`，一律取上游结构，并删掉本层残留的两处重复构造）。打包侧本轮**无需新增模块**（上游这 15 个提交没有新顶层文件），`tools/`/`ops/`/`catalog/`/`logs/` 的排除与守卫名单照旧。
- **v1.7.33 已于 2026-10-23 发布**：本版集成 #630、#632、#635、#638，并自本版起进入低频维护。完整变更与验证记录见 **[docs/CHANGELOG.md](docs/CHANGELOG.md#v173)**；下一版的改动继续写在本段。

- **v1.8.0 发布**：汇总 v1.7.33 之后的 #640、#642、#643、#645/#647，并补齐 #578、#618、#625 的发布记录。完整变更、验证范围与已知限制见 **[docs/CHANGELOG.md](docs/CHANGELOG.md#v180)**；下一版的改动继续写在本段。
- **修正 CN 专属模型判定，并给 OpenCode 写入真实上下文上限**（#618 / #625）：`minimax-` 曾被当成整个模型家族的 CN 专属前缀，于是国际版也提供的 `minimax-m3.1-flash` 被本地 400 拦下。现在只保留确定的 CN 独占项（`deepseek-v4-pro*` 与显式 `minimax-m3`），同族其他模型按出口实际目录判断。OpenCode 一键配置此前只写空的模型条目，客户端只能回落到自己的 200k 默认值；现在把网关目录中的 `context_window` / `max_output` 写进 `limit.context` / `limit.output`，没有规格的条目仍保持空对象。新增回归覆盖。 / Narrow the China-only model gate and give OpenCode the real context limit (#618 / #625): `minimax-` used to mark the whole family as CN-exclusive, so the globally served `minimax-m3.1-flash` was refused locally with a 400. Only the confirmed China-only entries remain (`deepseek-v4-pro*` and the explicit `minimax-m3`); other members of the family follow the actual catalogue of the selected exit. OpenCode's one-click config used to write empty model entries, so it fell back to its own 200k default; the gateway's catalogue `context_window` / `max_output` now go into `limit.context` / `limit.output`, while entries without specs stay empty objects. Regression coverage added.
- **流式回复在真实静默期发送 SSE 心跳**（#578）：上游思考期间可能长时间一个字节都不发，而客户端会把静默误判为断流；只在每次阻塞读之前检查心跳，恰好无法覆盖它。Chat、Responses 与 Anthropic Messages 三条流式路径现在共用后台 `SSEHeartbeat`：每 15 秒无写入就发送合法的 `: keepalive` 注释帧，与业务帧共用锁，保证不会截断 JSON；响应正常时不会多插帧，流结束后线程立即停止。新增 `tests/_test_stream_keepalive.py`（9 项，含读线程阻塞期间仍收到心跳与并发写入完整性），并复跑流式 id、usage 帧、断流错误帧与重试套件。 / Keep SSE streams alive through real upstream silence (#578): while the model is thinking the upstream may send nothing for longer than the client's idle window, and checking a heartbeat only before the next blocking read cannot cover that gap. Chat, Responses and Anthropic Messages now share a background `SSEHeartbeat`: after 15 idle seconds it writes a valid `: keepalive` comment frame under the same lock as application writes, so JSON frames cannot be split; responsive streams gain no extra frames and the thread stops as soon as the stream ends. Added `tests/_test_stream_keepalive.py` (9 checks, including heartbeat delivery while the reader is blocked and write integrity under contention), and re-ran the stream id, usage-frame, abort-frame and retry suites.

- **飞牛 fnOS 这一层：并入上游 v1.7.25–v1.7.29（Phase M）**：合并基从 `205d8b6`（v1.7.24）推进到 `af37786`（`release: v1.7.29`，该 tag 就是上游 `main` 的头部），共 **31 个提交、27 个文件、+4166/-165**，覆盖 v1.7.25 / v1.7.26 / v1.7.27 / v1.7.28 / v1.7.29 五个 release。上游这一批的主线是「面板与更新的收尾」：手机端四处布局修复（工具栏打卡按钮靠右 `#585`、用量副行每项一行与图表底边对齐 `#586`、账号卡出口与权重同行 `#587`、窄屏「积分消耗」独占一行 `#588`）；启动时补一次更新检查 `#589`（`startup=True` 绕过 24 小时窗口，仍受每小时预算 6 次约束，账本随 `update_check` 落盘）；便携更新保留 zip 里的 unix 权限位 `#582`；保留历史版本备份并支持面板「版本回退」`#571`（`updates/backup-<目标版本>/`，份数 0–3 默认 1，`request.json` 增 `action: install|rollback`，回退后校验 `Server: wb-proxy/<版本>`，失败自动恢复到回退前）；镜像/rootfs 部署的 `request.json` 带 `profile: "app"`，只替换应用层（`#573`）；账号档位改读计费摘要（`#505`，`IsPaidUser`/`SubscriptionPackageName` 落成账号上的 `tier`，失败不写结论，24 小时 TTL）；11-128 继续收口 —— assistant 历史也清洗并把散文里的 `DeepSeek Harness` 缩成 `DeepSeek`（`#574`）、DSH GUI 描述段的句尾语序（`#579`）；跨出口回退「国际版限流 → 国内版」默认关闭（`#564`）；账号表排序按「主行 + 紧跟的 `tr.cool-row` 续行」成组（`#568`）；uid 不再被手机号脱敏改写（`#581`，`179-97517476` 曾被当成号码，面板因此回 `no such account`）；API Key 的账号白名单与并发上限能落盘了（`#592`）。合并侧 4 个冲突：`README.md`（套件数按合并后的树重算为 **221 = 166 Python + 55 JS**；Unreleased 段保留本仓库六条并补上本条，已进 `docs/CHANGELOG.md` 的上游条目全部删掉、指针改为 `v1.4.5 ~ v1.7.29`）、`dashboard.html`（窄屏样式表：上游新的 `@media (max-width: 860px)` 统计条重排与本层的 `@media (max-width:640px)` 兜底按断点从宽到窄排列，两块都留）、`tests/_test_run_all_contracts.py` （取上游版 —— `sorted(..., key=int)` 比本层原来的 `sorted()` 更精确，同一个 listdir 顺序问题）、`.github/workflows/tests.yml`（上游又加回来了，按 Phase G 的「本仓库不留任何自建 CI」继续删除，只保留上游的 `release.yml`）。打包侧本轮**无需新增模块**（上游这批没有新顶层文件），`tools/`/`ops/`/`catalog/` 的排除与五个更新模块的守卫名单照旧；面板「安装更新」在飞牛上继续关闭（`install_enabled()` 的三条判据都不成立）。
- **飞牛 fnOS 这一层：并入上游 v1.7.18–v1.7.24（Phase L）**：合并基从 `af706fc`（v1.7.17）推进到 `205d8b6`（`release: v1.7.24`，该 tag 就指向上游 `main` 的头部，所以这一棵树没有「未发版提交」），共 **58 个提交、56 个文件、+6313/-489**，覆盖 v1.7.18 / v1.7.19 / v1.7.20 / v1.7.21 / v1.7.22 / v1.7.23 / v1.7.24 七个 release。上游这一批的主线从「断流」转到「可运维」：国际版每日活跃的时段（`schedule.daily_chat`，1–24 个 `HH:MM`）、并发（`daily_chat_web_concurrency`，默认 1）、线性重试（`base × N`，默认 120/240/360 秒）、当日去重、模型回退与随机提示词全部可配；API Key 可限制到账号白名单（`/u/<ref>` 定址到名单外 403）；`/v1/models` 可只列当前池子里真能服务的模型；`reasoning_effort` 被映射到模型目录声明的档位；全局提示词、出站身份版本号都能在面板里改；账号新增独立的 `tasksEnabled`（`enabled` 只管取号，签到/任务按它有选择）；流式断流不再伪造 `[DONE]`，改发标准 error 帧（`upstream_stream_error`）并关连接；热力图按本地日刷新。`v1.7.23` / `v1.7.24` 又把「一键更新」从 systemd 扩到便携版与非 systemd 部署，长出五个新顶层模块：`wb_tiers.py`（模型档位与可用性，`/v3/config` 的 `modelTiers`，PRO ONLY 模型只在池里有付费账号时出现）、`wb_webprompts.py`（内置 300 条随机提示词）、`wb_update_portable.py` 与 `wb_update_apply.py`（便携包自更新核心与包内 helper）、`wb_update_external.py`（非 systemd 部署的外部执行者参考实现），另有根目录 `start-wb-proxy-visible.bat` / `-lan-visible.bat`。`wb_proxy.py` 顶层 import 了 `wb_tiers` 与 `wb_webprompts`、`wb_update_request` 顶层 import 了 `wb_update_portable`，所以打包守卫名单与 `tests/_test_phase_e_verify.py` 的 `PKG_MODULES` 这五项全部补上（漏一个是装完启动即 ImportError）。**飞牛侧一处关键判断**：面板「安装更新」按钮的 `install_enabled()` 现在是 `_systemd_enabled() or external_enabled() or `wb_update_portable.available()``，在飞牛上三条都不成立（没有 systemd unit、没有 `WB_UPDATE_INSTALL_ENABLED=1` 与 `WB_UPDATE_EXECUTOR`、载荷里也没有便携包的 `release-manifest.json`），因此按钮保持关闭，不会去下「便携 zip」覆盖 fpk 装的只读载荷；升级飞牛包仍走应用中心或 FnDepot。新增的运行时状态都在 `accounts/`（`tasksEnabled` 写进账号 JSON），fnOS 侧不需要新目录。合并侧冲突只有 `README.md` 一个文件（套件数、Unreleased 段、指针行），`dashboard.html` / `wb_proxy.py` / `wb_accounts.py` / `release/portable.txt` / `release/portable_runtime.py` 全部自动合并。
- **飞牛 fnOS 这一层：并入上游 v1.7.14–v1.7.17（Phase K）**：合并基从 `fe30fa0`（v1.7.13）推进到 `af706fc`（`release: v1.7.17`），共 **76 个提交、59 个文件、+6758/-489**，覆盖 v1.7.14 / v1.7.15 / v1.7.16 / v1.7.17 四个 release。上游这一批把「断流」当成主线来治：`#522` 在**首字节之前**断流时同账号同出口重开一次（`emitted=False` 才重试、复用已经发出的响应头），出口维度的成功记账从「拿到响应头」挪到「流读完」（断流记 transient、重试成功不抵消、干净的流才清零）；流式 usage 改到末尾空 choices 帧、合成 chunk 用动态唯一 id，严格客户端不再因为带 choices 的 usage 帧提前结束。新增顶层模块 `wb_entitlements.py`（`11158` 「免费账号不可用」的运行时标注，状态落 `accounts/model_entitlements.json`，`wb_proxy.py` 顶层 import）与 19 个套件；另有 `11134/11102/11150/11158/11129` 这类模型级错误不再熔断整池（`#499`）、`/v1/models` 可按 Key 的模型限制过滤、一键部署区分 `WB_DEPLOY_MODE=local|lan|public`（`#512`）、OpenRouter 估价支持模型级校准系数（`#514`）、成长任务支持手动领取（`#507`）、面板改密结果以服务端为准（`#523`）、`X-Private-Data` 可配（`#516`）、DSH 一键配置改写 profile 补丁层并放宽限流重试，以及一批移动端看板布局修复。合并侧 3 个冲突：README（套件数按合并后的树重算为 **199 = 148 Python + 51 JS**；Unreleased 段保留本仓库五条并补上本条，已进 `docs/CHANGELOG.md` 的上游重复条目删掉、只留 `#523` 等三条 CHANGELOG 未收录的）、`release/portable.txt`（`wb_entitlements.py` 与我们的 `wb_export.py` 都留，按字母序）、`wb_proxy.py`（`_chat_stream_response` 里我们的 `StreamKeepalive` 与上游的出口记账块并存 —— 心跳在 `out_buf` 之上，记账按「读完」结算，两者互不覆盖）。打包侧跟上：`scripts/build-fpk.sh` 的载荷守卫名单与 `tests/_test_phase_e_verify.py` 的 `PKG_MODULES` 都补 `wb_entitlements.py`（漏它就是装完启动即 ImportError）；新增的运行时状态都落在 `accounts/`，fnOS 侧不需要新目录。
- **流式响应补空闲心跳，修「回答到一半断线」**：三个流式出口（`chat.completions` / `responses` / `messages`）此前只在上游吐字节时才写客户端，上游长思考或排队时一个字节都不写，于是任何按「多久没收到字节」判活的中间设备（nginx 的 `proxy_read_timeout` 默认 60 秒、Lucky 反代、路由器、Cloudflare 隧道）都会单方面掐掉连接 —— 客户端看到断流，服务端日志只有一次 `client_aborted`。现在写出口统一换成 `StreamKeepalive`：一把锁保证心跳线程与主线程不会把两条事件绞在一起，并在**距上次写出超过 `WB_STREAM_KEEPALIVE_SECONDS`（默认 10 秒，0 关闭，上限 300）**时补一行 SSE 注释 `: keepalive`；一直在出字的流里一次都不写，零开销。实测同一条链路（Lucky 反代 60.07 秒空闲 FIN）在补心跳后不再被判死。新增 `tests/_test_stream_keepalive.py`（16 项）。
- **发布改为「本地构建、本地上传」，GitHub 上不再有任何自动运行（Phase G）**：删掉本仓库全部自建 workflow（`sync-upstream.yml`、`build-fpk.yml`、`release-checksums.yml`、`docker-publish.yml`、`tests.yml`），只保留上游的 `.github/workflows/release.yml`（它只在 `v*` tag 上触发，我们的发布 tag 是 `fnos-X.Y.Z`，所以永不运行；删它反而会让下次并入上游再冲突）。新增 `scripts/gh-release.py`（纯标准库，走 REST API 打 tag / 传 Release 资产 / 改发布正文 / 算 sha256；token 从 `$WB_GH_TOKEN` 或 `/root/.gh-token` 读，绝不进仓库）与一页可照抄的 runbook [`docs/phase-g-local-release.md`](docs/phase-g-local-release.md)。同时清理本地构建缓存（`build/`、所有 `__pycache__/`、`*.pyc`/`*.pyo`、`.pytest_cache/`、`suite-logs/`，工作区 24M → 21M）并在 `.gitignore` 补上 `.pytest_cache/`。版本号规则不变：包版本 = 上游最新 release tag 的三段号，发布 tag = `fnos-X.Y.Z`。
- **飞牛 fnOS 这一层：并入上游 v1.6.18–v1.6.19 及 v1.6.19 之后的 34 个提交、版本号与上游对齐、发布 tag 改 `fnos-X.Y.Z`**（本仓库改动，上游没有对应 tag）：包版本就是上游最新 release tag 的三段号（`v1.6.19` → `1.6.19`），本仓库发布 tag 从 `v<版本>.<序号>` 改为 `fnos-X.Y.Z`——上游新增的 `.github/workflows/release.yml` 以 `push: tags: ["v*"]` 触发并创建 Draft Release，继续用 `v*` 会双触发。`sync-upstream.yml` 因此不再把上游 tag 镜像进本仓库，并把 cron 加到三条（`17 3` / `23 9` / `41 15`，GitHub 的 schedule 常年晚约 7 小时），冲突时除失败 + summary 外再推一个 `sync-conflict/<UTC 日期>` 分支（带冲突标记，省得人重做合并）。飞牛层重贴后还修掉两处真缺陷：上游给 `Handler` 新加的 `disable_nagle_algorithm` 在 AF_UNIX 上会抛 `Errno 95`，网关路径单独派生了一个关掉它的 handler（否则每个网关请求都在 `setup()` 死掉）；看板直连 `GET /` 的响应体要求与文件逐字节一致，因此缺省直连不再注入 `window.__WB_BASE__`/`__WB_VIA_GATEWAY__`（挂载态照旧注入，且 ETag 增加了一个覆盖网关上下文的校验分量，否则第二个 NAS 用户会拿到 304 + 别人的页面）。看板另修掉一个同名函数覆盖（上游新的 `fmtTok` 会静默盖掉我们的精确版，全站 token 显示退化成 `8.3K`）。上架飞牛第三方源（FnDepot）的材料见 `fnpack.json`。
- **飞牛 fnOS 这一层：并入上游 v1.7.4–v1.7.10（58 个提交）并合上三个打包缺口（Phase I）**：包版本推进到 `1.7.10`，发布 tag 仍按 `fnos-X.Y.Z` 走（本轮 `fnos-1.7.10`）。上游这一批新增了可选 SQLite 日志落库模块 `wb_logstore.py`（`wb_proxy.py` 已 `import wb_logstore`）与运行时转储目录 `catalog/`，而我们的打包侧此前都不知道它们：`scripts/build-fpk.sh` 的载荷守卫名单补上 `wb_logstore.py`（漏掉就等于把「启动即 ImportError」的失败模式放空），tar 排除列表补 `./catalog`（`catalog/README.txt` 明说这是运行时转储、删除永远安全，但打包是从工作树 tar，构建机上残留的 `product-config-<realm>.json` 会被打进包）；设备侧给 `fnos/cmd/main` 的启动命令加 `WB_PROXY_CATALOG_DIR="${PKGVAR}/catalog"`，否则默认落在只读的 payload 目录、上游 v1.7.5 起的「原始目录存档」在 NAS 上静默失效。日志库落在 `${PKGVAR}/usage/logs.sqlite3`，现有 launcher 已 `mkdir -p` 且 `chmod 700`，无需改动。
- **飞牛 fnOS 这一层：并入上游 v1.7.11–v1.7.13 及 v1.7.13 之后的 44 个提交（Phase J）**：合并基从 `7e5c38d`（v1.7.10）推进到 `fe30fa0`，共 63 个提交、69 个文件、+9626/-492；包版本按版本号规则取上游最新 release tag 的三段号 → `1.7.13`，发布 tag `fnos-1.7.13`（该 tag 指向的合并提交因此包含 v1.7.13 之后仍未发版的那 20 个上游提交，与上游 `main` 对齐）。上游这一批长出四个新顶层文件与一个运维目录：`wb_quota_scan.py`（模型额度定时主动查询，状态落 `accounts/quota_scan.json`）、`wb_window_probe.py`（配额窗口探针，状态落 `accounts/model_windows.json`）、`wb_update_request.py`（阿里云 systemd 更新服务的面板侧请求桥，`wb_proxy.py` 顶层 `import`，缺它网关启动即 ImportError）、`console_tail.py`（便携包日志窗口）；`ops/aliyun/` 是 root 级 updater 单元，根目录维护脚本按上游 #398 归档进 `tools/`。打包侧随之跟上：`scripts/build-fpk.sh` 的载荷守卫名单补 `wb_quota_scan.py` / `wb_window_probe.py` / `wb_update_request.py`（漏一个就是「装完启动即死」），tar 排除列表把已失效的单文件 `./_fixbats.py` 换成整目录 `./tools` + `./ops`（上游把脚本搬进 `tools/` 后旧规则不再命中，且新目录不该进包），`tests/_test_phase_e_verify.py` 的 `PKG_MODULES` 同步这三项；面板侧 `postJSON` 同时保留上游的「服务已关闭直接报错」与飞牛的 `wbUrl()` 网关前缀，`release/portable_runtime.py` 的必需文件表取并集（上游新增 `Lib/stat.py`、`Lib/platform.py`，飞牛仍要 `Lib/socketserver.py`、`Lib/struct.py`）。新增运行时状态全部落在 `accounts/`（本来就 `mkdir -p` + `chmod 700`），fnOS 侧不需要新目录，`WB_PROXY_CATALOG_DIR` 的修复照旧生效。 已发布版本的完整记录（v1.4.5 ~ v1.7.30，含每版的 PR 归属）见 **[docs/CHANGELOG.md](docs/CHANGELOG.md)**。
- **飞牛 fnOS 这一层：并入上游 v1.7.30（Phase N）**：合并基从 `af37786`（v1.7.29）推进到 `84dbc99`（`release: v1.7.30`，该 tag 就是上游 `main` 的头部），共 **34 个提交、32 个文件、+4954/-427**。上游这一批 15 笔社区改动的主线是「判定与面板」：调度器日志与区域风控闸门改取正在运行的 `wb_proxy`（#594，`python wb_proxy.py` 下 `import wb_proxy` 会再加载一份副本，副本的 `LOG_STORE` 是 None、暂停状态也是另一份）；签到不再把 `200 + code 10001` 的失败回执记成成功（#596）；一键签到按 `tasksEnabled` 选号（#598）；Token 保活提前量改成 48 小时（#600，旧值 2 小时远小于 24 小时巡检间隔）；下拉框自绘（#601）；每日活跃建会话失败后按 `phase` 补退避（#605）；面板闸门 fail-closed 修首帧闪烁与 `?pwd=` 卡死（#606）；一次流式回复只带一个 chunk id（#607）；面板 POST 的空 body 会被排空（#608，修同连接下一个请求 501）；**Pro Only 标注改由目录 `modelTiers` 驱动（#609）——上游因此删掉了 `wb_entitlements.py` 与其套件**；Codex 远程压缩 v2（#610）；账号级并发上限与会话粘滞键（#612，默认关）；静态 API Key 账号（#620）；账号行显示会员档位胶囊（#621）；每日活跃网页会话跑完即释放（#623，修 10105）。合并侧 4 个冲突：`README.md`、`dashboard.html`（上游的「先摘 `html.wb-panel-session`」与飞牛的「网关模式摘掉闸门并提示重开」两段都留：先摘类，再按网关模式提前返回）、`release/portable.txt` 与 `wb_proxy.py`（`wb_entitlements.py` 已被上游删除，这里跟着删掉 import 与清单项，只保留本层的 `wb_export.py`）。打包侧同步：`scripts/build-fpk.sh` 守卫名单与 `tests/_test_phase_e_verify.py` 的 `PKG_MODULES` 去掉 `wb_entitlements.py`。

已发布版本的完整记录（v1.4.5 ~ v1.8.0，含每版的 PR 归属）见 **[docs/CHANGELOG.md](docs/CHANGELOG.md)**。


## 七、致谢与引用声明 (Credits & References)

协议兼容、风控规避与任务链路设计过程中，参考并吸纳了以下开源项目的经验与逆向成果：

- **[Sliverkiss/workbuddy2api](https://github.com/Sliverkiss/workbuddy2api)**：成长任务全链路逆向、设备指纹稳定派生（`derive_id`）、整点排程调度（`Scheduler`）、指纹脱敏与 `reasoning_content` 回填；
- **[CangShui/workbuddy-cliproxy-fix](https://github.com/CangShui/workbuddy-cliproxy-fix)**：早期客户端代理修复与接口差异参考；
- **[lovingfish/workbuddy-cliproxy](https://github.com/lovingfish/workbuddy-cliproxy)** 与 **[mmqz/cpa-multi-plugins](https://github.com/mmqz/cpa-multi-plugins)**：网关通信与多插件管理原型参考；
- **[ardeyouxipianyi/workbuddy2api](https://github.com/ardeyouxipianyi/workbuddy2api)**：国内版分发包逆向分析与出站 User-Agent 规范参考；
- **[linguo2625469/workbuddy2api-panel](https://github.com/linguo2625469/workbuddy2api-panel)**：国内版连登管家（补签保连登、7d/14d/28d 档位兑换、抽奖闭环）、对话活跃上报的事件形状与「必须带 `userId`、每号每天一次」的风控口径、企业版门控（企业号无个人成长体系），以及新手礼包 / 活动补偿接口；
- **[aodianjun/workbuddy2api-hub](https://github.com/aodianjun/workbuddy2api-hub)**：OpenWrt 打包配方（`.ipk` / `.apk` 构建脚本、包 Makefile、init.d 与 uci 配置、面板缓存预热器），审计后并入 `wrt/`。

PR 贡献者（v1.4.5 之前的改动未进上方更新记录，这里一并列出）：

- **[@ddddd-ren](https://github.com/ddddd-ren)**：用量日志倒序检索与看板防堆叠（PR #14）、原子写入与并发竞争修复（PR #13）、账号池 JSON 导出导入（PR #5）；
- **[@wylftw0314-glitch](https://github.com/wylftw0314-glitch)**：Responses API custom 工具协议双向转译（PR #12）；
- **[@shuishuipingan](https://github.com/shuishuipingan)**：成长任务领取竞态与专家/团队事件 id 去重、猫猫旅行派出修复、夜猫子任务接入调度器、启动端口误判（PR #21）、按模型冷却限流（PR #22）、任务接取强化与轮询加速（PR #27）、网络抖动重试与 403 直通（PR #28）、HTTP 连接同步（PR #30）；
- **[@ayeaaaa](https://github.com/ayeaaaa)**：按账号绑定出口代理槽（PR #26）、DeepSeek `reasoning_content` 回填（PR #36）、看板移动端布局（PR #37）；
- **[@t-789](https://github.com/t-789)**：macOS 启动脚本与防火墙助手（PR #31）；
- **[@Cekxri](https://github.com/Cekxri)**：Codex App namespace 工具支持（PR #33）；
- **[@wiggins-kong](https://github.com/wiggins-kong)**：API Key 行 id 唯一化（PR #40）、Docker 镜像缺少运行时模块（PR #41）；
- **[@Pro-XK](https://github.com/Pro-XK)**：看板积分消耗与账号昵称（PR #45）；
- **[@teddyli18000](https://github.com/teddyli18000)**：单模型限流可视化（PR #50）、`/health` 鉴权状态修正（PR #52）；
- **[@LuFering](https://github.com/LuFering)**：Docker 部署下的 Linux 桌面凭据挂载说明（PR #55）；
- **[@zhangzm0](https://github.com/zhangzm0)**：`tool_choice="none"` 保留工具声明（PR #57）。

---

## 八、免责声明 (Disclaimer)

1. 本项目为非官方自托管网关，仅供技术研究、逆向协议学习与个人合法授权账号在私有环境测试使用。
2. 本项目不提供任何账号及额度。请严格遵守官方服务条款，禁止用于任何商业转售、恶意并发或违规滥用。
