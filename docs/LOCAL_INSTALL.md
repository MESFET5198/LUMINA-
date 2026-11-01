# 真机安装验证（需你确认后才执行）

这一步会写入用户配置目录 `%APPDATA%\lumina-electron\workshop\`，因此**没有执行**，
下面是完整步骤、预期结果与回滚办法。你确认后我按此执行。

## 现状（已读取，未修改）

```text
%APPDATA%\lumina-electron\workshop\
├── install-state.json          # 模块开关与版本状态
├── modules\
│   └── lumina.bead-pattern\1.0.1\   # 唯一已装模块（官方 seed）
├── projects\
└── staging\
```

`install-state.json` 结构（1 条记录）：

```json
{"modules":[{"active_version":null,"candidate_version":"1.0.1","consecutive_start_failures":0,
"enabled":true,"module_id":"lumina.bead-pattern","official":true,"official_uninstalled":false,
"previous_version":null,"source":"seed",
"source_repository":"https://github.com/lumina-layer-studio/Lumina-Fuse-Bead-Studio",
"versions":["1.0.1"]}],"schemaVersion":1}
```

## 步骤

1. **备份**（可回滚的前提）：

   ```bash
   cp "$APPDATA/lumina-electron/workshop/install-state.json" \
      "$APPDATA/lumina-electron/workshop/install-state.json.bak"
   ```

2. **解包到模块目录**：

   ```bash
   python - <<'PY'
   import zipfile, pathlib
   dest = pathlib.Path(r"%APPDATA%\lumina-electron\workshop\modules\studio.heightforge.heightmap\1.0.0")
   dest.mkdir(parents=True, exist_ok=True)
   with zipfile.ZipFile(r"D:\DSH\heightforge-workshop\dist\studio.heightforge.heightmap-1.0.0.lumina-workshop") as z:
       z.extractall(dest)
   print("extracted ->", dest)
   PY
   ```

3. **在 `install-state.json` 的 `modules` 数组里追加一条**（保持 JSON 合法）：

   ```json
   {"active_version":null,"candidate_version":"1.0.0","consecutive_start_failures":0,
    "enabled":true,"module_id":"studio.heightforge.heightmap","official":false,
    "official_uninstalled":false,"previous_version":null,"source":"local",
    "source_repository":"https://github.com/<owner>/<repo>","versions":["1.0.0"]}
   ```

   > `source` 的取值我是**按 `seed` 推测**的（`local` / `catalog` 两种都可能），
   > 这一步是本方案里唯一的不确定点；如果客户端不认这个值，模块不会出现在列表里。

4. **启动 Lumina Studio → 创意工坊**，观察下面 4 个判据。

## 预期结果与失败判据

| 观察点 | 通过的样子 | 不通过说明什么 |
| --- | --- | --- |
| 模块列表 | 出现「HeightForge 高度图」 | `source` 枚举不对，或客户端拒加载未登记模块 |
| 打开模块 | iframe 里出现深色界面，右上角徽章是「已连接 Lumina」 | 徽章仍是「独立模式」= 桥接握手没通（我的自实现协议与宿主不符） |
| 载入图片 | 弹宿主选图框，选完左侧出现原图、右侧出现高度图 | 权限被拒或 `image.pick` 返回结构与我预期不同 |
| 交给 Lumina | 转换器里出现高度图，可继续生成 | `handoff.image` 参数不符（如必须 8 位 PNG / 必须带 svgBytes） |

浏览器内已验证过的部分（不依赖宿主）：界面渲染、映射管线、16 位 PNG 导出，见
`docs/ui_module.png` 与 `python tools/run_js_tests.py` 的 27 例结果。

## 回滚

```bash
rm -rf "$APPDATA/lumina-electron/workshop/modules/studio.heightforge.heightmap"
cp "$APPDATA/lumina-electron/workshop/install-state.json.bak" \
   "$APPDATA/lumina-electron/workshop/install-state.json"
```

## 为什么值得做

Registry 审核会问“实际测试过什么场景”。目前我能给出的证据是浏览器内的引擎与打包
自检，缺的正是“宿主里点一遍”。这一步做完，PR 里的验证一栏就能写实测；不做的话，
PR 描述里已经如实标注了“尚未在真机宿主验证”。

---

## 实测结果（2026-11-02，已完成）

环境：Lumina Studio 2.0.0-beta（`versions/9c90c988…`），Windows 11 `10.0.26100`。

安装没有走 UI 点击，而是调用客户端自带的工坊后端接口（与工坊页面同一条链路）：

```text
POST /api/workshop/v1/install/local      (multipart, field=archive)  → 200 ok
POST /api/workshop/v1/modules/studio.heightforge.heightmap/activate   → 200 ok
GET  /api/workshop/v1/modules                                          → source=local, active=1.0.0
```

`install-state.json` 里新增条目：`{"module_id":"studio.heightforge.heightmap","source":"local",
"official":false,"enabled":true,"active_version":"1.0.0","versions":["1.0.0"]}`。

截图与判据：

| 环节 | 结果 | 证据 |
| --- | --- | --- |
| 工坊列表 | 出现「HeightForge 高度图」，标记**未审核**，状态「已启用 · 当前版本 1.0.0」 | `.tmp/screen2.png` |
| 点「打开」 | 模块在沙箱 iframe 内运行，徽标**已连接 Lumina** | `docs/ui_in_lumina.png` |
| 选图 | `image.pick` 打开宿主**原生**文件对话框并回传字节 | 同上（960×640 图已载入） |
| 处理 | 原图/高度图并排预览，状态栏 `min 0.000 · max 0.976 · mean 0.739` | 同上 |
| 交给 Lumina | 客户端切到「图像转换」，左栏出现「创意工坊图像 · 来源模块 studio.heightforge.heightmap」 | `docs/ui_handoff_in_lumina.png` |

两个需要注意的环境坑（会误导排查）：

1. 从带 `ELECTRON_RUN_AS_NODE=1` 的 shell 里启动 `Lumina Studio.exe`，Electron 会当 node 跑、
   窗口一闪即退（退出码 0）。用 `env -u ELECTRON_RUN_AS_NODE` 启动即可。
2. 窗口被其他置顶窗口遮住时，模拟点击会落到别的窗口上；把窗口移到空位再点。

## 回滚

```bash
rm -rf "$APPDATA/lumina-electron/workshop/modules/studio.heightforge.heightmap"
cp "$APPDATA/lumina-electron/workshop/install-state.json.bak-<时间戳>" \
   "$APPDATA/lumina-electron/workshop/install-state.json"
```

（本次安装前的备份：`install-state.json.bak-20261102-002113`。）
