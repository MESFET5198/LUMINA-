#!/usr/bin/env python3
"""把 Registry 记录转成可直接 ``git apply`` 的补丁。

用法::

    python tools/make_registry_patch.py                    # 读 registry/modules/<id>.json
    python tools/make_registry_patch.py --allow-placeholder

输出 ``registry/registry-pr.patch``：在 Lumina-Workshop-Registry 的克隆里
``git apply ../registry-pr.patch`` 就会新增 ``modules/<moduleId>.json``。
仓库地址仍是占位符时默认拒绝生成，避免把占位记录误提交。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from make_registry_record import is_placeholder_repository  # noqa: E402


def build_patch(record_path: Path) -> tuple[str, str, str]:
    """返回 (补丁文本, 目标路径, 提交标题)。"""
    raw = record_path.read_bytes()
    record = json.loads(raw)
    module_id = record["moduleId"]
    dest = f"modules/{module_id}.json"

    # git 用 sha1("blob <len>\\0" + 内容) 作为 blob id，补丁里的 index 行需要它
    header = f"blob {len(raw)}\0".encode()
    blob = hashlib.sha1(header + raw).hexdigest()

    text = raw.decode("utf-8")
    lines = text.splitlines()
    body = "\n".join("+" + line for line in lines)
    patch = (
        f"diff --git a/{dest} b/{dest}\n"
        "new file mode 100644\n"
        f"index 0000000000000000000000000000000000000000..{blob}\n"
        "--- /dev/null\n"
        f"+++ b/{dest}\n"
        f"@@ -0,0 +1,{len(lines)} @@\n"
        f"{body}\n"
    )
    version = record["versions"][0]["version"]
    subject = f"feat(modules): add {module_id} {version}"
    return patch, dest, subject


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成可 git apply 的 Registry 补丁")
    parser.add_argument("--record", type=Path, help="记录文件；默认 registry/modules/ 下唯一一份")
    parser.add_argument("--out", type=Path, default=ROOT / "registry" / "registry-pr.patch")
    parser.add_argument("--allow-placeholder", action="store_true")
    args = parser.parse_args(argv)

    if args.record:
        record_path = args.record
    else:
        found = sorted((ROOT / "registry" / "modules").glob("*.json"))
        if len(found) != 1:
            print(f"[fail] registry/modules/ 下应恰好有一份记录，实际 {len(found)} 份")
            return 1
        record_path = found[0]

    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"[fail] 读不了记录: {exc}")
        return 1

    if is_placeholder_repository(record["repository"]) and not args.allow_placeholder:
        print("[fail] 记录里的仓库地址还是占位符；替换后重跑，或显式加 --allow-placeholder")
        return 1

    patch, dest, subject = build_patch(record_path)
    args.out.write_text(patch, encoding="utf-8", newline="\n")
    print(f"[ok] {args.out}")
    print(f"     目标文件: {dest}")
    print(f"     建议提交标题: {subject}")
    print("     应用方式: cd <registry 克隆> && git apply " + str(args.out))
    if is_placeholder_repository(record["repository"]):
        print("[placeholder] 补丁里仍是占位仓库地址，不可提交")
    return 0


if __name__ == "__main__":
    sys.exit(main())
