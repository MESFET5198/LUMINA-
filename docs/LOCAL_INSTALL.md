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
