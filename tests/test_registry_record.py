#!/usr/bin/env python3
"""Registry 记录的负例测试：确认校验器会拦下每一类违规。

    python tests/test_registry_record.py
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from make_registry_record import RecordError, validate_record  # noqa: E402

FORMAL = ROOT / "registry" / "modules" / "studio.heightforge.heightmap.json"
DRAFT = ROOT / "registry" / "draft" / "studio.heightforge.heightmap.json"
BASE_PATH = FORMAL if FORMAL.exists() else DRAFT
BASE = json.loads(BASE_PATH.read_text("utf-8"))


def expect_fail(name: str, mutate) -> bool:
    record = copy.deepcopy(BASE)
    mutate(record)
    try:
        validate_record(record)
    except RecordError as exc:
        print(f"PASS {name}  ->  {exc}")
        return True
    print(f"FAIL {name}  ->  未拦截")
    return False


def expect_ok(name: str, mutate) -> bool:
    record = copy.deepcopy(BASE)
    mutate(record)
    try:
        validate_record(record)
    except RecordError as exc:
        print(f"FAIL {name}  ->  正常记录被误拦：{exc}")
        return False
    print(f"PASS {name}  ->  通过")
    return True


def v(record: dict) -> dict:
    return record["versions"][0]


def main() -> int:
    print(f"校验对象: {BASE_PATH.relative_to(ROOT)}")
    ok = True
    ok &= expect_ok("基线记录", lambda r: None)
    ok &= expect_fail("releaseTag 与版本不一致", lambda r: v(r).__setitem__("releaseTag", "v1.0.1"))
    ok &= expect_fail("assetName 拼错", lambda r: v(r).__setitem__("assetName", "heightmap-1.0.0.lumina-workshop"))
    ok &= expect_fail("sha256 大写", lambda r: v(r).__setitem__("sha256", v(r)["sha256"].upper()))
    ok &= expect_fail("sha256 太短", lambda r: v(r).__setitem__("sha256", "abc123"))
    ok &= expect_fail("多余字段", lambda r: v(r).__setitem__("downloadUrl", "https://x"))
    ok &= expect_fail("blocked 缺 revocation", lambda r: v(r).__setitem__("state", "blocked"))
    ok &= expect_fail("非 blocked 却带 revocation", lambda r: v(r).__setitem__("revocation", {
        "reasonCode": "security.review", "severity": "high",
        "message": {"zh-CN": "安全审查", "en-US": "Security review"}}))
    ok &= expect_fail("未知权限", lambda r: v(r)["permissions"].append({"name": "network.any", "reason": "x"}))
    ok &= expect_fail("重复权限", lambda r: v(r)["permissions"].append(copy.deepcopy(v(r)["permissions"][0])))
    ok &= expect_fail("repository 带 .git", lambda r: r.__setitem__("repository", "https://github.com/a/b.git"))
    ok &= expect_fail("moduleId 大写", lambda r: r.__setitem__("moduleId", "Studio.HeightForge.HeightMap"))
    ok &= expect_fail("workshopApi 上限不大于下限", lambda r: v(r)["workshopApi"].__setitem__("maxExclusive", "1.0.0"))
    ok &= expect_fail("版本倒序", lambda r: r["versions"].append({**copy.deepcopy(v(r)), "version": "0.9.0",
                                                                  "releaseTag": "v0.9.0"}))
    # 下一个补丁版本要从记录的当前版本算出来，否则记录版本一升测试就失效
    _maj, _min, _pat = (int(x) for x in v(BASE)["version"].split("."))
    _next = f"{_maj}.{_min}.{_pat + 1}"
    ok &= expect_ok("第二个更高版本", lambda r: r["versions"].append({
        **copy.deepcopy(v(r)), "version": _next, "releaseTag": "v" + _next,
        "assetName": f"studio.heightforge.heightmap-{_next}.lumina-workshop"}))
    ok &= expect_ok("合法的 blocked + revocation", lambda r: v(r).update({
        "state": "blocked",
        "revocation": {"reasonCode": "security.removed", "severity": "critical",
                       "message": {"zh-CN": "安全原因下架", "en-US": "Removed for security reasons"}}}))

    print("\nRESULT", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
