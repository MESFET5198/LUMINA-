# 提交到 Lumina-Workshop-Registry 的操作手册

本文件描述把 `studio.heightforge.heightmap` 上架到创意工坊的最后一段流程。
**记录已经生成好了**，只差把占位仓库地址换成真实地址。

## 0. 现状

| 项目 | 值 |
| --- | --- |
| 模块 ID | `studio.heightforge.heightmap` |
| 版本 | `1.0.0` |
| 包文件 | `studio.heightforge.heightmap-1.1.1.lumina-workshop` |
| 包大小 | 162,106 字节 |
| 包 sha256 | `17e92c08a8f3dc3421697fdb8e442d2d5050e9cb47909d3b142b7a70d66c30f0` |
| manifest sha256 | `4b305567d0593b31586436cd103e38f78c6918cec80ec887c1db849127e86f88` |
| 权限 | `image.pick`、`handoff.image` |
| 兼容 | Workshop API `1.0.0 ≤ x < 2.0.0`；Lumina `≥ 2.0.0` |

草稿记录在 `registry/draft/studio.heightforge.heightmap.json`（`repository` 仍是
`https://github.com/OWNER/heightforge-workshop`）。

## 1. 建仓库并发布 Release（人工，必须先做）

1. 建公开仓库，把本目录推上去（`tools/`、`tests/` 可以一起推，发布包里不含它们）。
2. 打 tag 并发布 Release：

   ```bash
   git tag -a v1.0.0 -m "HeightForge Height Map 1.0.0"
   git push origin v1.0.0
   ```

3. Release 必须是 **非 draft、非 prerelease**，且**只挂一个**模块资产：

   ```text
   tag:      v1.0.0
   asset:    studio.heightforge.heightmap-1.1.1.lumina-workshop
   checksum: studio.heightforge.heightmap-1.1.1.lumina-workshop.sha256   # 可选但建议
   ```

4. 确认这个地址能下载到东西（Registry 会从这里抓两次）：

   ```text
   https://github.com/<owner>/<repo>/releases/download/v1.0.0/studio.heightforge.heightmap-1.1.1.lumina-workshop
   ```

> 资产字节必须与本地 `dist/` 里的一致。若你重新打包过，摘要会变，记录要跟着重新生成。

## 2. 生成正式记录

```bash
python tools/make_registry_record.py \
  --repository https://github.com/<owner>/<repo> \
  --publisher "HeightForge Studio"
```

成功后会写到 `registry/modules/studio.heightforge.heightmap.json`。
脚本会自动核对：tag 与版本、资产名、字节数、两个 sha256、权限、兼容范围、
SemVer 递增；任何一项对不上都会 `[fail]` 而不是写出文件。

想先看效果可以加 `--draft`（写 `registry/draft/`，不覆盖正式记录）。

## 3. 提 PR

在 `Lumina-Workshop-Registry` 仓库里新增一个文件：

```text
modules/studio.heightforge.heightmap.json
```

PR 描述建议直接给：

- 模块做什么（图片 → 高度图，交给 Lumina 转换器）；
- 申请的权限与理由（`image.pick`、`handoff.image`，无网络）；
- 实测过的宿主范围，以及你**实际测试过**的场景（这点审核会问）。

## 4. CI 与审核会检查什么（对应本记录的字段）

| Registry 检查 | 本记录对应处 |
| --- | --- |
| 仓库是精确 HTTPS GitHub 地址 | `repository` |
| tag = `v<version>` 且非 draft/prerelease | `releaseTag` |
| 资产名 = `<moduleId>-<version>.lumina-workshop` | `assetName` |
| 字节数一致 | `assetBytes` |
| 包 sha256 一致 | `sha256` |
| 包内 manifest 的 sha256 一致 | `manifestSha256` |
| 包内 manifest 的 id/version 与记录一致 | `moduleId` / `version` |
| 权限与审核记录一致、且只在白名单内 | `permissions` |
| 兼容范围必须大于等于实测 | `workshopApi` / `luminaVersion` |
| 历史版本只追加、严格递增 | `versions[]` 顺序 |
| 两次下载字节稳定 | 由 CI 抓两次比较，对应本仓库的确定性构建 |

## 5. 可选：本地安装验证

桌面版会把工坊模块装在：

```text
%APPDATA%\lumina-electron\workshop\modules\<moduleId>\<version>\
```

把包装进该目录（现有 `lumina.bead-pattern\1.0.1` 就是样例）即可在客户端里试跑，
**但这是写用户配置目录，必须先经用户同意**；未签名/未登记模块在正式环境可能被拒，
只适合本地冒烟。

## 6. 常见驳回原因（已在本仓库提前规避）

- 包里多了文件（`tools/`、`tests/`、源码工程文件）→ 打包脚本只放白名单文件。
- `ui/index.html` 引用外部资源或用了 `eval` → 打包前静态扫描。
- 图标带 EXIF/ICC、或不是静态 PNG → 图标生成器与校验器都会拦。
- 资产重新上传导致字节变化 → 构建固定时间戳/权限/顺序，两次构建 sha256 一致。
- 记录里的摘要与资产不符 → 记录由脚本从 `dist/` 现场计算，不手抄。
