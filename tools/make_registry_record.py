#!/usr/bin/env python3
"""生成并校验 Registry 的模块源记录（``modules/<moduleId>.json``）。

记录结构以 ``Lumina-Workshop-Registry/src/workshop_registry/models.py`` 为准
（``ModuleSource`` / ``VersionBase`` / ``Permission`` / ``Revocation``），这里用
标准库复刻同样的约束，保证提交前本地就能拦住不合规的字段。

    python tools/make_registry_record.py --repository https://github.com/OWNER/REPO
    python tools/make_registry_record.py --repository ... --draft    # 占位地址，写到 registry/draft/

不带 ``--draft`` 才会写到 ``registry/modules/<moduleId>.json``（即 PR 里真正新增的文件）。
仓库地址还是占位符时必须显式加 ``--allow-placeholder``，否则脚本拒绝生成“可提交”记录。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
MODULE_ID = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+(?:[a-z0-9-]*[a-z0-9])?)*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REASON_CODE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
ALLOWED_PERMISSIONS = {"image.pick", "project.storage", "color-library.read", "handoff.image"}
SEVERITIES = {"low", "medium", "high", "critical"}
STATES = {"active", "deprecated", "blocked"}
PLACEHOLDER_OWNERS = {"owner", "your-account", "your-org", "replace-me", "placeholder"}


class RecordError(ValueError):
    """记录不符合 Registry 模型约束。"""


def _no_dupes(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise RecordError(f"重复字段: {k!r}")
        out[k] = v
    return out


def _strict(obj, allowed: set[str], where: str) -> None:
    extra = set(obj) - allowed
    missing = allowed - set(obj)
    if extra:
        raise RecordError(f"{where} 出现未知字段: {', '.join(sorted(extra))}")
    if missing:
        raise RecordError(f"{where} 缺字段: {', '.join(sorted(missing))}")


def _semver(value, where: str) -> str:
    if not isinstance(value, str) or not SEMVER.fullmatch(value):
        raise RecordError(f"{where} 必须是严格 SemVer")
    return value


def _semver_key(value: str):
    core, _, pre = value.split("+", 1)[0].partition("-")
    major, minor, patch = (int(x) for x in core.split("."))
    ids = tuple((0, int(x)) if x.isdigit() else (1, x) for x in pre.split(".")) if pre else ()
    return major, minor, patch, (1 if not pre else 0), ids


def _text(value, where: str, lo: int, hi: int) -> str:
    if not isinstance(value, str):
        raise RecordError(f"{where} 必须是字符串")
    if not (lo <= len(value.strip()) <= hi):
        raise RecordError(f"{where} 长度必须在 {lo}–{hi} 之间")
    return value


def _localized(value, where: str) -> dict:
    if not isinstance(value, dict) or set(value) != {"zh-CN", "en-US"}:
        raise RecordError(f"{where} 必须是 zh-CN/en-US 双语对象")
    for locale, text in value.items():
        _text(text, f"{where}.{locale}", 1, 200)
    return value


def _api_range(value, where: str) -> dict:
    if not isinstance(value, dict) or set(value) != {"min", "maxExclusive"}:
        raise RecordError(f"{where} 必须只有 min/maxExclusive")
    lo = _semver(value["min"], f"{where}.min")
    hi = _semver(value["maxExclusive"], f"{where}.maxExclusive")
    if _semver_key(hi) <= _semver_key(lo):
        raise RecordError(f"{where}.maxExclusive 必须大于 min")
    return value


def _permissions(value, where: str) -> list:
    if not isinstance(value, list) or len(value) > 32:
        raise RecordError(f"{where} 必须是数组且不超过 32 项")
    names = []
    for item in value:
        if not isinstance(item, dict):
            raise RecordError(f"{where} 的每一项必须是对象")
        _strict(item, {"name", "reason"}, where)
        if item["name"] not in ALLOWED_PERMISSIONS:
            raise RecordError(f"{where} 出现未知权限: {item['name']!r}")
        _text(item["reason"], f"{where}.reason", 1, 500)
        names.append(item["name"])
    if len(names) != len(set(names)):
        raise RecordError(f"{where} 存在重复权限")
    return value


def is_placeholder_repository(repository: str) -> bool:
    """判断仓库地址是否仍是占位符（OWNER / replace-me 之类）。"""
    match = re.fullmatch(r"https://github\.com/([^/]+)/([^/]+)", repository or "")
    if not match:
        return False
    owner, repo = match.group(1).casefold(), match.group(2).casefold()
    return owner in PLACEHOLDER_OWNERS or "replace" in owner or "replace" in repo

def validate_record(record: dict) -> dict:
    _strict(record, {"schemaVersion", "moduleId", "repository", "official", "publisher", "versions"},
            "记录根对象")
    if record["schemaVersion"] != 1:
        raise RecordError("schemaVersion 必须是 1")
    module_id = record["moduleId"]
    if not isinstance(module_id, str) or not MODULE_ID.fullmatch(module_id) or not (3 <= len(module_id) <= 128):
        raise RecordError("moduleId 必须是小写反向域名风格（3–128）")

    repo = record["repository"]
    if not isinstance(repo, str) or not re.fullmatch(r"https://github\.com/[^/]+/[^/]+", repo):
        raise RecordError("repository 必须是精确的 https://github.com/<owner>/<repo>（不带 .git/尾斜杠）")
    if repo.endswith(".git") or repo.endswith("/"):
        raise RecordError("repository 不能带 .git 或尾斜杠")

    if not isinstance(record["official"], bool):
        raise RecordError("official 必须是布尔值")
    _text(record["publisher"], "publisher", 1, 200)

    versions = record["versions"]
    if not isinstance(versions, list) or not (1 <= len(versions) <= 100):
        raise RecordError("versions 必须是 1–100 条的数组")

    previous = None
    for index, item in enumerate(versions, 1):
        where = f"versions[{index}]"
        if not isinstance(item, dict):
            raise RecordError(f"{where} 必须是对象")
        _strict(item, {"version", "releaseTag", "assetName", "assetBytes", "sha256",
                       "manifestSha256", "workshopApi", "luminaVersion", "permissions",
                       "state", "revocation"}, where)
        version = _semver(item["version"], f"{where}.version")
        if previous is not None and _semver_key(version) <= _semver_key(previous):
            raise RecordError(f"{where}.version 必须严格递增（重复或倒序都不允许）")
        previous = version

        tag = item["releaseTag"]
        if not isinstance(tag, str) or tag != f"v{version}":
            raise RecordError(f"{where}.releaseTag 必须等于 v{version}")
        _text(tag, f"{where}.releaseTag", 2, 160)

        expected_asset = f"{module_id}-{version}.lumina-workshop"
        if item["assetName"] != expected_asset:
            raise RecordError(f"{where}.assetName 必须等于 {expected_asset}")
        _text(item["assetName"], f"{where}.assetName", 1, 240)

        size = item["assetBytes"]
        if not isinstance(size, int) or isinstance(size, bool) or not (0 < size <= 100 * 1024 * 1024):
            raise RecordError(f"{where}.assetBytes 必须是 0 与 100 MiB 之间的整数")

        for key in ("sha256", "manifestSha256"):
            if not isinstance(item[key], str) or not SHA256.fullmatch(item[key]):
                raise RecordError(f"{where}.{key} 必须是 64 位小写十六进制")

        _api_range(item["workshopApi"], f"{where}.workshopApi")
        lum = item["luminaVersion"]
        if not isinstance(lum, dict) or set(lum) != {"min"}:
            raise RecordError(f"{where}.luminaVersion 必须只有 min")
        _semver(lum["min"], f"{where}.luminaVersion.min")

        _permissions(item["permissions"], f"{where}.permissions")

        state = item["state"]
        if state not in STATES:
            raise RecordError(f"{where}.state 必须是 {sorted(STATES)} 之一")
        rev = item["revocation"]
        if state == "blocked" and rev is None:
            raise RecordError(f"{where}：blocked 版本必须带 revocation")
        if state != "blocked" and rev is not None:
            raise RecordError(f"{where}：只有 blocked 版本可以带 revocation")
        if rev is not None:
            _strict(rev, {"reasonCode", "severity", "message"}, f"{where}.revocation")
            code = rev["reasonCode"]
            if not isinstance(code, str) or not REASON_CODE.fullmatch(code) or not (2 <= len(code) <= 80):
                raise RecordError(f"{where}.revocation.reasonCode 不合法")
            if rev["severity"] not in SEVERITIES:
                raise RecordError(f"{where}.revocation.severity 不合法")
            _localized(rev["message"], f"{where}.revocation.message")
    return record


def build_record(package: Path, repository: str, publisher: str, official: bool) -> dict:
    """从实际构建产物生成一条版本记录，摘要与字节数都来自磁盘。"""
    if package.suffix != ".lumina-workshop":
        raise RecordError("包扩展名必须是 .lumina-workshop")
    import zipfile

    data = package.read_bytes()
    with zipfile.ZipFile(package) as zf:
        manifest_raw = zf.read("manifest.json")
    manifest = json.loads(manifest_raw)

    expected_asset = f"{manifest['id']}-{manifest['version']}.lumina-workshop"
    if package.name != expected_asset:
        raise RecordError(f"包名必须是 {expected_asset}")

    return {
        "schemaVersion": 1,
        "moduleId": manifest["id"],
        "repository": repository,
        "official": official,
        "publisher": publisher,
        "versions": [
            {
                "version": manifest["version"],
                "releaseTag": f"v{manifest['version']}",
                "assetName": expected_asset,
                "assetBytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "manifestSha256": hashlib.sha256(manifest_raw).hexdigest(),
                "workshopApi": manifest["workshopApi"],
                "luminaVersion": manifest["luminaVersion"],
                "permissions": manifest["permissions"],
                "state": "active",
                "revocation": None,
            }
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成并校验 Registry 模块源记录")
    parser.add_argument("--repository", required=True, help="模块仓库的精确 GitHub HTTPS 地址")
    parser.add_argument("--publisher", default="HeightForge Studio")
    parser.add_argument("--official", action="store_true", help="官方模块才加这个开关")
    parser.add_argument("--draft", action="store_true", help="写到 registry/draft/（占位地址用）")
    parser.add_argument("--allow-placeholder", action="store_true",
                        help="允许用占位仓库地址生成正式记录（文件仍写 registry/modules/）")
    parser.add_argument("--package", type=Path, help="指定包；默认取 dist/ 下唯一产物")
    args = parser.parse_args(argv)

    try:
        if args.package:
            package = args.package
        else:
            found = sorted((ROOT / "dist").glob("*.lumina-workshop"))
            if len(found) != 1:
                raise RecordError(f"dist/ 下应恰好有一个包，实际 {len(found)} 个")
            package = found[0]

        placeholder = is_placeholder_repository(args.repository)
        if placeholder and not (args.draft or args.allow_placeholder):
            raise RecordError(
                "repository 仍是占位地址；替换成真实仓库地址，"
                "或显式加 --allow-placeholder 生成带占位的正式记录"
            )
        record = build_record(package, args.repository, args.publisher, args.official)
        validate_record(record)

        entry = record["versions"][0]
        download = (
            f"{record['repository']}/releases/download/"
            f"{entry['releaseTag']}/{entry['assetName']}"
        )
        target_dir = ROOT / "registry" / ("draft" if args.draft else "modules")
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{record['moduleId']}.json"
        target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (RecordError, OSError, ValueError, KeyError) as exc:
        print(f"[fail] {exc}")
        return 1

    print(f"[ok] {target}")
    print(f"     moduleId={record['moduleId']} official={record['official']}")
    print(f"     version={entry['version']} asset={entry['assetName']}")
    print(f"     assetBytes={entry['assetBytes']}")
    print(f"     sha256={entry['sha256']}")
    print(f"     manifestSha256={entry['manifestSha256']}")
    print(f"     release 资产地址（提交前必须能下载到）:\n       {download}")
    if args.draft:
        print("[draft] 这是占位记录，换成真实仓库地址后去掉 --draft 重跑")
    elif placeholder:
        print("[placeholder] 记录里的仓库是占位地址，三个硬性前提均未满足，**不可提交 PR**")
        print("              替换地址后重跑：python tools/make_registry_record.py --repository https://github.com/<owner>/<repo>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
