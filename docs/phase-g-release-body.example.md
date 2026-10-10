# WorkBuddy2API-Hub fnos-<版本>

> GitHub Release 正文模板。复制成 `docs/phase-g-release-body.md`（或任何文件）后替换 `<...>`，
> 再用 `python3 scripts/gh-release.py release-edit fnos-<版本> <文件>` 发布。
> 上传命令与校验清单见 `docs/phase-g-local-release.md`。

本次发布对应上游 `v<上游版本>`，包名 `WorkBuddy2API-Hub_<版本>_all.fpk`，`appname` 仍是
`workbuddy2api`（升级覆盖安装，数据目录 `/vol1/@appdata/workbuddy2api` 不变）。

## 文件与校验

| 文件 | 字节数 | sha256 |
| --- | --- | --- |
| `WorkBuddy2API-Hub_<版本>_all.fpk` | `<size>` | `<sha256>` |
| `WorkBuddy2API-Hub_<版本>_all.fpk.sha256` | `<size>` | — |

校验：`sha256sum -c WorkBuddy2API-Hub_<版本>_all.fpk.sha256`

## 安装 / 升级

1. 应用中心 → 手动安装 → 选择本 Release 的 `.fpk`（覆盖安装即可，端口仍是 8788）。
2. 升级前建议备份 `/vol1/@appdata/workbuddy2api/`（至少 `accounts/` 与 `usage/`）。
3. 卸载默认保留数据目录。

## 本版包含

- <改动 1>
- <改动 2>

## 验证数字

- `python3 tests/run_all.py --jobs 4`：`<passed> passed / 0 failed / 0 skipped`
- `bash scripts/verify-fpk.sh dist/WorkBuddy2API-Hub_<版本>_all.fpk`：`71 passed, 0 failed`

## 已知限制

- <限制 1>
