#!/usr/bin/env python3
"""Build and statically validate a ``.lumina-workshop`` package.

The checks here deliberately mirror
``Lumina-Workshop-Registry/src/workshop_registry/package.py`` so a package can
fail locally, before a Registry PR is opened. Nothing in this file is imported
by the module at runtime; it is build tooling only.

Usage::

    python tools/build_package.py            # 校验 + 打包到 dist/
    python tools/build_package.py --check dist/xxx.lumina-workshop
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import stat
import struct
import sys
import unicodedata
import zipfile
from html.parser import HTMLParser
from pathlib import Path

from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]

# ---- 与注册表一致的硬上限 -------------------------------------------------
MAX_PACKAGE_BYTES = 100 * 1024 * 1024
MAX_UNPACKED_BYTES = 300 * 1024 * 1024
MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_FILE_COUNT = 2_000
MAX_COMPRESSION_RATIO = 100.0
MAX_IMAGE_EDGE = 16_384
MAX_MANIFEST_BYTES = 256 * 1024
MAX_ICON_BYTES = 2 * 1024 * 1024
MAX_ICON_PIXELS = 1_048_576
MAX_GALLERY_FILES = 20
MAX_GALLERY_FILE_BYTES = 5 * 1024 * 1024
MAX_GALLERY_PIXELS = 16_000_000
MAX_TEXT_DOCUMENT_BYTES = 1024 * 1024

REQUIRED_FILES = {
    "manifest.json",
    "ui/index.html",
    "assets/icon.png",
    "README.md",
    "LICENSE",
}
GALLERY_PREFIX = "assets/gallery/"
GALLERY_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_COMPRESSION = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
RESERVED_DEVICE_NAMES = {
    "con", "prn", "aux", "nul",
    *{f"com{i}" for i in range(1, 10)},
    *{f"lpt{i}" for i in range(1, 10)},
}
PERMISSIONS = {"image.pick", "project.storage", "color-library.read", "handoff.image"}
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
MODULE_ID = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+(?:[a-z0-9-]*[a-z0-9])?)*$")
CSS_URL = re.compile(r"url\s*\(\s*([^)]+?)\s*\)", re.IGNORECASE)
HEAD_TAG = re.compile(r"<head(?:\s|>)", re.IGNORECASE)
SCRIPT_TAG = re.compile(r"<script(?:\s|>)", re.IGNORECASE)
DYNAMIC_CODE = re.compile(r"\b(?:eval|import)\s*\(", re.IGNORECASE)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SUSPICIOUS = (b"http://", b"https://", b"file://", b"javascript:", b"<script", b"<svg", b"<html")


class PackageError(ValueError):
    """A package failed the static trust-boundary inspection."""


# ---- 路径与 zip 元数据 ---------------------------------------------------
def _check_member(info: zipfile.ZipInfo, seen: set[str]) -> None:
    name = info.filename
    if (
        not name
        or "\x00" in name
        or "\\" in name
        or name.startswith("/")
        or name.endswith("/")
        or unicodedata.normalize("NFC", name) != name
    ):
        raise PackageError(f"路径不安全: {name!r}")
    parts = name.split("/")
    if any(p in {"", ".", ".."} for p in parts):
        raise PackageError(f"路径不安全: {name!r}")
    for part in parts:
        if ":" in part or part.endswith((" ", ".")):
            raise PackageError(f"路径不安全: {name!r}")
        if part.split(".", 1)[0].casefold() in RESERVED_DEVICE_NAMES:
            raise PackageError(f"路径使用了 Windows 设备名: {name!r}")
    key = name.casefold()
    if key in seen:
        raise PackageError(f"大小写不敏感的重名路径: {name!r}")
    seen.add(key)

    mode = (info.external_attr >> 16) & 0xFFFF
    if info.create_system == 3:
        if stat.S_ISLNK(mode):
            raise PackageError(f"不允许符号链接成员: {name!r}")
        if stat.S_IFMT(mode) not in {0, stat.S_IFREG}:
            raise PackageError(f"不支持的成员类型: {name!r}")
    if info.flag_bits & 0x1:
        raise PackageError(f"不允许加密成员: {name!r}")
    if info.compress_type not in ALLOWED_COMPRESSION:
        raise PackageError(f"不支持的压缩方式: {name!r}")


def _check_limits(members: list[zipfile.ZipInfo]) -> int:
    if len(members) > MAX_FILE_COUNT:
        raise PackageError(f"文件数超过上限 {MAX_FILE_COUNT}")
    unpacked = compressed = 0
    for info in members:
        if info.file_size > MAX_FILE_BYTES:
            raise PackageError(f"单文件超过上限: {info.filename!r}")
        unpacked += info.file_size
        compressed += info.compress_size
        if unpacked > MAX_UNPACKED_BYTES:
            raise PackageError("解压后总量超过上限")
        if info.file_size and info.file_size / max(info.compress_size, 1) > MAX_COMPRESSION_RATIO:
            raise PackageError(f"压缩比超过上限: {info.filename!r}")
    if unpacked and unpacked / max(compressed, 1) > MAX_COMPRESSION_RATIO:
        raise PackageError("整包压缩比超过上限")
    return unpacked


def _check_file_set(names: set[str]) -> list[str]:
    missing = REQUIRED_FILES - names
    if missing:
        raise PackageError("缺少必需文件: " + ", ".join(sorted(missing)))
    gallery = []
    for name in names:
        if name in REQUIRED_FILES:
            continue
        if name.startswith(GALLERY_PREFIX):
            gallery.append(name)
            continue
        raise PackageError(f"包内出现多余文件: {name!r}")
    if len(gallery) > MAX_GALLERY_FILES:
        raise PackageError(f"图库张数超过上限 {MAX_GALLERY_FILES}")
    return sorted(gallery)


# ---- manifest ------------------------------------------------------------
def _no_duplicate_keys(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise PackageError(f"manifest 出现重复字段: {key!r}")
        seen[key] = value
    return seen


def _localized(value, field: str) -> None:
    if not isinstance(value, dict) or set(value) != {"zh-CN", "en-US"}:
        raise PackageError(f"manifest.{field} 必须是 zh-CN/en-US 双语对象")
    for locale, text in value.items():
        if not isinstance(text, str) or not (1 <= len(text.strip()) <= 200):
            raise PackageError(f"manifest.{field}.{locale} 长度必须是 1–200")


def check_manifest(raw: bytes) -> dict:
    if len(raw) > MAX_MANIFEST_BYTES:
        raise PackageError("manifest.json 超过 256 KiB")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise PackageError("manifest.json 必须是 UTF-8") from exc
    if "\x00" in text:
        raise PackageError("manifest.json 不能包含 NUL")
    try:
        data = json.loads(text, object_pairs_hook=_no_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise PackageError(f"manifest.json 不是合法 JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise PackageError("manifest.json 根节点必须是对象")

    allowed = {
        "manifestVersion", "id", "version", "name", "description", "publisher",
        "workshopApi", "luminaVersion", "entrypoints", "permissions",
    }
    extra = set(data) - allowed
    if extra:
        raise PackageError("manifest 含未知字段: " + ", ".join(sorted(extra)))
    missing = allowed - set(data)
    if missing:
        raise PackageError("manifest 缺字段: " + ", ".join(sorted(missing)))

    if data["manifestVersion"] != 1:
        raise PackageError("manifestVersion 必须是 1")
    mid = data["id"]
    if not isinstance(mid, str) or not MODULE_ID.fullmatch(mid) or not (3 <= len(mid) <= 128):
        raise PackageError("manifest.id 必须是小写反向域名风格（3–128）")
    version = data["version"]
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise PackageError("manifest.version 必须是严格 SemVer")
    _localized(data["name"], "name")
    _localized(data["description"], "description")
    publisher = data["publisher"]
    if not isinstance(publisher, str) or not (1 <= len(publisher.strip()) <= 200):
        raise PackageError("manifest.publisher 必须是 1–200 的非空文本")

    api = data["workshopApi"]
    if not isinstance(api, dict) or set(api) != {"min", "maxExclusive"}:
        raise PackageError("manifest.workshopApi 必须只有 min/maxExclusive")
    for key in ("min", "maxExclusive"):
        if not SEMVER.fullmatch(str(api[key])):
            raise PackageError(f"workshopApi.{key} 必须是 SemVer")
    if not _semver_lt(api["min"], api["maxExclusive"]):
        raise PackageError("workshopApi.maxExclusive 必须大于 min")

    lum = data["luminaVersion"]
    if not isinstance(lum, dict) or set(lum) != {"min"} or not SEMVER.fullmatch(str(lum["min"])):
        raise PackageError("manifest.luminaVersion 必须只有 min 且为 SemVer")

    entry = data["entrypoints"]
    if not isinstance(entry, dict) or entry.get("ui") != "ui/index.html":
        raise PackageError("entrypoints.ui 必须精确等于 ui/index.html")

    perms = data["permissions"]
    if not isinstance(perms, list) or len(perms) > 32:
        raise PackageError("permissions 必须是数组且不超过 32 项")
    names = []
    for item in perms:
        if not isinstance(item, dict) or set(item) != {"name", "reason"}:
            raise PackageError("每个权限只允许 name/reason 两个字段")
        if item["name"] not in PERMISSIONS:
            raise PackageError(f"未知权限: {item['name']!r}")
        reason = item["reason"]
        if not isinstance(reason, str) or not (1 <= len(reason.strip()) <= 500):
            raise PackageError("权限理由必须是 1–500 的非空文本")
        names.append(item["name"])
    if len(names) != len(set(names)):
        raise PackageError("permissions 中存在重复权限")
    return data


def _semver_lt(a: str, b: str) -> bool:
    def key(v: str):
        core, _, pre = v.split("+", 1)[0].partition("-")
        major, minor, patch = (int(x) for x in core.split("."))
        ids = tuple((0, int(x)) if x.isdigit() else (1, x) for x in pre.split(".")) if pre else ()
        return major, minor, patch, (1 if not pre else 0), ids

    return key(a) < key(b)


# ---- 运行时 HTML ---------------------------------------------------------
def _is_inline(value: str) -> bool:
    v = value.strip().strip("\"'").strip()
    low = v.casefold()
    return (not v) or v.startswith("#") or low.startswith(("data:", "blob:")) or low == "about:blank"


class _HtmlCheck(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_style = False

    @staticmethod
    def _css(value: str) -> None:
        for match in CSS_URL.finditer(value):
            if not _is_inline(match.group(1)):
                raise PackageError("运行时 HTML 的 CSS 只能使用内联资源")

    def _attrs(self, attrs):
        for name, value in attrs:
            if value is None:
                continue
            key = name.casefold()
            if key in {"src", "href"} and not _is_inline(value):
                raise PackageError("运行时 HTML 不得引用包内文件或网络资源")
            if key == "style":
                self._css(value)

    def handle_starttag(self, tag, attrs):
        self._attrs(attrs)
        if tag.casefold() == "style":
            self.in_style = True

    def handle_startendtag(self, tag, attrs):
        self._attrs(attrs)

    def handle_endtag(self, tag):
        if tag.casefold() == "style":
            self.in_style = False

    def handle_data(self, data):
        if self.in_style:
            self._css(data)


def check_runtime_html(raw: bytes) -> None:
    try:
        html = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise PackageError("ui/index.html 必须是 UTF-8") from exc
    if "\x00" in html:
        raise PackageError("ui/index.html 不能包含 NUL")
    head, script = HEAD_TAG.search(html), SCRIPT_TAG.search(html)
    if head is None or (script is not None and script.start() < head.start()):
        raise PackageError("ui/index.html 必须把 <head> 放在第一个 <script> 之前")
    if DYNAMIC_CODE.search(html):
        raise PackageError("ui/index.html 不得使用 eval 或动态 import")
    parser = _HtmlCheck()
    parser.feed(html)
    parser.close()


# ---- 图像 ---------------------------------------------------------------
def _png_size(raw: bytes) -> tuple[int, int] | None:
    if not raw.startswith(PNG_SIGNATURE) or len(raw) < 33 or raw[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", raw[16:24])


def _check_dims(width: int, height: int, max_pixels: int, label: str) -> None:
    if width <= 0 or height <= 0 or width > MAX_IMAGE_EDGE or height > MAX_IMAGE_EDGE:
        raise PackageError(f"{label} 尺寸超出上限")
    if width * height > max_pixels:
        raise PackageError(f"{label} 像素数超出上限")


def check_image(name: str, raw: bytes, *, icon: bool) -> None:
    suffix = Path(name).suffix.casefold()
    if icon:
        if suffix != ".png" or not raw.startswith(PNG_SIGNATURE):
            raise PackageError("图标必须是静态 PNG")
        if len(raw) > MAX_ICON_BYTES:
            raise PackageError("图标超过 2 MiB")
        expected, max_px, label = "PNG", MAX_ICON_PIXELS, "图标"
    else:
        if suffix not in GALLERY_SUFFIXES:
            raise PackageError("图库只允许 PNG/JPEG/WebP")
        ok = (
            (suffix == ".png" and raw.startswith(PNG_SIGNATURE))
            or (suffix in {".jpg", ".jpeg"} and raw.startswith(b"\xff\xd8\xff"))
            or (suffix == ".webp" and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP")
        )
        if not ok:
            raise PackageError(f"图库文件头与扩展名不符: {name!r}")
        if len(raw) > MAX_GALLERY_FILE_BYTES:
            raise PackageError(f"图库图片超过 5 MiB: {name!r}")
        expected = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}[suffix]
        max_px, label = MAX_GALLERY_PIXELS, "图库图片"

    size = _png_size(raw)
    if size:
        _check_dims(size[0], size[1], max_px, label)
    low = raw.lower()
    if b"actl" in low or (suffix == ".webp" and b"ANIM" in raw[:64]):
        raise PackageError(f"{label} 不能是动图")
    for marker in SUSPICIOUS:
        if marker in low:
            raise PackageError(f"{label} 含外部引用标记: {marker!r}")

    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != expected:
                raise PackageError(f"{label} 实际格式与路径不符")
            _check_dims(image.size[0], image.size[1], max_px, label)
            if getattr(image, "n_frames", 1) != 1:
                raise PackageError(f"{label} 不能是动图")
            for key in ("exif", "xmp", "XML:com.adobe.xmp", "icc_profile", "comment"):
                if key in image.info:
                    raise PackageError(f"{label} 含不支持的元数据: {key}")
            image.verify()
    except PackageError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise PackageError(f"{label} 已损坏或无法解码") from exc


# ---- 校验 / 打包 --------------------------------------------------------
def validate_package(path: Path) -> dict:
    if path.suffix != ".lumina-workshop":
        raise PackageError("包扩展名必须是 .lumina-workshop")
    if not path.is_file():
        raise PackageError("包不是普通文件")
    total = path.stat().st_size
    if total > MAX_PACKAGE_BYTES:
        raise PackageError("压缩包超过 100 MiB")

    with zipfile.ZipFile(path) as package:
        infos = package.infolist()
        seen: set[str] = set()
        by_name: dict[str, zipfile.ZipInfo] = {}
        for info in infos:
            _check_member(info, seen)
            by_name[info.filename] = info
        unpacked = _check_limits(infos)
        gallery = _check_file_set(set(by_name))

        payload = {name: package.read(name) for name in by_name}
        checks = (
            ("manifest.json", MAX_MANIFEST_BYTES),
            ("assets/icon.png", MAX_ICON_BYTES),
            ("README.md", MAX_TEXT_DOCUMENT_BYTES),
            ("LICENSE", MAX_TEXT_DOCUMENT_BYTES),
        )
        for name, cap in checks:
            if len(payload[name]) > cap:
                raise PackageError(f"{name} 超过大小上限")

    manifest = check_manifest(payload["manifest.json"])
    check_runtime_html(payload["ui/index.html"])
    check_image("assets/icon.png", payload["assets/icon.png"], icon=True)
    for name in gallery:
        check_image(name, payload[name], icon=False)
    for name in ("README.md", "LICENSE"):
        try:
            payload[name].decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise PackageError(f"{name} 必须是 UTF-8") from exc

    return {
        "path": str(path),
        "bytes": total,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "unpacked_bytes": unpacked,
        "manifest_sha256": hashlib.sha256(payload["manifest.json"]).hexdigest(),
        "manifest": manifest,
        "files": sorted(by_name),
    }


def build(output_dir: Path) -> Path:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    asset = f"{manifest['id']}-{manifest['version']}.lumina-workshop"
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / asset

    # 只打包规范允许的文件；仓库里的 tools/、tests/、docs/ 不进包
    members = [
        ("manifest.json", ROOT / "manifest.json"),
        ("ui/index.html", ROOT / "ui" / "index.html"),
        ("assets/icon.png", ROOT / "assets" / "icon.png"),
        ("README.md", ROOT / "README.md"),
        ("LICENSE", ROOT / "LICENSE"),
    ]
    gallery_dir = ROOT / "assets" / "gallery"
    if gallery_dir.is_dir():
        for item in sorted(gallery_dir.iterdir()):
            if item.is_file():
                members.append((f"assets/gallery/{item.name}", item))

    # 确定性打包：固定时间戳、固定权限、固定顺序，便于两次构建字节一致
    with zipfile.ZipFile(target, "w") as package:
        for arcname, source in sorted(members):
            info = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            package.writestr(info, source.read_bytes(), compresslevel=9)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="构建并校验 .lumina-workshop 包")
    parser.add_argument("--out", default="dist", type=Path, help="输出目录（默认 dist/）")
    parser.add_argument("--check", type=Path, help="只校验已有的包")
    args = parser.parse_args(argv)

    try:
        if args.check:
            report = validate_package(args.check)
        else:
            target = build(args.out)
            report = validate_package(target)
    except PackageError as exc:
        print(f"[fail] {exc}")
        return 1

    m = report["manifest"]
    print(f"[ok] {report['path']}")
    print(f"     id={m['id']} version={m['version']}")
    print(f"     {report['bytes']} 字节 / 解压 {report['unpacked_bytes']} 字节 / {len(report['files'])} 个文件")
    print(f"     sha256={report['sha256']}")
    print(f"     manifestSha256={report['manifest_sha256']}")
    print("     files=" + ", ".join(report["files"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
