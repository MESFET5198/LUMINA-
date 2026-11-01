# PR 描述（可直接粘贴到 Lumina-Workshop-Registry 的新建 PR）

> 使用前把 `<owner>/<repo>` 换成真实仓库地址；除此之外不需要改动任何摘要或字节数
> （数字来自 `dist/` 现场计算，见文末验证输出）。

---

## English

- Module IDs affected: `studio.heightforge.heightmap` (new module, community publisher)
- Immutable GitHub Release tags and assets:
  `v1.0.0` → `studio.heightforge.heightmap-1.0.0.lumina-workshop`
  — 162,106 bytes, sha256 `17e92c08a8f3dc3421697fdb8e442d2d5050e9cb47909d3b142b7a70d66c30f0`,
  manifest sha256 `4b305567d0593b31586436cd103e38f78c6918cec80ec887c1db849127e86f88`.
  Asset URL: `https://github.com/<owner>/<repo>/releases/download/v1.0.0/studio.heightforge.heightmap-1.0.0.lumina-workshop`
- Permission or compatibility changes:
  new module declaring `image.pick` and `handoff.image` only (no network, no storage).
  `workshopApi`: `>=1.0.0 <2.0.0`; `luminaVersion`: `>=2.0.0`.
- Ownership changes: none (v1 rejects ownership transfer in normal PRs)
- Revocation evidence, if applicable: none — version `state` is `active`, `revocation` is `null`
- Verification commands and results: see the block at the end of this description.

## 中文

- 涉及的模块 ID：`studio.heightforge.heightmap`（新模块，社区发布者）
- 不可变 GitHub Release 标签与资产：
  `v1.0.0` → `studio.heightforge.heightmap-1.0.0.lumina-workshop`
  —— 162,106 字节，sha256 `17e92c08a8f3dc3421697fdb8e442d2d5050e9cb47909d3b142b7a70d66c30f0`，
  manifest sha256 `4b305567d0593b31586436cd103e38f78c6918cec80ec887c1db849127e86f88`。
  资产地址：`https://github.com/<owner>/<repo>/releases/download/v1.0.0/studio.heightforge.heightmap-1.0.0.lumina-workshop`
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

**尚未验证的部分（如实说明）**：模块的宿主桥接是按公开文档自实现的最小握手，
尚未替换为官方 `@lumina/workshop-sdk`，也**没有在真实 Lumina 客户端里安装试跑**。
本 PR 提交前若要补这一步，会先把结果补进本节。

---

## 验证输出 / Verification

```text
$ python tools/build_package.py --check dist/studio.heightforge.heightmap-1.0.0.lumina-workshop
[ok] dist\studio.heightforge.heightmap-1.0.0.lumina-workshop
     id=studio.heightforge.heightmap version=1.0.0
     162106 字节 / 解压 186080 字节 / 6 个文件
     sha256=17e92c08a8f3dc3421697fdb8e442d2d5050e9cb47909d3b142b7a70d66c30f0
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
