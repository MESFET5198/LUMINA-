# PR 描述（可直接粘贴到 Lumina-Workshop-Registry 的新建 PR）

> 使用前把 `<owner>/<repo>` 换成真实仓库地址；除此之外不需要改动任何摘要或字节数
> （数字来自 `dist/` 现场计算，见文末验证输出）。

---

## English

- Module IDs affected: `studio.heightforge.heightmap` (new module, community publisher)
- Immutable GitHub Release tags and assets:
  `v1.0.0` → `studio.heightforge.heightmap-1.1.0.lumina-workshop`
  — 198,976 bytes, sha256 `7c027b4445c35b978bb8bc98b6e6ce76033525e5a588bdd8538d9e96cbb9821a`,
  manifest sha256 `4b305567d0593b31586436cd103e38f78c6918cec80ec887c1db849127e86f88`.
  Asset URL: `https://github.com/<owner>/<repo>/releases/download/v1.0.0/studio.heightforge.heightmap-1.1.0.lumina-workshop`
- Permission or compatibility changes:
  new module declaring `image.pick` and `handoff.image` only (no network, no storage).
  `workshopApi`: `>=1.0.0 <2.0.0`; `luminaVersion`: `>=2.0.0`.
- Ownership changes: none (v1 rejects ownership transfer in normal PRs)
- Revocation evidence, if applicable: none — version `state` is `active`, `revocation` is `null`
- Verification commands and results: see the block at the end of this description.

## 中文

- 涉及的模块 ID：`studio.heightforge.heightmap`（新模块，社区发布者）
- 不可变 GitHub Release 标签与资产：
  `v1.0.0` → `studio.heightforge.heightmap-1.1.0.lumina-workshop`
  —— 198,976 字节，sha256 `7c027b4445c35b978bb8bc98b6e6ce76033525e5a588bdd8538d9e96cbb9821a`，
  manifest sha256 `4b305567d0593b31586436cd103e38f78c6918cec80ec887c1db849127e86f88`。
  资产地址：`https://github.com/<owner>/<repo>/releases/download/v1.0.0/studio.heightforge.heightmap-1.1.0.lumina-workshop`
- 权限或兼容范围变化：
  新模块，只申请 `image.pick` 与 `handoff.image`（无网络、无工程存储权限）。
  `workshopApi`：`>=1.0.0 <2.0.0`；`luminaVersion`：`>=2.0.0`。
- 所有权变化：无（v1 普通 PR 禁止转移所有权）
- 若有封禁，请附证据：无（版本 `state` 为 `active`，`revocation` 为 `null`）
- 验证命令与结果：见文末。

---

## 模块说明 / About the module

**做什么 / What it does**：在工坊里把一张图片转成高度图，并把结果 PNG 交给 Lumina 的
浮雕/拼豆转换器。参数与桌面版 HeightForge 1.3.0 一致：高度来源（亮度/平均/通道/饱和度/
颜色距离）、输入色阶、Gamma、S 曲线对比、模糊、反相、输出量程，另有 6 个预设。
Turn an image into a height map with the same mapping pipeline as the HeightForge
desktop app, then hand the PNG to Lumina's converter.

**为什么只申请两个权限 / Why only two permissions**：

| 权限 | 具体用途 | 不申请的替代做法 |
| --- | --- | --- |
| `image.pick` | 用户主动选图后读取像素做映射 | 没有它就无法拿到图像 |
| `handoff.image` | 把生成的高度图 PNG 交给 Lumina 转换器 | 没有它结果只能停在模块内部 |
| ~~`project.storage`~~ | 本轮不做工程保存，按“不申请未使用权限”的要求不声明 | 参数通过界面即时生效，退出即丢弃 |
| ~~`color-library.read`~~ | 用不到色库 | — |

**没有网络**：模块内不发起任何请求（沙箱也会拦截）；`ui/index.html` 为单文件自包含，
JS/CSS 全部内联，无 `src=`/`href=` 外链，无 `eval`/动态 `import`。

**兼容范围怎么来的 / Compatibility evidence**：按宿主发布说明，Workshop API `1.0.0` 与
Manifest `1` 为当前稳定契约，因此声明 `>=1.0.0 <2.0.0`；`luminaVersion >= 2.0.0` 对应
当前桌面版线。**尚未在真机宿主里跑过端到端**（见下），如需更保守的范围请直接告诉我。

**已在真机宿主里跑通端到端（2026-11-02，Lumina Studio 2.0.0-beta，Windows 11 26100）**：
用本机公开的工坊后端接口 `POST /api/workshop/v1/install/local` 装包并 `activate`，
模块在工坊里显示为「未审核 · 已启用 · 当前版本 1.0.0」，点「打开」后运行于沙箱 iframe，
徽标显示「已连接 Lumina」；`image.pick` 走宿主原生选图对话框取图，管线实时出高度图，
点「交给 Lumina」后客户端自动切到「图像转换」，左栏出现「创意工坊图像」来源标注
（`studio.heightforge.heightmap`）。截图见仓库 `docs/ui_in_lumina.png` 与
`docs/ui_handoff_in_lumina.png`。

**仍需说明的部分（如实标注）**：宿主桥接是按宿主 bundle 里的真实协议（`lumina.workshop.ready`
→ `connect` + `MessagePort` → `lumina-workshop-rpc` 帧）自实现的，**没有用官方
`@lumina/workshop-sdk` 依赖**——因为构建环境无法访问 npm/Release 资产。行为已按上述协议对齐，
但若审核要求“必须依赖官方 SDK”，我可以改成引用 `1.0.2` 的 tgz 再重跑一遍。

---

## 验证输出 / Verification

```text
$ python tools/build_package.py --check dist/studio.heightforge.heightmap-1.1.0.lumina-workshop
[ok] dist\studio.heightforge.heightmap-1.1.0.lumina-workshop
     id=studio.heightforge.heightmap version=1.0.0
     198976 字节 / 解压 244897 字节 / 6 个文件
     sha256=7c027b4445c35b978bb8bc98b6e6ce76033525e5a588bdd8538d9e96cbb9821a
     manifestSha256=4b305567d0593b31586436cd103e38f78c6918cec80ec887c1db849127e86f88
     files=LICENSE, README.md, assets/gallery/screenshot.png, assets/icon.png, manifest.json, ui/index.html

$ python tools/run_js_tests.py
PASS ……（27 例）
RESULT OK 27

$ python tests/test_registry_record.py
校验对象: registry\modules\studio.heightforge.heightmap.json
……（16 例）
RESULT OK
```

- 包内文件严格等于白名单：`manifest.json`、`ui/index.html`、`assets/icon.png`、
  `assets/gallery/screenshot.png`、`README.md`、`LICENSE`（6 个，162 KB）。
- 构建是确定性的：连续两次打包 sha256 完全一致，可用于满足“同一资产下载两次字节稳定”。
- 反例自测：多余文件、未知权限、外链脚本、缺 LICENSE、路径穿越、记录字段错配均被本地拦截。
