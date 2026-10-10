# 飞牛 OS（fnOS）应用包

`fnos/` 是这个网关的飞牛应用描述，`scripts/build-fpk.sh` 把它和服务器源码打成一个
`.fpk` 安装包。原生 Python 应用，**不用 Docker**：跑在飞牛自带的 `python3` 上，
缺了就用应用商店里的 `python312`（`/var/apps/python312/target/bin`）。

## 目录

| 路径 | 作用 |
| --- | --- |
| `manifest` | 应用元信息：`appname = workbuddy2api`、显示名 `WorkBuddy2API-Hub`、`service_port = 8788`、`platform = all`、`source = thirdparty`。`version`/`distributor`/`distributor_url`/`checksum` 由构建脚本填。 |
| `cmd/main` | 唯一的生命周期入口：`start` / `stop` / `status` / `restart` / `log [行数]` / `python-check` / `install` / `uninstall-clean` / `purge <目录>`。 |
| `cmd/*_init`、`cmd/*_callback` | 应用中心在安装、升级、卸载、改配置前后调用，全部转发给 `cmd/main`。 |
| `config/privilege` | 以 `package` 身份运行，用户名与组名都是 `workbuddy2api`（不用 root）。 |
| `config/resource` | 只登记端口：`WorkBuddy2API.sc` 把 `8788/tcp` 映射出去，没有数据共享目录。 |
| `WorkBuddy2API.sc` | 端口转发声明（`src.ports = 8788/tcp`）。 |
| `ui/config` | 应用中心入口：`workbuddy2api.Application` → `type: iframe`，`gatewaySocket: app.sock`、`gatewayPrefix: /app/workbuddy2api`、`url: /app/workbuddy2api/`（原理见「免密码入口」）。**必须放在载荷里**（`app.tgz` 内），包根再放一份只是沿用惯例：应用中心登记「打开」入口时读的是载荷里的那一份。 |
| `ui/images/{64,256}.png` | 构建时由 `ICON.PNG` / `ICON_256.PNG` 生成，仓库里只存这两份位图（载荷与包根各放一份，与 `ui/config` 里的 `images/{0}.png` 对应）。 |
| `wizard/uninstall` | 卸载时问一句「保留还是删除账号、用量、看板密码」。 |

### 命名：产品名与 `appname`

| 用途 | 值 |
| --- | --- |
| 产品名 —— `manifest` 的 `display_name`、`ui/config` 的 `title`、Release 标题、fpk 文件名、CI artifact 名 | **WorkBuddy2API-Hub** |
| 标识符 —— `manifest` 的 `appname`、`WorkBuddy2API.sc` 的文件名及其段落名、`TRIM_APPNAME`、包内 `workbuddy2api.Application` | `workbuddy2api`（**不要动**） |

安装目录（`/vol1/@appcenter/workbuddy2api/`）、数据目录（`/vol1/@appdata/workbuddy2api/`）、
网关前缀（`/app/workbuddy2api`）与 `.sc` 的端口声明都挂在标识符上：改它等于让应用另起一套目录，
老用户升级后账号、用量与看板密码会留在旧目录里，入口地址也会跟着变。所以改名只改产品名，
`scripts/build-fpk.sh` 在打包前会断言这两者分别是 `WorkBuddy2API-Hub` 与 `workbuddy2api`。

## 装好之后

- **应用中心入口**（推荐）：桌面/应用中心里点「打开」，看板在飞牛里内嵌打开，已经登录飞牛的
  用户**不用再输看板密码**（原理见下面「免密码入口」）。
- **直连看板**：`http://<NAS>:8788/`，这条路径要输看板密码，默认 `admin`，
  首次登录后请在「设置」里改掉。
- **数据目录**：`/var/apps/workbuddy2api/var/`
  - `accounts/`：账号凭证与 `settings.json`（API Key、看板密码）；
  - `usage/`：请求流水；
  - `workbuddy2api.log`：服务日志（超过 5 MB 自动轮转一次）；
  - `workbuddy2api.pid`：PID 文件。
- **程序目录**：`/var/apps/workbuddy2api/target/server/`（升级时整体替换，**不要**在这里放东西）。
- **地址不知道去哪找**：看板「设置」页顶部有「使用说明」，列出 API 地址、直连地址与应用中心入口，
  每行都能一键复制；端口取自服务端（`/panel/status` 的 `direct_port`），换端口不用改页面。
- **导入账号**：看板「导入账号」选一个 JSON 文件即可，支持本网关导出的文件、账号数组、
  单个账号对象、cockpit tools 导出的 snake_case 写法（`access_token` / `expires_at`）、
  以及桌面客户端的 `{"account":…,"auth":…}`。详见仓库 README。
- **防火墙**：`WorkBuddy2API.sc` 声明了 `8788/tcp`；如果路由器/交换机另有一层防火墙，
  记得放行。

## 打包

```bash
bash scripts/build-fpk.sh          # 产出 dist/WorkBuddy2API-Hub_<版本>_<platform>.fpk + .sha256
bash scripts/verify-fpk.sh         # 在本机把整条生命周期跑一遍
```

- **版本号**：就是**上游自己的三段版本号**，例如 `1.6.19`；发布 tag 是 `fnos-1.6.19`，
  包名、`manifest`、Release 标题（`WorkBuddy2API-Hub 1.6.19`）都用这个数字，**没有再补第四段**。
  `bash scripts/build-fpk.sh --print-version` 只算不构建。没打 `fnos-*` tag 时构建出来的是过程包
  （`1.6.19-alpha3` 这种带后缀、装不上也不该装的东西），规则见下面「版本号和 tag」。
- **distributor**：默认取 `origin` 的 owner 与 URL，也就是你的 fork；`origin` 还指向上游时
  脚本会直接报错（否则应用商店里会把包记成上游作者），可以显式传
  `PACKAGER=<你的用户名> PACKAGER_URL=<你的 fork>`。
- **载荷**：`app.tgz` 里只有服务器源码（`server/`，含上游的 `pricing/pricing.json`）、
  `dashboard.html` 与 `LICENSE`；测试、源码 `docs/`、启动脚本、`Dockerfile`、`accounts/`、
  `usage/` 一律不进包——构建脚本发现 `accounts/` 或 `usage/` 会直接失败。
- **校验**：打包前用 `ast.parse` 检查载荷里每个 `.py`，并逐个确认运行时模块与
  `server/pricing/pricing.json` 都在；打包后校验必需文件、端口三处一致
  （`manifest` ↔ `ui/config` ↔ `.sc`）、显示名/标识符，以及 `manifest` 里声明的 `checksum`
  （`app.tgz` 的 md5）。

`scripts/verify-fpk.sh` 会像应用中心那样解包，导出 `TRIM_*` 环境变量，然后走完
安装 → 启动 → 用面板登录并导入一份 cockpit tools 格式的账号文件 → 升级（确认账号还在）
→ 停止 → 卸载（两种选择都试一遍），共 71 项断言（含网关入口：socket 权限、带与不带
`X-Trim-Username` 两种免密识别、前缀剥离、停止后 socket 文件被清掉；以及包身份：产品名、
`appname`、版本在文件名/`manifest`/`ui/config` 三处一致、**版本必须是上游的三段数字（不能是
四段、也不能是 `-alpha` 过程版本）**，运行时模块与 `pricing/` 齐全，
`accounts/`、`usage/`、`tests/`、`docs/` 四个目录都没进包，包内每个文件逐字节等于仓库里那份）。其中「包就是这棵树构建的版本」这一条只在 HEAD 上有 `fnos-<版本>` tag 时断言——本地没打 tag 时树给的是过程版本，无从比较，它会打一行 `SKIP` 说明而不是假装通过。它跑的是真进程、真 HTTP，**但装不了真机**：
应用中心本身（`trim-cli`）只存在于飞牛系统里，所以最后一公里还是要在一台真 NAS 上试。

### 两种 `TRIM_APPDEST` 形状

应用中心交给生命周期脚本的 `TRIM_APPDEST` 是**载荷目录**，在真机上是
`<卷>/@appcenter/<appname>`（例：`/vol1/@appcenter/workbuddy2api`），**没有** `/target` 后缀；
只有 `/var/apps/<appname>/target` 这个软链接才有后缀。写成 `${TRIM_APPDEST%/target}` 再退一级的
脚本会在真机上算出 `<卷>/@appcenter`，于是找不到自己的 `cmd/main`。`scripts/verify-fpk.sh` 里
「the layout appcenter really uses」这一段就是照着真机形状跑的回归测试（见下）。

生命周期脚本找自己的候选顺序是 `WB_APPDIR` → `TRIM_APPDEST` → `TRIM_APPDEST` 去掉 `/target`
→ `/var/apps/<appname>`。最后那个是**绝对路径**，所以真机上的定位实际靠它，而沙箱里没法拥有
`/var/apps/workbuddy2api`：不设 `WB_APPDIR` 时，那个回归测试会去跑**已安装的那份**（装过就过、
没装就挂），根本没有测到沙箱里这份代码。`WB_APPDIR` 只有 `scripts/verify-fpk.sh` 会设置，
应用中心永远不设它，真机行为不变。

### 免密码入口（应用中心里的 iframe）

应用中心入口不再是一个指向 `8788` 的新标签页，而是交给飞牛自己的网关：

```json
"workbuddy2api.Application": {
    "type": "iframe",
    "gatewaySocket": "app.sock",            // 载荷目录里的 unix socket
    "gatewayPrefix": "/app/workbuddy2api",
    "url": "/app/workbuddy2api/",
    "allUsers": true
}
```

`cmd/main start` 带上 `--unix-socket <载荷>/app.sock --base-path /app/workbuddy2api` 启动，
服务器把 socket 建成 `0666`（连接它的网关进程不一定以本应用的用户身份运行）。请求由
`/usr/trim/bin/trim_http_cgi` 转发进来，并带上 `X-Trim-Username`、`X-Trim-Userid`、
`X-Trim-Isadmin` —— 这是飞牛那边的实现，`strings /usr/trim/bin/trim_http_cgi` 里能读到
`X-Trim-Username` 以及 `gatewaySocket` / `gatewayPrefix` 的字段名。

头可以伪造，所以**只有 socket 对端是 root（uid 0，即网关自己）或本应用自己的 uid 时**才认它，
其它进程一律当匿名请求；TCP 端口上永远不认这个头。在这个前提下，**socket 上的对端校验通过就
算已登录**，头只负责给出显示用的用户名——已经登录飞牛的人不会因为会话头没跟上来又被弹回
口令框。真机上（root 模拟网关）：

```
root  + X-Trim-Username: deepseek.harness -> {"via_gateway": true, "gateway_user": "deepseek.harness", "authenticated": true}
root  不带头                              -> {"via_gateway": true, "gateway_user": "", "authenticated": true}
uid 951 + 伪造同一个头                     -> {"via_gateway": true, "gateway_user": "", "authenticated": false}
```

看板里的表现：网关进来的用户直接进主界面，右上角提示「已通过飞牛OS 统一登录进入」，
用户名来自 `X-Trim-Username`（没带就只显示入口提示）；直连 `8788` 的用户看到的是
「请从飞牛OS 应用中心打开」和一个折叠的密码登录。
`/v1` API 端口的行为没变，仍然只认 API Key。

`allUsers: true` = 所有登录飞牛的用户都能看到这个入口（与改之前的 url 入口一致）；
想收紧就改成 `false`（`false` 的确切语义没有在本机对照过，agent2api 用的是 `false`）。

### 真机验证记录（fnOS 1.2.0800）

已在一台飞牛 NAS 上真装真跑通过：

- **安装**：应用中心「手动安装」，或 `trim-cli app install-fpk <file.fpk> --yes`；
- **启动**：`GET /health` 返回 `{"ok": true, "realm": "intl", ...}`，日志写在
  `/vol1/@appdata/workbuddy2api/workbuddy2api.log`（`trim-cli app start|stop|restart` 也可用）；
- **账号导入**：`POST /panel/login`（默认密码 `admin`）拿到看板令牌，再 `POST /accounts/import`
  直接吃 cockpit tools 那种 snake_case 数组，凭证落到 `@appdata/workbuddy2api/accounts/`；
- **应用中心入口**：`ui/config` 进载荷之后，应用记录里出现 `appServiceInfo`
  （`control.isOpen = true`、`openType = url`、端口 `8788`），桌面与应用中心都能点开看板。
  图标按 `ui/images/{0}.png` 解析，所以载荷里必须有 `ui/images/{64,256}.png`。

- **网关入口**（2026-10-05，用一个改名/换端口的同源包 `wbgateway` 1.6.10 实测，
  不动已经在用的那个应用）：装完后应用列表里 `appServiceInfo.type` 是 `iframe`、
  `urls.path = /app/wbgateway/`（对照：老入口是 `type: url`、`urls.port = 8788`）；
  载荷里的 `app.sock` 是 `srw-rw-rw-`，用 root 带 `X-Trim-Username` 连上去
  `via_gateway` / `gateway_user` / `authenticated` 三项都成立，换个 uid 伪造同样的头被忽略；
  socket 上带 `/app/wbgateway` 前缀的请求会被剥掉前缀，看板里注入的是
  `<base href="/app/wbgateway/">` 与 `window.__WB_BASE__="/app/wbgateway"`。
  浏览器里 `/app/<appname>/…` 先由飞牛校验会话（没有会话时 nginx 直接回 `invalid token`），
  所以「带着飞牛会话在应用中心里点开」这一段只能靠一次真的登录去点，CLI 模拟不了。

- **当前状态（2026-10-09）**：设备上装的仍是旧包 `1.6.10.11`；`1.6.17.1`（上游 v1.6.17 加这一层
  网关与打包改动）只在本机构建并跑完 `scripts/verify-fpk.sh` 的沙箱演练，**没有**装到设备上。

只有真机才知道的两件事，已经写进脚本与回归测试：

1. `TRIM_APPDEST` 的形状（见上一节）；
2. 同一个 `appname` 已经装过时，`trim-cli app install-fpk` 会以 **10236（已安装）** 拒绝；
   而本包带卸载向导（`wizard/uninstall`），`trim-cli app uninstall --yes` 会以
   「app-center uninstall requires custom wizard parameters; run it from App Center UI」被拒
   （2026-10-05 复测；向导自己的默认选项是 `wizard_delete_data=false`，也就是保留）。
   改用 CLI 卸载也行，但要先把已安装目录里的 `wizard/uninstall` 临时挪走
   （`cp -a /var/apps/<appname>/wizard/uninstall /tmp/ && rm /var/apps/<appname>/wizard/uninstall`）：
   2026-10-05 对一个测试包这么卸过，`trim-cli app uninstall <appname> --yes` 成功，
   而且数据目录**原样保留**（去掉向导就没得选「删除数据」，所以走的是保留那条路）。
   **升级的做法**：在应用中心里先卸载（向导里选「保留现有文件」），再安装新的 `.fpk` ——
   账号、用量与看板密码都在 `/vol1/@appdata/workbuddy2api` 里原样保留。
   但不要默认「一定保留」：2026-10-05 11:21 的一次卸载（不是 CLI，CLI 会被拒）之后
   `accounts/`、`settings.json`、`usage/` 全没了，而 journal 只留下 `APP_UNINSTALLED`、
   没记当时向导选了什么。升级前先备份：
   `tar czf ~/workbuddy2api-backup.tgz -C /vol1/@appdata workbuddy2api/accounts workbuddy2api/settings.json`
   （账号文件里是凭证，备份文件自己收好）。

## CI

- `.github/workflows/build-fpk.yml`：推送 `fnos-*`（本仓库的发布 tag）或历史 `v*` tag 时构建
  fpk、跑一遍 `scripts/verify-fpk.sh`，然后把 `.fpk` 和 `.sha256` 挂到同名 Release 上
  （Release 标题是产品名 `WorkBuddy2API-Hub <tag>`，手动触发时改为上传 artifact
  `workbuddy2api-hub-fpk`）。构建前它会把 tag 上的版本和 `--print-version` 对一遍，不一致
  直接失败——「tag 说要发 1.6.19，树算出来是别的」这种包不会再被发出去。
- `.github/workflows/sync-upstream.yml`：每天尝试三次（03:17 / 09:23 / 15:41 UTC，即北京时间
  11:17 / 17:23 / 23:41；GitHub 的定时任务常年晚点甚至整个丢失，冗余几次才靠得住）拉上游
  `ardeyouxipianyi/workbuddy2api-hub` 的 `main`，能快进/自动合并就合并并推送，然后**只有上游最新
  release 版本比我们已发布的更大**才打 `fnos-<版本>` tag 并构建发布（同一个版本不会发两次）。
  **上游的 tag 绝不推到本仓库**（理由见「版本号和 tag」）。**合并冲突则中止**：把带冲突标记的
  合并推成一个 `sync-conflict/<UTC 日期>` 分支（`git checkout` 它就能接着解）、把冲突文件和解
  决命令写进本次运行的 summary、尽力开/更新一个 issue，并让这次运行失败——不会留下半个合并的
  仓库，也不会有一次「静悄悄的红」。

### 版本号和 tag

**版本号就是上游自己的版本号**：上游 release 是 `v1.6.19`，我们的包就是 `1.6.19`，我们的 tag
是 `fnos-1.6.19`。没有第四段，也没有自己的发布计数器。

```
上游 tag:    v1.6.19
我们的 tag:  fnos-1.6.19     <- manifest / Release 名 / fpk 文件名 都是 1.6.19
```

为什么不自己编版本号（Phase F 之前是 `1.6.17.1` 这种「上游三段 + 本基线上的第几次发布」）：

- 版本号是对用户和应用商店的承诺，`1.6.19` 能直接和上游 release 对上；`1.6.19.7` 这种数字没人
  读得出含义，飞牛比较版本号的规则也没有正式文档。我们为这套自编号码付过代价：tag `v1.6.17.1`
  在 CI 里构建出了 **1.6.10.3**，比设备上装的还小，根本升不上去。
- 旧方案依赖「这次 checkout 能看到哪个上游 tag」，而 CI 全新 clone 只看得到本仓库自己的 tag。
  现在版本只取决于 HEAD 上有没有 `fnos-*` tag，与能看到哪些远端 tag 无关。

**为什么不再用 `v*`**：上游新增了自己的发布工作流，它在 push 到 `v*` tag 时会创建 draft
release。我们继续用 `v1.6.19` 这样的 tag，就会连带触发上游的发布流程；而且两边同名的 tag 在
`git fetch upstream` 之后会互相覆盖（不覆盖也会打架）。所以本仓库的发布 tag 一律加 `fnos-`
前缀，和上游的 `vX.Y.Z` / `vX.Y.Z.N` 彻底错开。历史 tag（`v1.6.10.1`、`v1.6.17.1` 这些）保留
不动——删了旧 Release 就没了标签——但它们现在只是一段历史，不再被当成发布。

**没打 tag 的时候**（本地开发、手动 dispatch、`--alpha`）构建出来的是**过程版本**，带
`-alpha<k>` 后缀，k = 距最近一次发布过了多少个提交。过程版本不该装上设备：

```bash
bash scripts/build-fpk.sh                     # HEAD 上有 fnos-1.6.19 时 -> 1.6.19
bash scripts/build-fpk.sh --alpha             # 1.6.19-alpha3   设备上试用的中间包
bash scripts/build-fpk.sh --print-version     # 只看版本，不构建（可加 --alpha）
VERSION=1.6.19 bash scripts/build-fpk.sh      # 显式指定版本（手工发版用）
```

既没有 tag 也没给 `VERSION=` 时，兜底顺序是：最近一个 `fnos-*` tag 的版本 → 上游 remote 上最新
的 `vX.Y.Z`（`git ls-remote --tags upstream`）→ `fnos/manifest` 里的占位版本。这条链只用来给
**过程包**起个名字，发布包永远来自 tag 或显式 `VERSION=`（`verify-fpk.sh` 会拒绝四段版本和
`-alpha` 版本进包）。

**发版**：自动路径是 `sync-upstream.yml` 合并上游后判断「上游最新 release 是否比我们已发布的
更新」，是就打 `fnos-<上游版本>` tag，再显式 `uses: build-fpk.yml` 构建（不靠 tag push 事件：
用 `GITHUB_TOKEN` 推的 tag 不会触发别的 workflow）。手工路径就是自己打这个 tag：
`git tag -a fnos-1.6.19 -m "WorkBuddy2API-Hub 1.6.19 (upstream v1.6.19)" && git push origin fnos-1.6.19`
——tag 上的数字决定了包版本，`build-fpk.yml` 会核对它。

**设备升级**：设备上装的是 `1.6.17.1`（旧的四段版本），新包 `1.6.19` 数字更大，应用中心会提示
升级；在应用中心卸载旧包（向导里选保留数据）再装新包即可，数据目录
`/vol1/@appdata/workbuddy2api` 不受影响。规则原文与这次改动的来龙去脉见
[`docs/phase-f-version-policy.md`](../docs/phase-f-version-policy.md)。

> 两个 workflow 都要写仓库（推分支、推 tag、发 Release、开 issue），所以 fork 里需要
> Settings → Actions → General → Workflow permissions 选 **Read and write**，
> Workflow 才能拿到可写的 `GITHUB_TOKEN`。默认的只读会让「发 Release」和「推同步结果」
> 两步报 `Resource not accessible by integration`。
>
> 用 `GITHUB_TOKEN` 推的 tag 不会再触发别的 workflow（GitHub 的防递归规则），所以
> `sync-upstream.yml` 是显式 `uses: build-fpk.yml` 去构建的，而不是靠 tag push 事件。

> 如果你不打算在 fork 里发 Docker 镜像，可以把继承来的
> `.github/workflows/docker-publish.yml` 关掉（Actions 页面里 Disable workflow）。

## 约定出处

`fpk` 的目录形状、`manifest` 字段、`TRIM_*` 环境变量与生命周期钩子的语义，来自飞牛第三方
应用生态里公开的包（`conversun/fnos-apps`、`Jacob9102/fnos-file-tool`、FnDepot 上的成品包）；
脚本本身是按这些约定自己写的——`conversun/fnos-apps` 是 GPL-3.0，本仓库是 MIT，不能抄它的脚本。
