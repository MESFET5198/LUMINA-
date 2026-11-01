# HeightForge 高度图 / HeightForge Height Map

把一张图片转成高度图，并交给 Lumina 继续处理。

Turn an image into a height map and hand it to Lumina.

## 用法 / Usage

1. 点右上角「载入图片」，选一张照片或扫描图（PNG/JPEG/WebP 等常见格式）；
   想先看效果可以点旁边的「示例」，它会现场合成一张硬币图。
2. 在右侧调参数，左侧「高度图」会实时更新：**白 = 最高点，黑 = 最低点**。
3. 满意后点「交给 Lumina」，高度图会作为 PNG 进入 Lumina 的浮雕/拼豆转换器。

1. Choose **载入图片** (Pick image) and open a photo or scan.
2. Adjust the panel on the right; the height map preview updates live.
   **White = highest, black = lowest.**
3. Press **交给 Lumina** (Hand off) to send the PNG to Lumina's converter.

## 参数说明 / Controls

| 参数 | 作用 |
| --- | --- |
| 高度来源 | 用亮度、RGB 平均、单通道、饱和度或「颜色距离」决定高度来源；颜色距离模式下，与目标色接近的像素算最高点 |
| 输入色阶 | 决定**图片里哪些像素**算最低点/最高点：低于左端的一律压到最低，高于右端的一律拉到最高 |
| Gamma / 对比 | 调整中间调：Gamma > 1 压暗中间调，对比用 S 曲线增强层次 |
| 平滑 | 高斯近似模糊，压掉噪点，让浮雕更干净 |
| 反相 | 黑 ↔ 白、最高点 ↔ 最低点 |
| 输出量程 | 决定**最低点/最高点落到多高**：把上限拉到 50%，最亮处也只有一半高 |
| 预设 | 默认 / 硬币徽章 / 地形 / 细节增强 / 柔和平滑 / 全部重置 |

## 输出 / Output

- 「交给 Lumina」：标准 8 位 PNG，随宿主交接（`handoff.image`）。
- 「下载 16 位 PNG」：浏览器内导出 16 位灰度 PNG（0–65535），适合在外部工具里当高度图用。

## 隐私 / Privacy

模块只在本地处理像素：不上传图片、不访问网络、不写入任何凭据。申请的权限只有
`image.pick`（用户选图）与 `handoff.image`（把结果交给 Lumina），v1 也没有通用网络权限。

Everything runs locally in the sandboxed module frame. The module requests only
`image.pick` and `handoff.image`.

## 版本 / Version

1.0.0 — 对应宿主 Workshop API `1.0.0` / Manifest `1`。
