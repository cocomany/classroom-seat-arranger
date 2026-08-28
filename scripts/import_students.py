#!/usr/bin/env python3
"""将常见学生名单文件标准化为座位编排请求。"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

from cli_zh import ChineseArgumentParser
from xml.etree import ElementTree as ET

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


HEADER_PATTERNS = {
    "name": re.compile(r"姓名|名字|学生|name", re.I),
    "gender": re.compile(r"性别|gender|sex", re.I),
    "heightCm": re.compile(r"身高|height", re.I),
    "vision": re.compile(r"视力|近视|vision", re.I),
    "score": re.compile(r"成绩|分数|score|grade", re.I),
    "discipline": re.compile(r"纪律|课堂|表现|discipline|behavior", re.I),
    "role": re.compile(r"职务|职位|班干部|role|position", re.I),
    "tags": re.compile(r"标签|备注|特点|tags?|notes?", re.I),
}


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法识别文件编码：{path.name}")


def column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference.upper())
    value = 0
    for letter in letters.group(0) if letters else "A":
        value = value * 26 + ord(letter) - 64
    return value - 1


def xlsx_rows(path: Path) -> list[list[Any]]:
    namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", namespace):
                shared.append("".join(node.text or "" for node in item.iter() if node.tag.endswith("}t")))
        sheets = sorted(name for name in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name))
        if not sheets:
            raise ValueError("Excel 中没有可读取的工作表。")
        root = ET.fromstring(archive.read(sheets[0]))
        output: list[list[Any]] = []
        for row in root.findall(".//m:sheetData/m:row", namespace):
            values: dict[int, Any] = {}
            for cell in row.findall("m:c", namespace):
                index = column_index(cell.attrib.get("r", "A1"))
                cell_type = cell.attrib.get("t")
                value_node = cell.find("m:v", namespace)
                if cell_type == "inlineStr":
                    value = "".join(node.text or "" for node in cell.iter() if node.tag.endswith("}t"))
                elif value_node is None:
                    value = ""
                elif cell_type == "s":
                    value = shared[int(value_node.text or 0)]
                else:
                    value = value_node.text or ""
                values[index] = value
            if values:
                width = max(values) + 1
                output.append([values.get(index, "") for index in range(width)])
        return output


def docx_rows(path: Path) -> list[list[Any]]:
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    rows: list[list[Any]] = []
    for row in root.findall(".//w:tr", namespace):
        cells = []
        for cell in row.findall("w:tc", namespace):
            cells.append("".join(node.text or "" for node in cell.iter() if node.tag.endswith("}t")).strip())
        if any(cells):
            rows.append(cells)
    if rows:
        return rows
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        text = "".join(node.text or "" for node in paragraph.iter() if node.tag.endswith("}t")).strip()
        if text:
            paragraphs.append([text])
    return paragraphs


def delimited_rows(path: Path) -> list[list[Any]]:
    text = read_text(path)
    if path.suffix.lower() == ".tsv":
        return list(csv.reader(text.splitlines(), delimiter="\t"))
    if path.suffix.lower() == ".csv":
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",，\t;")
        except csv.Error:
            dialect = csv.excel
        return list(csv.reader(text.splitlines(), dialect))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    if any(re.search(r"[,，\t;；]", line) for line in lines):
        return [re.split(r"[,，\t;；]", line) for line in lines]
    if len(lines) == 1:
        names = [name for name in re.split(r"[、,，;；\s]+", lines[0]) if name]
        return [[name] for name in names]
    return [[line] for line in lines]


def json_rows(path: Path) -> tuple[list[list[Any]] | None, dict[str, Any] | None]:
    data = json.loads(read_text(path))
    if isinstance(data, dict) and isinstance(data.get("students"), list):
        return None, data
    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        headers = list(dict.fromkeys(key for item in data for key in item))
        return [headers] + [[item.get(key, "") for key in headers] for item in data], None
    if isinstance(data, list) and all(isinstance(item, list) for item in data):
        return data, None
    raise ValueError("JSON 必须是学生对象数组、二维表格，或包含 students 的请求对象。")


def number(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def normalize_gender(value: Any) -> str:
    text = str(value or "").strip().lower()
    if re.search(r"女|female|\bf\b", text):
        return "female"
    if re.search(r"男|male|\bm\b", text):
        return "male"
    return "unknown"


def normalize_vision(value: Any) -> str:
    text = str(value or "").strip().lower()
    if re.search(r"重|severe|高度", text):
        return "severe"
    if re.search(r"中|moderate", text):
        return "moderate"
    if re.search(r"轻|mild|近视", text):
        return "mild"
    if re.search(r"正常|normal|无", text):
        return "normal"
    return "unknown"


def normalize_discipline(value: Any) -> str:
    text = str(value or "").strip().lower()
    if re.search(r"活跃|讲话|好动|纪律差|talkative|active", text):
        return "talkative"
    if re.search(r"安静|quiet", text):
        return "quiet"
    if re.search(r"正常|一般|normal", text):
        return "normal"
    return "unknown"


def score_value(value: Any) -> float | None:
    direct = number(value)
    if direct is not None:
        return direct
    text = str(value or "")
    if re.search(r"优秀|优", text):
        return 92
    if re.search(r"良好|良", text):
        return 82
    if re.search(r"中等|一般|中", text):
        return 72
    if re.search(r"待提高|较弱|差", text):
        return 62
    return None


def normalize_rows(rows: list[list[Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    rows = [[str(cell or "").strip() for cell in row] for row in rows if any(str(cell or "").strip() for cell in row)]
    if not rows:
        return [], ["名单为空。"]
    header = rows[0]
    has_header = any(pattern.search(cell) for cell in header for pattern in HEADER_PATTERNS.values())
    indexes: dict[str, int] = {}
    if has_header:
        for field, pattern in HEADER_PATTERNS.items():
            indexes[field] = next((index for index, cell in enumerate(header) if pattern.search(cell)), -1)
        data_rows = rows[1:]
    else:
        indexes = {"name": 0, "gender": 1, "heightCm": 2, "vision": 3, "score": 4, "discipline": 5, "role": 6, "tags": 7}
        data_rows = rows

    def cell(row: list[str], field: str) -> str:
        index = indexes.get(field, -1)
        return row[index].strip() if 0 <= index < len(row) else ""

    students: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen_names: dict[str, int] = {}
    for row in data_rows:
        name = cell(row, "name")
        if not name:
            continue
        seen_names[name] = seen_names.get(name, 0) + 1
        student: dict[str, Any] = {
            "id": f"s{len(students) + 1:03d}",
            "name": name,
            "gender": normalize_gender(cell(row, "gender")),
            "vision": normalize_vision(cell(row, "vision")),
            "discipline": normalize_discipline(cell(row, "discipline")),
        }
        height = number(cell(row, "heightCm"))
        score = score_value(cell(row, "score"))
        role = cell(row, "role")
        tags = [tag.strip() for tag in re.split(r"[、,，;；|]", cell(row, "tags")) if tag.strip() and tag.strip() != "无"]
        if height and height > 0:
            student["heightCm"] = height
        if score is not None:
            student["score"] = score
        if role and role != "无":
            student["role"] = role
        if tags:
            student["tags"] = tags
        students.append(student)
    duplicates = [name for name, count in seen_names.items() if count > 1]
    if duplicates:
        warnings.append(f"存在同名学生：{'、'.join(duplicates)}；请核对并保留不同 ID。")
    return students, warnings


def default_request(class_name: str, students: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "className": class_name,
        "students": students,
        "layout": {
            "rows": "auto",
            "cols": 8,
            "aislesAfter": [2, 4, 6],
            "disabledSeatIds": [],
            "podiumSideSeats": False,
            "trimExtraSeats": True,
        },
        "rules": [],
        "history": [],
        "options": {"candidateCount": 3, "seed": 20260824, "considerHistory": False},
        "warnings": warnings,
    }


def main() -> int:
    parser = ChineseArgumentParser(description="将常见学生名单归一化为座位编排请求 JSON。")
    parser.add_argument("source", type=Path, help=".xlsx/.docx/.csv/.tsv/.txt/.json 名单")
    parser.add_argument("--class-name", default="未命名班级", help="班级名称")
    parser.add_argument("--output", "-o", type=Path, required=True, help="输出 JSON")
    args = parser.parse_args()

    try:
        suffix = args.source.suffix.lower()
        request: dict[str, Any] | None = None
        if suffix == ".xlsx":
            rows = xlsx_rows(args.source)
        elif suffix == ".docx":
            rows = docx_rows(args.source)
        elif suffix == ".json":
            rows, request = json_rows(args.source)
        elif suffix in {".csv", ".tsv", ".txt"}:
            rows = delimited_rows(args.source)
        else:
            raise ValueError("不支持该文件类型。图片和 PDF 请先用 Agent 的多模态能力提取。")

        if request is None:
            students, warnings = normalize_rows(rows or [])
            request = default_request(args.class_name, students, warnings)
        else:
            request.setdefault("schemaVersion", 1)
            request.setdefault("className", args.class_name)
            request.setdefault("layout", default_request(args.class_name, [], [])["layout"])
            request.setdefault("rules", [])
            request.setdefault("history", [])
            request.setdefault("options", default_request(args.class_name, [], [])["options"])
        if not request.get("students"):
            raise ValueError("没有识别到学生姓名。")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"已导入 {len(request['students'])} 名学生 → {args.output}")
        for warning in request.get("warnings", []):
            print(f"提醒：{warning}", file=sys.stderr)
        return 0
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile, ET.ParseError) as error:
        print(f"导入失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
