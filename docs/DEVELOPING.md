# 开发说明（不进入发布包）

本仓库是 Lumina 创意工坊模块 `studio.heightforge.heightmap` 的源码仓库。
发布包只包含 `manifest.json`、`ui/index.html`、`assets/icon.png`、
`assets/gallery/*`、`README.md`、`LICENSE`；其余目录仅用于开发。

## 构建与自检

```bash
python tools/make_icon.py                 # 生成 assets/icon.png（静态 PNG，无元数据）
python tools/build_package.py             # 校验 + 打包到 dist/
python tools/build_package.py --check dist/<...>.lumina-workshop   # 只校验已有包
python tools/run_js_tests.py              # 无头浏览器跑引擎单测（27 例）
```

`tools/build_package.py` 的规则是对
`Lumina-Workshop-Registry/src/workshop_registry/package.py` 的复刻（文件白名单、
体积/文件数/压缩比上限、路径安全、manifest 结构、运行时 HTML 资源限制、图像元数据
与动图限制），目的是让不合规在本地就失败。

## 设计约束（来自工坊规则）

- 单一入口 `ui/index.html`，JS/CSS/图像全部内联；不得有 `src=`/`href=` 外链。
- 禁止 `eval(` 与动态 `import(`；`<head>` 必须在第一个 `<script>` 之前。
- 无网络权限：模块内不发起任何请求，仅通过宿主 MessagePort 通信。
- 16 位 PNG 由自研编码器生成（deflate 用 stored 块），不依赖第三方库。

## 已知待办

- 桥接层目前按 `docs/module-development.md` + `contracts.ts` 自行实现最小握手，
  拿到 `@lumina/workshop-sdk` 的 Release 资产后应替换为官方 SDK。
