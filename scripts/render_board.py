#!/usr/bin/env python3
"""Render a valid solver candidate as self-contained HTML and optional PNG."""

from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


SKILL_ROOT = Path(__file__).resolve().parent.parent
ASSETS = SKILL_ROOT / "assets"
TEMPLATE = ASSETS / "templates" / "seat-board.html"
THEMES = ASSETS / "templates" / "themes.json"


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def embed_css_file(path: Path) -> str:
    css = path.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        raw = match.group(1).strip().strip("'\"")
        resource = (path.parent / raw).resolve()
        return f"url('{data_uri(resource)}')" if resource.is_file() else match.group(0)

    return re.sub(r"url\(([^)]+)\)", replace, css)


def font_css(embed: bool) -> str:
    if not embed:
        return ""
    styles = []
    for family in ("noto-sans-sc", "noto-serif-sc", "ma-shan-zheng"):
        path = ASSETS / "fonts" / family / "index.css"
        if path.is_file():
            styles.append(embed_css_file(path))
    return "\n".join(styles)


def tag_values(student: dict[str, Any]) -> list[str]:
    tags = [str(item) for item in student.get("tags", []) if str(item).strip() and str(item).strip() != "无"]
    vision = {"mild": "轻度近视", "moderate": "中度近视", "severe": "重度近视"}.get(student.get("vision"))
    if vision:
        tags.append(vision)
    if student.get("discipline") == "talkative":
        tags.append("课堂活跃")
    if "score" in student:
        tags.append(f"成绩 {student['score']:g}")
    return list(dict.fromkeys(tags))[:3]


def seat_card(seat: dict[str, Any], student: dict[str, Any] | None, show_tags: bool, show_roles: bool, class_name: str = "") -> str:
    classes = f"seat-card {class_name}".strip()
    if not seat.get("usable", False):
        return f'<div class="{classes} disabled" aria-label="不可用座位"></div>'
    if not student:
        return f'<div class="{classes} empty" aria-label="空座位"></div>'
    gender = student.get("gender", "unknown")
    accent = {"male": "var(--male)", "female": "var(--female)", "unknown": "#819087"}[gender]
    gender_text = {"male": "男", "female": "女", "unknown": "·"}[gender]
    name = str(student["name"])
    name_class = "student-name name-4" if len(name) >= 4 else "student-name name-3" if len(name) == 3 else "student-name"
    role = html.escape(str(student.get("role", "")))
    role_html = f'<span class="role">{role}</span>' if show_roles and role and role != "无" else ""
    tags = tag_values(student) if show_tags else []
    tags_html = "".join(f"<span>{html.escape(tag)}</span>" for tag in tags)
    display_number = "讲台侧" if seat.get("zone") == "podium" else f"{seat['row'] + 1}-{seat['col'] + 1}"
    return (
        f'<article class="{classes}" style="--student-accent:{accent}">'
        f'<div class="student-main"><div class="student-line"><strong class="{name_class}">{html.escape(name)}</strong>'
        f'<span class="gender" title="{gender_text}">{gender_text}</span></div>{role_html}</div>'
        f'<div class="student-tags">{tags_html}</div><span class="seat-number">{display_number}</span></article>'
    )


def grid_columns(cols: int, aisles: list[int]) -> str:
    parts = []
    for col in range(cols):
        parts.append("156px")
        if col < cols - 1:
            parts.append("22px" if col + 1 in aisles else "7px")
    return " ".join(parts)


def locate_chrome() -> str | None:
    candidates = [
        shutil.which(name) for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "msedge")
    ]
    if os.name == "nt":
        for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
            if base:
                candidates.extend([
                    str(Path(base) / "Google/Chrome/Application/chrome.exe"),
                    str(Path(base) / "Microsoft/Edge/Application/msedge.exe"),
                ])
    elif sys.platform == "darwin":
        candidates.extend([
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ])
    return next((value for value in candidates if value and Path(value).is_file()), None)


def capture_png(html_path: Path, png_path: Path, height: int) -> None:
    chrome = locate_chrome()
    if not chrome:
        raise RuntimeError("未找到 Chrome、Chromium 或 Edge；HTML 已生成，可用 Agent 的浏览器截图能力导出。")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        "--virtual-time-budget=1800",
        "--force-device-scale-factor=1",
        f"--window-size=1600,{height + 52}",
        f"--screenshot={png_path.resolve()}",
        html_path.resolve().as_uri(),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=45, check=False)
    if result.returncode != 0 or not png_path.is_file():
        raise RuntimeError((result.stderr or result.stdout or "浏览器截图失败").strip())


def render(result: dict[str, Any], candidate_index: int, theme: str, show_tags: bool, show_roles: bool, embed_fonts: bool) -> tuple[str, int]:
    if result.get("status") != "ok":
        raise ValueError("结果不是可用方案，不能渲染。")
    candidates = result.get("candidates", [])
    if not 0 <= candidate_index < len(candidates):
        raise ValueError(f"方案序号超出范围：可选 0–{len(candidates) - 1}。")
    theme_config = json.loads(THEMES.read_text(encoding="utf-8"))
    if theme not in theme_config:
        raise ValueError(f"未知主题：{theme}。")
    candidate = candidates[candidate_index]
    layout = result["layout"]
    seats = result["seats"]
    students = {student["id"]: student for student in result["students"]}
    assignment = candidate["assignment"]
    by_seat = {seat["id"]: seat for seat in seats}
    rows_html = []
    for row in range(layout["rows"]):
        cells = []
        for col in range(layout["cols"]):
            seat = by_seat[f"seat-{row}-{col}"]
            student = students.get(assignment.get(seat["id"]))
            cells.append(seat_card(seat, student, show_tags, show_roles))
            if col < layout["cols"] - 1:
                cells.append(f'<div class="gap {"aisle" if col + 1 in layout["aislesAfter"] else "seam"}" aria-hidden="true"></div>')
        rows_html.append(f'<div class="seat-row">{"".join(cells)}</div>')
    podium_left = ""
    podium_right = ""
    if layout.get("podiumSideSeats"):
        for seat_id, side in (("podium-left", "left"), ("podium-right", "right")):
            seat = by_seat[seat_id]
            card = seat_card(seat, students.get(assignment.get(seat_id)), show_tags, show_roles, "side-seat")
            if side == "left":
                podium_left = card
            else:
                podium_right = card
    overlay_path = ASSETS / "themes" / theme_config[theme]["overlay"]
    board_height = max(720, 430 + int(layout["rows"]) * 112)
    generated = result.get("generatedAt", "")
    try:
        date_text = datetime.fromisoformat(generated.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        date_text = datetime.now().strftime("%Y-%m-%d")
    replacements = {
        "{{DOCUMENT_TITLE}}": html.escape(f"{result['className']}座位表"),
        "{{FONT_CSS}}": font_css(embed_fonts),
        "{{BOARD_HEIGHT}}": str(board_height),
        "{{GRID_COLUMNS}}": grid_columns(layout["cols"], layout["aislesAfter"]),
        "{{OVERLAY_DATA}}": data_uri(overlay_path),
        "{{THEME}}": theme,
        "{{CLASS_NAME}}": html.escape(str(result["className"])),
        "{{META}}": html.escape(f"{date_text} · {len(result['students'])} 人"),
        "{{PODIUM_LEFT}}": podium_left,
        "{{PODIUM_RIGHT}}": podium_right,
        "{{ROWS_HTML}}": "".join(rows_html),
        "{{SUMMARY}}": html.escape(str(candidate.get("summary", ""))),
    }
    document = TEMPLATE.read_text(encoding="utf-8")
    for key, value in replacements.items():
        document = document.replace(key, value)
    return document, board_height


def main() -> int:
    parser = argparse.ArgumentParser(description="将有效座位方案渲染为离线 HTML 和可选 PNG。")
    parser.add_argument("result", type=Path, help="arrange_seats.py 结果 JSON")
    parser.add_argument("--candidate", type=int, default=0, help="方案序号，从 0 开始")
    parser.add_argument("--theme", choices=["campus", "sports", "ink", "space"], default="campus")
    parser.add_argument("--output", "-o", type=Path, required=True, help="输出 HTML")
    parser.add_argument("--png", type=Path, help="可选 PNG 输出")
    parser.add_argument("--hide-tags", action="store_true")
    parser.add_argument("--hide-roles", action="store_true")
    parser.add_argument("--no-embed-fonts", action="store_true")
    args = parser.parse_args()
    try:
        result = json.loads(args.result.read_text(encoding="utf-8-sig"))
        document, height = render(result, args.candidate, args.theme, not args.hide_tags, not args.hide_roles, not args.no_embed_fonts)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(document, encoding="utf-8")
        print(f"已生成座位表 HTML → {args.output}")
        if args.png:
            capture_png(args.output, args.png, height)
            print(f"已生成座位表 PNG → {args.png}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"渲染失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
