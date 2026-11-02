#!/usr/bin/env python3
"""宿主行为回归：用最小假宿主驱动 ui/index.html，验证 1.3.0 修的四个问题。

为什么需要它：这四个问题都发生在 iframe + MessagePort 的真实宿主环境里，
纯函数单测（tools/run_js_tests.py）覆盖不到「按钮什么时候可点」「导出栏是否收起」
这类状态同步。这里起一个本地 HTTP 服务（同源，方便断言 iframe DOM），
再用无头 Chrome 跑一遍：

  1) 载入示例后「交给 Lumina」必须立刻可点
  2) 第一次交接返回 needs-confirmation → 按钮变「确认替换」；再点一次 → 完成
  3) 宿主内导出控件收起、显示说明；独立打开时导出可用
  4) 开启台阶化后 Gamma/对比被禁用并显示提示

用法：
    python tools/verify_host_fixes.py            # 打印 PASS/FAIL 行与 RESULT
    python tools/verify_host_fixes.py --dump     # 额外打印 iframe 外侧 DOM 片段
"""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import subprocess
import sys
import threading
import re
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

HARNESS = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>host harness</title>
<style>html,body{margin:0;height:100%}iframe{width:1400px;height:900px;border:0}</style></head>
<body>
<iframe id="mod" src="/ui/index.html"></iframe>
<pre id="out">RUNNING</pre>
<script>
const results = [];
function ok(name, pass, extra) { results.push({name, pass: !!pass, extra: extra === undefined ? "" : String(extra)}); }
function wait(ms) { return new Promise((r) => setTimeout(r, ms)); }
async function waitFor(fn, timeout) {
  const deadline = Date.now() + (timeout || 5000);
  while (Date.now() < deadline) {
    try { if (fn()) return true; } catch (e) { /* iframe 未就绪 */ }
    await wait(80);
  }
  return false;
}

let handoffCalls = 0;
let connected = false;
window.addEventListener("message", (ev) => {
  const data = ev.data;
  if (!data || data.type !== "lumina.workshop.ready") return;
  const ch = new MessageChannel();
  ch.port1.onmessage = (e) => {
    const frame = e.data || {};
    if (frame.kind !== "request") return;
    let result = {};
    if (frame.method === "handoff.image") {
      handoffCalls += 1;
      result = { status: handoffCalls === 1 ? "needs-confirmation" : "completed" };
    } else if (frame.method === "lifecycle.ready") {
      result = { ok: true };
    }
    ch.port1.postMessage({
      protocol: "lumina-workshop-rpc", version: 1, kind: "response",
      requestId: frame.requestId, ok: true, result,
    });
  };
  connected = true;
  document.getElementById("mod").contentWindow.postMessage(
    { type: "lumina.workshop.connect", sessionId: "harness-session" }, "*", [ch.port2]);
});

(async function () {
  const fr = document.getElementById("mod");
  await new Promise((r) => fr.addEventListener("load", r, { once: true }));
  const win = fr.contentWindow, doc = fr.contentDocument;
  const $ = (id) => doc.getElementById(id);
  await waitFor(() => $("badge") && $("badge").textContent.indexOf("已连接") >= 0, 6000);

  // 3) 宿主内导出必须收起并给说明
  ok("宿主内隐藏导出控件", $("exportCtl").hidden === true);
  ok("宿主内显示导出说明", $("exportNote").hidden === false && $("exportNote").textContent.indexOf("导出") >= 0,
     $("exportNote").textContent.slice(0, 40));

  // 1) 没有图时禁用；载入示例后必须立刻可点
  ok("无图时按钮禁用", $("btnHandoff").disabled === true, $("btnHandoff").disabled);
  $("btnDemo").click();
  const ready = await waitFor(() => $("btnHandoff").disabled === false, 6000);
  ok("示例出图后按钮可点", ready, "disabled=" + $("btnHandoff").disabled);
  ok("按钮文案是「交给 Lumina」", $("btnHandoff").textContent.trim() === "交给 Lumina", $("btnHandoff").textContent.trim());

  // 2) 第一次交接 → needs-confirmation → 「确认替换」→ 再点一次完成
  $("btnHandoff").click();
  await wait(400);
  const toast1 = $("toast").textContent.slice(0, 40);
  const pending = await waitFor(() => $("btnHandoff").textContent.trim() === "确认替换", 6000);
  ok("第一次交接后进入待确认", pending,
     "label=" + $("btnHandoff").textContent.trim() + " calls=" + handoffCalls + " toast=" + toast1);
  ok("待确认时按钮仍可点", $("btnHandoff").disabled === false);
  $("btnHandoff").click();
  const done = await waitFor(() => handoffCalls === 2 && $("btnHandoff").textContent.trim() === "交给 Lumina", 6000);
  ok("第二次点击完成替换", done, "calls=" + handoffCalls + " label=" + $("btnHandoff").textContent.trim());

  // 4) 台阶化后 Gamma/对比禁用 + 提示
  const gamma = $("rngGamma"), contrast = $("rngContrast"), hint = $("hintCurves");
  ok("台阶化前曲线可用", gamma.disabled === false && hint.hidden === true);
  $("chkLayers").checked = true;
  $("chkLayers").dispatchEvent(new Event("change"));
  const disabled = await waitFor(() => gamma.disabled === true, 4000);
  ok("台阶化后 Gamma/对比禁用", disabled && contrast.disabled === true);
  ok("台阶化后显示曲线提示", hint.hidden === false && hint.textContent.length > 0, hint.textContent.slice(0, 30));
  $("chkLayers").checked = false;
  $("chkLayers").dispatchEvent(new Event("change"));
  const restored = await waitFor(() => gamma.disabled === false && hint.hidden === true, 4000);
  ok("关掉台阶化后曲线恢复", restored);

  const failed = results.filter((r) => !r.pass);
  const lines = results.map((r) => (r.pass ? "PASS " : "FAIL ") + r.name + (r.extra ? "  [" + r.extra + "]" : ""));
  lines.push("RESULT " + (failed.length ? "FAIL " + failed.length : "OK " + results.length));
  document.getElementById("out").textContent = lines.join("\n");
})();
</script>
</body></html>
"""


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D401 - 保持安静
        pass


def find_browser() -> str:
    for candidate in BROWSERS:
        if Path(candidate).is_file():
            return candidate
    raise SystemExit("找不到 Chrome/Edge，无法运行宿主行为回归")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", action="store_true", help="额外打印原始 DOM 尾部")
    args = ap.parse_args()

    (ROOT / ".tmp").mkdir(exist_ok=True)
    (ROOT / ".tmp" / "host_harness.html").write_text(HARNESS, encoding="utf-8")

    handler = functools.partial(QuietHandler, directory=str(ROOT))
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{port}/.tmp/host_harness.html"

        browser = find_browser()
        dom_path = ROOT / ".tmp" / "host_dom.txt"
        cmd = [
            browser, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
            "--allow-file-access-from-files", "--window-size=1420,960",
            f"--user-data-dir={ROOT / '.tmp' / 'chrome-profile'}",
            "--virtual-time-budget=12000", "--dump-dom", url,
        ]
        with dom_path.open("w", encoding="utf-8", errors="replace") as sink:
            subprocess.run(cmd, stdout=sink, stderr=subprocess.DEVNULL, timeout=180)
        dom = dom_path.read_text(encoding="utf-8", errors="replace")
        httpd.shutdown()

    match = re.search(r'<pre id="out">(.*?)</pre>', dom, re.DOTALL)
    if not match:
        print(dom[-1500:])
        print("[fail] 读不到测试输出")
        return 1
    text = html.unescape(match.group(1))
    print(text)
    if args.dump:
        print("---- DOM tail ----")
        print(dom[-800:])
    tail = [ln for ln in text.splitlines() if ln.startswith("RESULT")]
    if not tail:
        print("[fail] 没有 RESULT 行")
        return 1
    return 0 if tail[-1].startswith("RESULT OK") else 1


if __name__ == "__main__":
    sys.exit(main())
