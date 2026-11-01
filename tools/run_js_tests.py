#!/usr/bin/env python3
"""在无头 Chrome/Edge 里跑 ``ui/index.html`` 内联引擎的单元测试。

思路：从 ``ui/index.html`` 里抽出 ``<script id="engine">`` 的源码（唯一来源，
不在测试里复制一份），拼进一个断言页，再用 ``--headless --dump-dom`` 读回结果。
没有 Node、没有 npm，也不改模块本身的构建方式。

    python tools/run_js_tests.py
"""

from __future__ import annotations

import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

ENGINE_RE = re.compile(
    r'<script id="engine">(.*?)</script>', re.DOTALL
)

CASES = r"""
const E = window.HeightForgeEngine;
const results = [];
function ok(name, cond, extra) {
  results.push({ name, pass: !!cond, extra: extra === undefined ? "" : String(extra) });
}
function near(a, b, eps) { return Math.abs(a - b) <= (eps === undefined ? 1e-4 : eps); }

// --- 输入色阶 -------------------------------------------------------------
{
  const field = new Float32Array([0, 0.25, 0.5, 0.75, 1]);
  const out = E.mapField(field, 5, 1, {inLo: 0.25, inHi: 0.75, gamma: 1, contrast: 1, blur: 0, invert: false, outLo: 0, outHi: 1});
  ok("色阶：两端夹取", near(out[0], 0) && near(out[4], 1), `[${out[0]},${out[4]}]`);
  ok("色阶：中间线性", near(out[2], 0.5), out[2]);
  ok("色阶：单调", out[0] <= out[1] && out[1] <= out[2] && out[2] <= out[3] && out[3] <= out[4]);
}
// --- 输出量程 -------------------------------------------------------------
{
  const field = new Float32Array([0, 0.5, 1]);
  const out = E.mapField(field, 3, 1, {inLo: 0, inHi: 1, gamma: 1, contrast: 1, blur: 0, invert: false, outLo: 0.1, outHi: 0.5});
  ok("量程：下限", near(out[0], 0.1), out[0]);
  ok("量程：上限", near(out[2], 0.5), out[2]);
  ok("量程：中点", near(out[1], 0.3), out[1]);
}
// --- 反相 / 退化色阶 -------------------------------------------------------
{
  const field = new Float32Array([0, 0.3, 1]);
  const inv = E.mapField(field, 3, 1, {inLo: 0, inHi: 1, gamma: 1, contrast: 1, blur: 0, invert: true, outLo: 0, outHi: 1});
  ok("反相：端点互换", near(inv[0], 1) && near(inv[2], 0), `[${inv[0]},${inv[2]}]`);
  const thr = E.mapField(field, 3, 1, {inLo: 0.5, inHi: 0.5, gamma: 1, contrast: 1, blur: 0, invert: false, outLo: 0, outHi: 1});
  ok("退化色阶 → 二值", near(thr[0], 0) && near(thr[1], 0) && near(thr[2], 1), `[${thr[0]},${thr[1]},${thr[2]}]`);
}
// --- 亮度 / 颜色距离 / 饱和度 --------------------------------------------
{
  const rgba = new Uint8ClampedArray([255,255,255,255, 0,0,0,255, 200,20,20,255]);
  const luma = E.extractSource(rgba, "luma");
  ok("亮度：白=1 黑=0", near(luma[0], 1) && near(luma[1], 0), `[${luma[0]},${luma[1]}]`);
  const target = [200 / 255, 20 / 255, 20 / 255];
  const dist = E.extractSource(rgba, "color", target, 0.25);
  ok("颜色距离：目标色为峰值", near(dist[2], 1), dist[2]);
  ok("颜色距离：远处为 0", near(dist[1], 0, 1e-3), dist[1]);
  const sat = E.extractSource(new Uint8ClampedArray([128,128,128,255, 255,0,0,255]), "saturation");
  ok("饱和度：灰=0 纯红=1", near(sat[0], 0) && near(sat[1], 1), `[${sat[0]},${sat[1]}]`);
}
// --- gamma / 对比 ---------------------------------------------------------
{
  const field = new Float32Array([0.5]);
  const g = E.mapField(field, 1, 1, {inLo: 0, inHi: 1, gamma: 2, contrast: 1, blur: 0, invert: false, outLo: 0, outHi: 1});
  ok("gamma>1 压暗中间调", near(g[0], 0.25), g[0]);
  const flat = E.mapField(new Float32Array([0.25, 0.75]), 2, 1, {inLo: 0, inHi: 1, gamma: 1, contrast: 1, blur: 0, invert: false, outLo: 0, outHi: 1});
  ok("对比=1 不变", near(flat[0], 0.25) && near(flat[1], 0.75), `[${flat[0]},${flat[1]}]`);
  const punch = E.mapField(new Float32Array([0.25, 0.75]), 2, 1, {inLo: 0, inHi: 1, gamma: 1, contrast: 1.6, blur: 0, invert: false, outLo: 0, outHi: 1});
  ok("对比>1 拉开层次", punch[0] < 0.25 && punch[1] > 0.75, `[${punch[0].toFixed(3)},${punch[1].toFixed(3)}]`);
  ok("smoothstep 端点", near(E.smoothstep(0), 0) && near(E.smoothstep(1), 1) && near(E.smoothstep(0.5), 0.5));
}
// --- 模糊 -----------------------------------------------------------------
{
  const w = 32, h = 32;
  const src = new Float32Array(w * h);
  for (let i = 0; i < src.length; i++) src[i] = (i % 2 === 0) ? 0 : 1; // 棋盘噪声
  const blurred = E.blurField(src, w, h, 2);
  const v = (a) => { const m = E.stats(a).mean; let s = 0; for (const x of a) s += (x - m) ** 2; return s / a.length; };
  ok("模糊：方差下降", v(blurred) < v(src) * 0.5, `${v(src).toFixed(4)} → ${v(blurred).toFixed(4)}`);
  ok("模糊：均值基本不变", near(E.stats(blurred).mean, E.stats(src).mean, 0.02));
}
// --- 校验和 / PNG ---------------------------------------------------------
{
  const ascii = (s) => new TextEncoder().encode(s);
  ok("crc32 已知向量", E.crc32(ascii("123456789"), 0, 9) === 0xCBF43926, E.crc32(ascii("123456789"), 0, 9).toString(16));
  ok("adler32 已知向量", E.adler32(ascii("Wikipedia")) === 0x11E60398, E.adler32(ascii("Wikipedia")).toString(16));
}
{
  // 3×2 的高度场 → 16 位 PNG → 只解析 stored 块还原像素
  const w = 3, h = 2;
  const field = new Float32Array([0, 0.5, 1, 0.1, 0.2, 0.3]);
  const png = E.encodePng16(field, w, h);
  const sig = [0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a];
  ok("PNG 签名", sig.every((b, i) => png[i] === b));
  const dv = new DataView(png.buffer, png.byteOffset);
  ok("PNG 宽高", dv.getUint32(16) === w && dv.getUint32(20) === h);
  ok("PNG 位深 16 / 灰度", png[24] === 16 && png[25] === 0, `${png[24]}/${png[25]}`);

  // 找 IDAT
  let at = 8, idat = null;
  while (at < png.length) {
    const len = dv.getUint32(at);
    const type = String.fromCharCode(png[at + 4], png[at + 5], png[at + 6], png[at + 7]);
    if (type === "IDAT") idat = png.subarray(at + 8, at + 8 + len);
    at += 12 + len;
  }
  ok("PNG 有 IDAT", !!idat);
  // 解 stored deflate：0x78 0x01 + 若干块
  const raw = [];
  let p = 2;
  while (p < idat.length) {
    const header = idat[p];
    const final = header & 1;
    const len = idat[p + 1] | (idat[p + 2] << 8);
    for (let i = 0; i < len; i++) raw.push(idat[p + 5 + i]);
    p += 5 + len;
    if (final) break;
  }
  const stride = 1 + w * 2;
  ok("PNG 数据长度", raw.length === stride * h, `${raw.length}/${stride * h}`);
  let expect = [0, 0.5, 1, 0.1, 0.2, 0.3];
  let pixelOk = true;
  for (let y = 0; y < h; y++) {
    if (raw[y * stride] !== 0) pixelOk = false;         // filter = none
    for (let x = 0; x < w; x++) {
      const i = y * stride + 1 + x * 2;
      const value = (raw[i] << 8) | raw[i + 1];
      const want = Math.round(Math.min(1, Math.max(0, expect[y * w + x])) * 65535);
      if (value !== want) pixelOk = false;
    }
  }
  ok("PNG 像素往返一致", pixelOk);
}
// --- 统计 -----------------------------------------------------------------
{
  const s = E.stats(new Float32Array([0, 0.5, 1]));
  ok("统计 min/max/mean", near(s.min, 0) && near(s.max, 1) && near(s.mean, 0.5));
}
"""

HARNESS = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>engine tests</title></head>
<body><pre id="out">RUNNING</pre>
<script id="engine">{engine}</script>
<script>
(function () {{
{cases}
  const failed = results.filter((r) => !r.pass);
  const lines = results.map((r) => (r.pass ? "PASS " : "FAIL ") + r.name + (r.extra ? "  [" + r.extra + "]" : ""));
  lines.push("RESULT " + (failed.length ? "FAIL " + failed.length : "OK " + results.length));
  document.getElementById("out").textContent = lines.join("\\n");
}})();
</script>
</body></html>
"""


def find_browser() -> str:
    for candidate in BROWSERS:
        if Path(candidate).is_file():
            return candidate
    found = shutil.which("chrome") or shutil.which("msedge")
    if found:
        return found
    raise SystemExit("找不到 Chrome/Edge，无法运行浏览器内测试")


def main() -> int:
    source = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    match = ENGINE_RE.search(source)
    if not match:
        raise SystemExit("ui/index.html 里找不到 <script id=\"engine\">")
    engine = match.group(1)

    page = HARNESS.format(engine=engine, cases=CASES)
    workdir = ROOT / ".tmp"
    workdir.mkdir(parents=True, exist_ok=True)
    harness = workdir / "engine_tests.html"
    harness.write_text(page, encoding="utf-8")

    browser = find_browser()
    profile = workdir / "chrome-profile"
    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-first-run",
        "--allow-file-access-from-files",
        f"--user-data-dir={profile}",
        "--virtual-time-budget=8000",
        "--dump-dom",
        harness.as_uri(),
    ]
    # 沙箱禁止为子进程建管道（CreatePipe → WinError 5），所以把浏览器输出写进文件再读
    dom_path = workdir / "dom.txt"
    with dom_path.open("w", encoding="utf-8", errors="replace") as sink:
        proc = subprocess.run(cmd, stdout=sink, stderr=subprocess.DEVNULL, timeout=120)
    dom = dom_path.read_text(encoding="utf-8", errors="replace")
    match_out = re.search(r"<pre id=\"out\">(.*?)</pre>", dom, re.DOTALL)
    if not match_out:
        print(dom[-2000:])
        print(f"[fail] 无法读取测试输出（浏览器退出码 {proc.returncode}）")
        return 1

    text = html.unescape(match_out.group(1))
    print(text)
    tail = [line for line in text.splitlines() if line.startswith("RESULT")]
    if not tail:
        print("[fail] 没有 RESULT 行")
        return 1
    return 0 if tail[-1].startswith("RESULT OK") else 1


if __name__ == "__main__":
    sys.exit(main())
