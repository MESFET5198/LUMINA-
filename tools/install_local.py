#!/usr/bin/env python3
"""把 ``dist`` 里的模块包装进本机 Lumina Studio（开发者本机验证用）。

不依赖第三方库，只用标准库拼 multipart。Lumina Studio 需要处于运行状态，
后端默认监听 ``http://127.0.0.1:8000``。

    python tools/install_local.py                      # 自动挑最新包
    python tools/install_local.py --archive dist/xxx.lumina-workshop
    python tools/install_local.py --version 1.1.0 --activate
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000"


def _multipart(path: Path, field: str = "archive") -> tuple[bytes, str]:
    boundary = "----heightforge" + uuid.uuid4().hex
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{path.name}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    return head + path.read_bytes() + tail, f"multipart/form-data; boundary={boundary}"


def _post(url: str, data: bytes, ctype: str) -> tuple[int, str]:
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def latest_package() -> Path:
    pkgs = sorted((ROOT / "dist").glob("*.lumina-workshop"), key=lambda p: p.stat().st_mtime)
    if not pkgs:
        raise SystemExit("[fail] dist/ 里没有 .lumina-workshop 包，先跑 tools/build_package.py")
    return pkgs[-1]


def install(archive: Path) -> dict:
    body, ctype = _multipart(archive)
    status, text = _post(f"{BASE}/api/workshop/v1/install/local", body, ctype)
    print(f"[install] HTTP {status}")
    if status >= 400:
        raise SystemExit("[fail] 安装失败：" + text[:400])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def activate(module_id: str, version: str) -> None:
    payload = json.dumps({"version": version}).encode()
    status, text = _post(f"{BASE}/api/workshop/v1/modules/{module_id}/activate", payload, "application/json")
    print(f"[activate] HTTP {status} {text[:200]}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="安装本地工坊模块到 Lumina Studio")
    ap.add_argument("--archive", type=Path, default=None, help="指定 .lumina-workshop 包")
    ap.add_argument("--version", default=None, help="安装后激活的版本，默认取包内 manifest")
    ap.add_argument("--activate", action="store_true", help="安装后立即激活")
    args = ap.parse_args(argv)

    archive = args.archive or latest_package()
    if not archive.is_absolute():
        archive = (ROOT / archive) if (ROOT / archive).exists() else archive
    print(f"[pkg] {archive} ({archive.stat().st_size} bytes)")

    result = install(archive)
    print(json.dumps(result, ensure_ascii=False)[:600])

    version = args.version
    module_id = "studio.heightforge.heightmap"
    if args.activate:
        if not version:
            import zipfile

            with zipfile.ZipFile(archive) as zf:
                version = json.loads(zf.read("manifest.json"))["version"]
        activate(module_id, version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
