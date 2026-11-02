#!/usr/bin/env python3
"""发 1.3.0 的 GitHub Release 并回下载校验（用本机已存的 git 凭据）。

- 凭据：``git credential fill`` 取 https://github.com 的 password（PAT）
- 网络：api.github.com 先直连，失败再走本地代理 127.0.0.1:7890
- 上传后再把资产下载回来比对 sha256，确保 Release 上的字节与本地一致

用法： python tools/publish_release.py --tag v1.3.0 --asset dist/xxx.lumina-workshop [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.error
import urllib.request

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = "xueseyinlang-cmyk"
REPO = "LUMINA-"
API = "https://api.github.com"
PROXY = "http://127.0.0.1:7890"


def token() -> str:
    out = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True, text=True, timeout=60,
    )
    for line in out.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("取不到 GitHub 凭据（git credential fill 无 password）")


def open_with_fallback(req: urllib.request.Request, *, data=None, method=None):
    """先直连，失败再走代理。返回 (status, bytes)。"""
    def _do(handler):
        opener = urllib.request.build_opener(handler)
        try:
            with opener.open(req, timeout=180) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as err:      # 4xx/5xx 也是有效响应，交给调用方判断
            return err.code, err.read()

    handlers = [urllib.request.ProxyHandler({}),
                urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})]
    last = None
    for handler in handlers:
        try:
            return _do(handler)
        except Exception as exc:  # noqa: BLE001 - 直连/代理都可能失败
            last = exc
    raise SystemExit(f"请求失败：{last}")


def api(path: str, *, tok: str, data: dict | None = None, method: str | None = None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        API + path, data=body,
        headers={
            "Authorization": f"Bearer {tok}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "heightforge-release",
            **({"Content-Type": "application/json"} if body else {}),
        },
        method=method or ("POST" if body else "GET"),
    )
    status, raw = open_with_fallback(req)
    return status, (json.loads(raw.decode()) if raw else None)


def upload_asset(tok: str, upload_url: str, name: str, payload: bytes):
    """GitHub 的资产上传接口收的是**原始字节**，不是 multipart（用 multipart 会把信封一起存进去）。"""
    url = upload_url.split("{")[0]
    req = urllib.request.Request(
        f"{url}?name={name}", data=payload,
        headers={
            "Authorization": f"Bearer {tok}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/octet-stream",
            "User-Agent": "heightforge-release",
        },
        method="POST",
    )
    status, raw = open_with_fallback(req)
    return status, (json.loads(raw.decode()) if raw else None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--asset", required=True)
    ap.add_argument("--name", default="")
    ap.add_argument("--notes-file", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    asset = Path(args.asset)
    if not asset.is_file():
        raise SystemExit(f"找不到资产：{asset}")
    payload = asset.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    name = args.name or asset.name
    print(f"[asset] {name}  {len(payload)} bytes  sha256={digest}")

    tok = token()
    if args.dry_run:
        print("[dry-run] 不实际创建 Release")
        return 0

    notes = Path(args.notes_file).read_text(encoding="utf-8") if args.notes_file else f"studio.heightforge.heightmap {args.tag}"

    # 已存在就先取，避免重复创建报 422
    status, existing = api(f"/repos/{OWNER}/{REPO}/releases/tags/{args.tag}", tok=tok)
    if status == 200:
        rel = existing
        print(f"[release] 已存在 id={rel['id']}，复用")
    else:
        status, rel = api(
            f"/repos/{OWNER}/{REPO}/releases", tok=tok,
            data={
                "tag_name": args.tag,
                "name": f"studio.heightforge.heightmap {args.tag}",
                "body": notes,
                "draft": False,
                "prerelease": False,
            },
        )
        print(f"[release] 创建 HTTP {status} id={(rel or {}).get('id')}")

    have = {a["name"]: a for a in rel.get("assets", [])}
    if name in have:
        print(f"[asset] Release 上已有同名资产（{have[name]['size']} 字节），先删再传")
        api(f"/repos/{OWNER}/{REPO}/releases/assets/{have[name]['id']}", tok=tok, method="DELETE")

    status, uploaded = upload_asset(tok, rel["upload_url"], name, payload)
    print(f"[upload] HTTP {status} state={uploaded.get('state')} size={uploaded.get('size')}")

    # 回下载比对
    url = f"https://github.com/{OWNER}/{REPO}/releases/download/{args.tag}/{name}"
    req = urllib.request.Request(url, headers={"User-Agent": "heightforge-release"})
    status, back = open_with_fallback(req)
    back_digest = hashlib.sha256(back).hexdigest()
    same = back_digest == digest and len(back) == len(payload)
    print(f"[verify] HTTP {status} {len(back)} bytes sha256={back_digest} 一致={same}")
    print(f"[url] {url}")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
