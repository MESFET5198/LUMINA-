# PR 描述（Lumina-Workshop-Registry）

> 本文档即 PR 正文，可直接粘贴。所有摘要与字节数均由 `dist/` 现场计算
> （`python tools/build_package.py` + `tools/make_registry_record.py`），未经手写。

---

## English

- Module IDs affected: `studio.heightforge.heightmap` (new module, community publisher)
- Immutable GitHub Release tags and assets:
  `v1.3.1` → `studio.heightforge.heightmap-1.3.1.lumina-workshop`
  — 197,712 bytes, sha256 `984361f65526f1bd38928e149be0bc717418f6ecd5837111c92623376dcb6232`,
  manifest sha256 `da26be3c722a0d6f907dd45596b1533b12ab50019b2b3ef974f2ca4527bc61e8`.
  Asset URL: `https://github.com/xueseyinlang-cmyk/LUMINA-/releases/download/v1.3.1/studio.heightforge.heightmap-1.3.1.lumina-workshop`
- Permission or compatibility changes:
  New module declaring `image.pick` and `handoff.image` only (no network, no storage).
  `workshopApi`: `>=1.0.0 <2.0.0`; `luminaVersion`: `>=2.0.0`.
- Ownership changes: none (v1 rejects ownership transfer in normal PRs)
- Revocation evidence, if applicable: none — version `state` is `active`, `revocation` is `null`
- Verification commands and results: see the block at the end of this description.

## 中文

- 涉及的模块 ID：`studio.heightforge.heightmap`（新模块，社区发布者）
- 不可变 GitHub Release 标签与资产：
  `v1.3.1` → `studio.heightforge.heightmap-1.3.1.lumina-workshop`
  —— 197,712 字节，sha256 `984361f65526f1bd38928e149be0bc717418f6ecd5837111c92623376dcb6232`，
  manifest sha256 `da26be3c722a0d6f907dd45596b1533b12ab50019b2b3ef974f2ca4527bc61e8`。
  资产地址：`https://github.com/xueseyinlang-cmyk/LUMINA-/releases/download/v1.3.1/studio.heightforge.heightmap-1.3.1.lumina-workshop`
- 权限或兼容范围变化：
  新模块，只申请 `image.pick` 与 `handoff.image`（无网络、无工程存储权限）。
  `workshopApi`：`>=1.0.0 <2.0.0`；`luminaVersion`：`>=2.0.0`。
- 所有权变化：无（v1 普通 PR 禁止转移所有权）
- 若有封禁，请附证据：无（版本 `state` 为 `active`，`revocation` 为 `null`）
- 验证命令与结果：见文末。

---

## 模块说明 / About the module

**做什么 / What it does**：在工坊里把一张图片转成高度图，并把结果 PNG 交给 Lumina 的
浮雕/拼豆转换器。参数与桌面版 HeightForge 1.3.1 一致：
10 种高度来源（亮度 Rec.709 / 线性亮度 / 平均 / 最大 / R / G / B / Alpha / 饱和度 / 颜色距离）、
输入色阶 + 自动色阶 + 直方图、Gamma、S 曲线对比、高斯平滑、反相、输出量程、
物理高度（mm/cm/in）、台阶化分层（2–8 层，亮度区间 / 颜色选区，可拖拽台阶条）、
三种预览（灰度 / 山体着色 / 法线图）、导出 16 位 / 8 位 PNG、法线图、OBJ 与参数 JSON。
Turn an image into a height map with the same mapping pipeline as the HeightForge
desktop app, then hand the result to Lumina's converter.

**为什么只申请两个权限 / Why only two permissions**：

| 权限 | 具体用途 | 不申请的替代做法 |
| --- | --- | --- |
| `image.pick` | 用户主动选图后读取像素做映射 | 没有它就无法拿到图像 |
| `handoff.image` | 把生成的高度图 PNG 交给 Lumina 转换器 | 没有它结果只能停在模块内部 |
| ~~`project.storage`~~ | 本轮不做工程保存，按「不申请未使用权限」的要求不声明 | 参数通过界面即时生效，退出即丢弃 |
| ~~`color-library.read`~~ | 用不到色库 | — |

**没有网络**：模块内不发起任何请求（沙箱也会拦截）；`ui/index.html` 为单文件自包含，
JS/CSS 全部内联，无 `src=`/`href=` 外链，无 `eval`/动态 `import`。

**官方 SDK**：构建期依赖 `@lumina/workshop-sdk@1.0.2`，按规范以不可变 Release URL
固定（`package.json` + `pnpm-lock.yaml`），随后用 `tools/bundle_sdk.mjs` 把
`dist/{contracts,theme,client}.js` 确定性内联进 `ui/index.html` 的
`<script id="lumina-sdk">`，运行期挂在 `window.LuminaWorkshop`；包内仍零外链。
握手、`image.pick`、`handoff.image`、`lifecycle.ready` 全部走 SDK 的
`connectWorkshop()` / `client.*`，没有自实现 RPC。

**兼容范围怎么来的 / Compatibility evidence**：按 SDK 契约
（`WORKSHOP_API_VERSION = "1.0.0"`、`WORKSHOP_MANIFEST_VERSION = 1`）声明
`>=1.0.0 <2.0.0`；`luminaVersion >= 2.0.0` 对应当前桌面版线。

**已在真机宿主里跑通端到端（Lumina Studio 2.0.0-beta，Windows 11 26100）**：
用本机公开的工坊后端接口 `POST /api/workshop/v1/install/local` 装包并 `activate`，
模块在工坊里显示为「未审核 · 已启用」，点「打开」后运行于沙箱 iframe，徽标显示
「已连接 Lumina」；`image.pick` 拉起宿主原生选图对话框取图，管线实时出高度图，
点「交给 Lumina」后客户端自动切到「图像转换」，左栏出现「创意工坊图像 · 来源模块
studio.heightforge.heightmap」。截图见仓库 `docs/ui_in_lumina.png` 与
`docs/ui_handoff_in_lumina.png`。

**1.3.1 修复的四个验收问题（本 PR 版本）**：

| # | 问题 | 修复 |
| --- | --- | --- |
| 1 | 首次出图后「交给 Lumina」按钮仍不可点 | 按钮状态改为由 `syncHandoff()` 单一来源推导：`connected && field && !pending` 即可点，出图即同步 |
| 2 | 转换器已有图片时重复点击无效 | 读 `handoff.image` 返回的 `{status}`：`needs-confirmation` 时按钮变「确认替换」并复用同一 `projectId`，再点一次即完成替换 |
| 3 | 宿主沙箱里导出按钮点了没反应 | 宿主内隐藏导出控件并显示说明（导出只在独立打开时可用）；独立打开时五种格式照常，真的写出文件 |
| 4 | 台阶化后 Gamma/对比仍在参与，与文案矛盾 | 分层时管线改走 `mapFieldBanded()`（模糊→色阶→分层→反相→量程，跳过 Gamma/对比），并禁用这两个滑杆 + 显示提示 |

---

## 验证输出 / Verification

```text
$ python tools/build_package.py
[ok] dist\studio.heightforge.heightmap-1.3.1.lumina-workshop
     id=studio.heightforge.heightmap version=1.3.1
     197712 字节 / 解压 266475 字节 / 6 个文件
     sha256=984361f65526f1bd38928e149be0bc717418f6ecd5837111c92623376dcb6232
     manifestSha256=da26be3c722a0d6f907dd45596b1533b12ab50019b2b3ef974f2ca4527bc61e8
     files=LICENSE, README.md, assets/gallery/screenshot.png, assets/icon.png, manifest.json, ui/index.html

$ python tools/run_js_tests.py
PASS ……（83 例）
RESULT OK 83

$ python tests/test_registry_record.py
校验对象: registry\modules\studio.heightforge.heightmap.json
……（16 例）
RESULT OK
```

- 包内文件严格等于白名单：`manifest.json`、`ui/index.html`、`assets/icon.png`、
  `assets/gallery/screenshot.png`、`README.md`、`LICENSE`（6 个）。
- 构建是确定性的：连续两次打包 sha256 完全一致，可满足「同一资产下载两次字节稳定」。
- 反例自测：多余文件、未知权限、外链脚本、缺 LICENSE、路径穿越、记录字段错配均被本地拦截。

### 1.3.1 — 真机复核发现的两个显示缺陷

在真实 Lumina Studio（工作坊沙箱）里逐项复核时发现两处「逻辑对、但用户看不出来」的问题，已在 1.3.1 修复：

| 现象 | 原因 | 修复 |
| --- | --- | --- |
| 导出发送区在宿主里仍可见（应只留说明） | `#exportCtl` 带内联 `style="display:flex"`，优先级高于 `hidden` 属性 | 增加全局 `[hidden]{display:none !important}`，让 `hidden` 能压过任何内联 display |
| 连接失败时只显示「独立模式」，无法判断原因 | 握手异常被静默吞掉 | 失败时在徽标上显示错误码（`独立模式 · <code>`）并写入 `title`，便于用户与维护者定位 |

验证：引擎用例 83 条全过；`tools/verify_host_fixes.py` 假宿主回归 12 条全过；本机 1.3.1 安装/激活 HTTP 200；真机复核中导出栏只剩说明文字、开启台阶化后 Gamma/对比 呈禁用态并出现提示语。

