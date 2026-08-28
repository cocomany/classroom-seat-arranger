#!/usr/bin/env python3
"""校验并生成兼容 SkillHub 的 ZIP 技能包。"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import zipfile
from pathlib import Path

from cli_zh import ChineseArgumentParser


SKILL_ROOT = Path(__file__).resolve().parent.parent
MAX_FILES = 200
MAX_BYTES = 10 * 1024 * 1024
BLOCKED_SUFFIXES = {
    ".exe", ".dll", ".so", ".dylib", ".bin", ".dat", ".zip", ".tar", ".gz", ".bz2", ".rar", ".7z",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".mp3", ".mp4", ".avi", ".mov", ".wav",
    ".flac", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".class", ".jar", ".war",
    ".o", ".a", ".lib", ".pyc", ".pyo", ".wasm", ".woff", ".woff2", ".ttf", ".otf", ".eot",
}
FONT_SUFFIXES = {".woff", ".woff2", ".ttf", ".otf", ".eot"}
FONT_MIME_TYPES = {
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".eot": "application/vnd.ms-fontobject",
}
IGNORED_PARTS = {".git", "__pycache__", "outputs", "output", ".DS_Store", ".gitignore"}
REQUIRED_FRONTMATTER = ("slug", "version", "displayName")


def package_files() -> list[Path]:
    files = []
    for path in SKILL_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(SKILL_ROOT)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if path.name.startswith(".env"):
            continue
        if path.suffix.lower() in FONT_SUFFIXES:
            continue
        files.append(path)
    return sorted(files)


def inline_font_css(path: Path) -> bytes:
    """把 CSS 引用的本地字体转换为标准 data URI，避开平台禁止的字体文件扩展名。"""
    css = path.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        raw = match.group(1).strip().strip("'\"")
        if raw.startswith(("data:", "http://", "https://")):
            return match.group(0)
        resource = (path.parent / raw).resolve()
        suffix = resource.suffix.lower()
        if suffix not in FONT_SUFFIXES:
            return match.group(0)
        if not resource.is_file() or SKILL_ROOT not in resource.parents:
            raise ValueError(f"字体资源不存在或超出技能目录：{raw}")
        encoded = base64.b64encode(resource.read_bytes()).decode("ascii")
        return f"url('data:{FONT_MIME_TYPES[suffix]};base64,{encoded}')"

    inlined = re.sub(r"url\(([^)]+)\)", replace, css)
    unresolved = re.findall(r"url\(([^)]*\.(?:woff2?|ttf|otf|eot)[^)]*)\)", inlined, re.IGNORECASE)
    if unresolved:
        raise ValueError(f"CSS 中仍有未内嵌字体：{path.relative_to(SKILL_ROOT)}")
    return inlined.encode("utf-8")


def parse_frontmatter_text(text: str) -> dict[str, str]:
    match = re.match(r"^---\s*\n([\s\S]*?)\n---", text)
    if not match:
        return {}
    values: dict[str, str] = {}
    for key in REQUIRED_FRONTMATTER:
        item = re.search(rf"^{re.escape(key)}\s*:\s*(.+)$", match.group(1), re.MULTILINE)
        if item:
            values[key] = item.group(1).strip().strip("\"'")
    return values


def manifest_value(text: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}\s*:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip().strip("\"'") if match else ""


def manifest_list(text: str, key: str) -> list[str]:
    block = re.search(rf"^{re.escape(key)}\s*:\s*\n((?:\s+-\s+.*\n?)*)", text, re.MULTILINE)
    if not block:
        return []
    return [item.strip().strip("\"'") for item in re.findall(r"^\s+-\s+(.+)$", block.group(1), re.MULTILINE)]


def skillhub_skill_md() -> tuple[str, dict[str, str]]:
    source_path = SKILL_ROOT / "SKILL.md"
    manifest_path = SKILL_ROOT / "manifest.yaml"
    if not source_path.is_file() or not manifest_path.is_file():
        return "", {}
    source = source_path.read_text(encoding="utf-8-sig")
    manifest = manifest_path.read_text(encoding="utf-8-sig")
    values = {key: manifest_value(manifest, key) for key in REQUIRED_FRONTMATTER}
    summary = manifest_value(manifest, "summary")
    homepage = manifest_value(manifest, "homepage")
    repository = manifest_value(manifest, "repository")
    author = manifest_value(manifest, "author")
    tags = manifest_list(manifest, "tags")
    injected = (
        f"slug: {values['slug']}\n"
        f"displayName: {values['displayName']}\n"
        f"version: {values['version']}\n"
        f"summary: {summary}\n"
        f"tags: {json.dumps(tags, ensure_ascii=False)}\n"
        f"author: {author}\n"
        f"homepage: {homepage}\n"
        f"repository: {repository}\n"
    )
    if not source.startswith("---\n"):
        return "", values
    return "---\n" + injected + source[len("---\n"):], values


def generated_overrides(files: list[Path], generated_skill_md: str) -> dict[str, bytes]:
    overrides = {"SKILL.md": generated_skill_md.encode("utf-8")}
    for path in files:
        relative = path.relative_to(SKILL_ROOT).as_posix()
        if relative.startswith("assets/fonts/") and path.suffix.lower() == ".css":
            overrides[relative] = inline_font_css(path)
    return overrides


def validate(files: list[Path], overrides: dict[str, bytes], frontmatter: dict[str, str]) -> int:
    errors = []
    skill_md = SKILL_ROOT / "SKILL.md"
    if skill_md not in files:
        errors.append("根目录必须包含 SKILL.md")
    elif not overrides.get("SKILL.md"):
        errors.append("无法生成 SkillHub 版 SKILL.md；请检查 manifest.yaml")
    for field in REQUIRED_FRONTMATTER:
        if not frontmatter.get(field):
            errors.append(f"manifest.yaml 缺少 {field}")
    if frontmatter.get("slug") and not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,126}[a-z0-9]", frontmatter["slug"]):
        errors.append("slug 必须是 2-128 位 kebab-case")
    if frontmatter.get("version") and not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?", frontmatter["version"]):
        errors.append("version 必须是合法 SemVer")
    if len(files) > MAX_FILES:
        errors.append(f"文件数 {len(files)} 超过 SkillHub 上限 {MAX_FILES}")
    total = sum(
        len(overrides.get(path.relative_to(SKILL_ROOT).as_posix(), path.read_bytes()))
        for path in files
    )
    if total > MAX_BYTES:
        errors.append(f"总大小 {total / 1024 / 1024:.2f} MiB 超过 SkillHub 上限 10 MiB")
    blocked = [str(path.relative_to(SKILL_ROOT)) for path in files if path.suffix.lower() in BLOCKED_SUFFIXES]
    if blocked:
        errors.append("包含 SkillHub 禁止的二进制文件：" + ", ".join(blocked[:8]))
    if errors:
        raise ValueError("\n".join(errors))
    return total


def main() -> int:
    parser = ChineseArgumentParser(description="校验并生成 SkillHub 可上传 ZIP。")
    parser.add_argument("--output", "-o", type=Path, required=True, help="ZIP 输出路径，必须位于技能根目录之外")
    args = parser.parse_args()
    try:
        output = args.output.resolve()
        if output == SKILL_ROOT or SKILL_ROOT in output.parents:
            raise ValueError("输出 ZIP 必须放在 Skill 根目录之外，避免被收入自身或 GitHub 导入扫描")
        files = package_files()
        generated_skill_md, frontmatter = skillhub_skill_md()
        overrides = generated_overrides(files, generated_skill_md)
        total = validate(files, overrides, frontmatter)
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in files:
                relative = path.relative_to(SKILL_ROOT).as_posix()
                if relative in overrides:
                    archive.writestr(relative, overrides[relative])
                else:
                    archive.write(path, relative)
        print(f"SkillHub 技能包校验通过：{frontmatter['slug']}@{frontmatter['version']} · {len(files)} 个文件 · {total / 1024 / 1024:.2f} MiB")
        print(f"ZIP 文件：{output} · {output.stat().st_size / 1024 / 1024:.2f} MiB")
        return 0
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"打包失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
