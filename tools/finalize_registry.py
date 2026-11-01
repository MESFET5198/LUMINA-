#!/usr/bin/env python
"""仓库建好后，一条命令把 Registry 记录/补丁/PR 描述刷成真实仓库地址。

用法：
    python tools/finalize_registry.py --repo https://github.com/<owner>/<repo>

它会：
  1. 用真实 repository 重新生成 registry/modules/studio.heightforge.heightmap.json
     （不带 --allow-placeholder，占位地址会被拒）
  2. 重新生成 registry/registry-pr.patch（可直接 git apply 到 Registry 克隆）
  3. 重算 PR 描述里的字节数/摘要
  4. 打印后续的 push / Release / PR 命令
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"


def latest_package() -> Path:
    """取 dist/ 下版本号最大的 .lumina-workshop。"""
    pkgs = sorted(DIST.glob("*.lumina-workshop"))
    if not pkgs:
        raise SystemExit("dist/ 里没有包，先跑 python tools/build_package.py")

    def version_key(path: Path) -> tuple[int, ...]:
        match = re.search(r"-(\d+)\.(\d+)\.(\d+)\.lumina-workshop$", path.name)
        if not match:
            return (0,)
        return tuple(int(part) for part in match.groups())

    return max(pkgs, key=version_key)


def run(*args: str) -> None:
    print("$", " ".join(args))
    proc = subprocess.run([sys.executable, *args], cwd=ROOT, check=False)
    if proc.returncode != 0:
        raise SystemExit(
            f"\n[停止] {' '.join(args[:1])} 返回 {proc.returncode}。"
            "若是占位仓库被拒，请传真实的 https://github.com/<owner>/<repo>。"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="https://github.com/<owner>/<repo>")
    parser.add_argument("--publisher", default="HeightForge Studio")
    parser.add_argument("--package", type=Path, default=None)
    args = parser.parse_args()

    repo = args.repo.strip().rstrip("/")
    if not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise SystemExit(f"仓库地址不合法：{repo}")

    pkg = args.package or latest_package()
    print(f"[包] {pkg.relative_to(ROOT)}")
    run("tools/make_registry_record.py", "--repository", repo,
        "--publisher", args.publisher, "--package", str(pkg.relative_to(ROOT)))
    run("tools/make_registry_patch.py")

    record = json.loads(
        (ROOT / "registry/modules/studio.heightforge.heightmap.json").read_text(encoding="utf-8")
    )
    version = record["versions"][0]
    tag = version["releaseTag"]
    asset = version["assetName"]
    print("\n=== 接下来 4 步 ===")
    print(f"1) 推代码与标签（在本仓库里）：")
    print(f"     git remote add origin {repo}   # 若已有 origin 则跳过")
    print(f"     git push -u origin main && git push origin {tag}")
    print(f"2) 建 Release（Web 或 gh）：tag 选 {tag}，附 1 个资产 {asset}")
    print(f"     gh release create {tag} dist/{asset} --title \"HeightForge 高度图 {version['version']}\" --notes-file README.md")
    print(f"3) 到 Registry 克隆里打补丁并提 PR：")
    print(f"     cd <Lumina-Workshop-Registry> && git apply {ROOT / 'registry/registry-pr.patch'}")
    print(f"     git checkout -b add-studio.heightforge.heightmap && git add -A && git commit -m \"feat(modules): add studio.heightforge.heightmap {version['version']}\"")
    print(f"     git push origin add-studio.heightforge.heightmap   # 然后按 registry/PR_BODY.md 填 PR")
    print(f"4) 回到本仓库记录最终数字：{version['assetBytes']} 字节 / sha256 {version['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
