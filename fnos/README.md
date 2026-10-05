# 飞牛 OS（fnOS）应用包

`fnos/` 是这个网关的飞牛应用描述，`scripts/build-fpk.sh` 把它和服务器源码打成一个
`.fpk` 安装包。原生 Python 应用，**不用 Docker**：跑在飞牛自带的 `python3` 上，
缺了就用应用商店里的 `python312`（`/var/apps/python312/target/bin`）。

## 目录

| 路径 | 作用 |
| --- | --- |
| `manifest` | 应用元信息：`appname = workbuddy2api`、显示名 `WorkBuddy2API`、`service_port = 8788`、`platform = all`、`source = thirdparty`。`version`/`distributor`/`distributor_url`/`checksum` 由构建脚本填。 |
| `cmd/main` | 唯一的生命周期入口：`start` / `stop` / `status` / `restart` / `log [行数]` / `python-check` / `install` / `uninstall-clean` / `purge <目录>`。 |
| `cmd/*_init`、`cmd/*_callback` | 应用中心在安装、升级、卸载、改配置前后调用，全部转发给 `cmd/main`。 |
| `config/privilege` | 以 `package` 身份运行，用户名与组名都是 `workbuddy2api`（不用 root）。 |
| `config/resource` | 只登记端口：`WorkBuddy2API.sc` 把 `8788/tcp` 映射出去，没有数据共享目录。 |
| `WorkBuddy2API.sc` | 端口转发声明（`src.ports = 8788/tcp`）。 |
| `ui/config` | 桌面图标：`workbuddy2api.Application` → `http://<NAS>:8788/`。**必须放在载荷里**（`app.tgz` 内），包根再放一份只是沿用惯例：应用中心登记「打开」入口时读的是载荷里的那一份。 |
| `ui/images/{64,256}.png` | 构建时由 `ICON.PNG` / `ICON_256.PNG` 生成，仓库里只存这两份位图（载荷与包根各放一份，与 `ui/config` 里的 `images/{0}.png` 对应）。 |
| `wizard/uninstall` | 卸载时问一句「保留还是删除账号、用量、看板密码」。 |

## 装好之后

- **看板**：`http://<NAS>:8788/`（桌面图标或应用中心都能打开）。看板密码默认 `admin`，
  首次登录后请在「设置」里改掉。
- **数据目录**：`/var/apps/workbuddy2api/var/`
  - `accounts/`：账号凭证与 `settings.json`（API Key、看板密码）；
  - `usage/`：请求流水；
  - `workbuddy2api.log`：服务日志（超过 5 MB 自动轮转一次）；
  - `workbuddy2api.pid`：PID 文件。
- **程序目录**：`/var/apps/workbuddy2api/target/server/`（升级时整体替换，**不要**在这里放东西）。
- **导入账号**：看板「导入账号」选一个 JSON 文件即可，支持本网关导出的文件、账号数组、
  单个账号对象、cockpit tools 导出的 snake_case 写法（`access_token` / `expires_at`）、
  以及桌面客户端的 `{"account":…,"auth":…}`。详见仓库 README。
- **防火墙**：`WorkBuddy2API.sc` 声明了 `8788/tcp`；如果路由器/交换机另有一层防火墙，
  记得放行。

## 打包

```bash
bash scripts/build-fpk.sh          # 产出 dist/workbuddy2api_<版本>_<platform>.fpk
bash scripts/verify-fpk.sh         # 在本机把整条生命周期跑一遍
```

- **版本号**：默认取 `git describe --tags` 的 tag，再加上「这个 tag 之后有多少个提交」作为
  第四段：tag 上就是 `1.6.10`，tag 之后 3 个提交就是 `1.6.10.3`。飞牛只在版本号变大时才提供
  升级，而上游打 tag 往往晚于构成它的提交，所以从 `main` 直接构建必须能表达「比 1.6.10 新」。
  正式发布永远从 tag 构建，于是保持三段版本号。
- **distributor**：默认取 `origin` 的 owner 与 URL，也就是你的 fork；`origin` 还指向上游时
  脚本会直接报错（否则应用商店里会把包记成上游作者），可以显式传
  `PACKAGER=<你的用户名> PACKAGER_URL=<你的 fork>`。
- **载荷**：`app.tgz` 里只有服务器源码（`server/`）、`dashboard.html` 与 `LICENSE`；
  测试、启动脚本、`Dockerfile`、`accounts/`、`usage/` 一律不进包——构建脚本发现
  `accounts/` 或 `usage/` 会直接失败。
- **校验**：打包前用 `ast.parse` 检查载荷里每个 `.py`；打包后校验必需文件、端口三处一致
  （`manifest` ↔ `ui/config` ↔ `.sc`）与 `manifest` 里声明的 `checksum`（`app.tgz` 的 md5）。

`scripts/verify-fpk.sh` 会像应用中心那样解包，导出 `TRIM_*` 环境变量，然后走完
安装 → 启动 → 用面板登录并导入一份 cockpit tools 格式的账号文件 → 升级（确认账号还在）
→ 停止 → 卸载（两种选择都试一遍），共 40 多项断言。它跑的是真进程、真 HTTP，**但装不了真机**：
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

只有真机才知道的两件事，已经写进脚本与回归测试：

1. `TRIM_APPDEST` 的形状（见上一节）；
2. 同一个 `appname` 已经装过时，`trim-cli app install-fpk` 会以 **10236（已安装）** 拒绝；
   而本包带卸载向导（`wizard/uninstall`），`trim-cli app uninstall --yes` 会以
   「app-center uninstall requires custom wizard parameters; run it from App Center UI」被拒
   （2026-10-05 复测；向导自己的默认选项是 `wizard_delete_data=false`，也就是保留）。
   **升级的做法**：在应用中心里先卸载（向导里选「保留现有文件」），再安装新的 `.fpk` ——
   账号、用量与看板密码都在 `/vol1/@appdata/workbuddy2api` 里原样保留。
   但不要默认「一定保留」：2026-10-05 11:21 的一次卸载（不是 CLI，CLI 会被拒）之后
   `accounts/`、`settings.json`、`usage/` 全没了，而 journal 只留下 `APP_UNINSTALLED`、
   没记当时向导选了什么。升级前先备份：
   `tar czf ~/workbuddy2api-backup.tgz -C /vol1/@appdata workbuddy2api/accounts workbuddy2api/settings.json`
   （账号文件里是凭证，备份文件自己收好）。

## CI

- `.github/workflows/build-fpk.yml`：推送 `v*` tag 时构建 fpk、跑一遍 `scripts/verify-fpk.sh`，
  然后把 `.fpk` 和 `.sha256` 挂到同名 Release 上（手动触发时改为上传 artifact）。
- `.github/workflows/sync-upstream.yml`：每天 03:17 UTC（北京时间 11:17）拉上游
  `ardeyouxipianyi/workbuddy2api-hub` 的 `main`，能快进/自动合并就合并并推送，然后给这个新状态
  打一个 tag 并构建发布；**合并冲突则中止、开一个 issue 留痕并让这次运行失败**，
  不会留下半个合并的仓库。

### 版本号和 tag

上游是「先提交、过几天才打 release tag」，而飞牛只在数字变大时才提示升级，所以版本号 =
**树里最新的上游三段 tag + 第四段（这个基线上的第几次发布）**：

```
上游 tag:              v1.6.10
这个基线的第一次发布:   1.6.10.1     <- tag / manifest / Release 名 / fpk 文件名 都是它
第二次发布:             1.6.10.2
上游发布 v1.6.11 之后:  1.6.11.1     （比任何 1.6.10.x 都大，飞牛会提示升级）
```

第四段数的是**发布**，不是提交：`scripts/build-fpk.sh` 里的 `derive_version` 取「本基线已经
存在的四段 tag 中最大的那个 + 1」。这样不需要手工维护计数器，一批改动对应一个版本，界面里
也不会堆出一串零碎版本。

**过程版本**（还没打算发布、只想丢到设备上试的包）用 `--alpha` 构建，带 `-alpha<k>` 后缀，
k = 距上一次发布过了多少个提交：

```bash
bash scripts/build-fpk.sh                    # 1.6.10.2          发布用
bash scripts/build-fpk.sh --alpha            # 1.6.10.2-alpha3   设备上试用的中间包
bash scripts/build-fpk.sh --print-version    # 只看版本，不构建（可加 --alpha）
```

alpha 包不打 tag、不发 Release，只用于测试；真正发布时去掉后缀，manifest 里的版本永远是纯
数字（飞牛比较版本号的规则没有正式文档，alpha 只出现在我们自己试用的包里，发布包不受影响）。
`vX.Y.Z` 形状的三段 tag 只认上游的：本仓库自己发的四段 tag 在算基线时被刻意忽略。

上游发布 v1.6.11 之后基线上移，第四段重新从 1 开始 —— 版本依然比任何 `1.6.10.x` 大。上游每天
同步一次：只要同步带来了新提交，就会推一个新的 tag 并构建发布（新 fpk + 新 Release），在应用
中心卸载旧包（向导里选保留数据）再装新包即可。

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
