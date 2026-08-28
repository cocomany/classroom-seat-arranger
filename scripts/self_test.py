#!/usr/bin/env python3
"""Fast behavioral self-test for the packaged skill."""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path

from arrange_seats import solve
from import_students import docx_rows, normalize_rows, xlsx_rows
from render_board import capture_png, locate_chrome, render


SKILL_ROOT = Path(__file__).resolve().parent.parent
SAMPLE = SKILL_ROOT / "assets" / "examples" / "sample-request.json"


def make_tiny_xlsx(path: Path) -> None:
    content_types = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
</Types>'''
    worksheet = '''<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
<row r="1"><c r="A1" t="inlineStr"><is><t>姓名</t></is></c><c r="B1" t="inlineStr"><is><t>性别</t></is></c><c r="C1" t="inlineStr"><is><t>职务</t></is></c></row>
<row r="2"><c r="A2" t="inlineStr"><is><t>林晓</t></is></c><c r="B2" t="inlineStr"><is><t>女</t></is></c><c r="C2" t="inlineStr"><is><t>班长</t></is></c></row>
<row r="3"><c r="A3" t="inlineStr"><is><t>欧阳若曦</t></is></c><c r="B3" t="inlineStr"><is><t>男</t></is></c></row>
</sheetData></worksheet>'''
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)


def make_tiny_docx(path: Path) -> None:
    document = '''<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:tbl>
<w:tr><w:tc><w:p><w:r><w:t>姓名</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>性别</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p><w:r><w:t>苏禾</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>女</w:t></w:r></w:p></w:tc></w:tr>
</w:tbl></w:body></w:document>'''
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document)


def assert_candidate_integrity(result: dict) -> None:
    assert result["status"] == "ok", result.get("issues")
    assert len(result["candidates"]) == 3
    usable = {seat["id"] for seat in result["seats"] if seat["usable"]}
    student_ids = {student["id"] for student in result["students"]}
    for candidate in result["candidates"]:
        assigned = {student_id for seat_id, student_id in candidate["assignment"].items() if seat_id in usable and student_id}
        assert assigned == student_ids
        assert not candidate["hardViolations"]
        assert candidate["assignment"]["seat-0-0"] == "s001"


def main() -> int:
    parser = argparse.ArgumentParser(description="验证座位编排 Skill 的导入、求解、轮换和渲染。")
    parser.add_argument("--with-png", action="store_true", help="如果本机有 Chrome，再验证 PNG 截图")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="seat-skill-test-") as directory:
        temp = Path(directory)
        xlsx = temp / "roster.xlsx"
        make_tiny_xlsx(xlsx)
        students, warnings = normalize_rows(xlsx_rows(xlsx))
        assert not warnings
        assert [student["name"] for student in students] == ["林晓", "欧阳若曦"]
        assert students[0]["gender"] == "female" and students[0]["role"] == "班长"
        docx = temp / "roster.docx"
        make_tiny_docx(docx)
        word_students, word_warnings = normalize_rows(docx_rows(docx))
        assert not word_warnings and word_students[0]["name"] == "苏禾" and word_students[0]["gender"] == "female"

        request = json.loads(SAMPLE.read_text(encoding="utf-8"))
        request["layout"]["rows"] = 3
        first = solve(request)
        second = solve(request)
        assert_candidate_integrity(first)
        assert [candidate["assignment"] for candidate in first["candidates"]] == [candidate["assignment"] for candidate in second["candidates"]]

        large_request = deepcopy(request)
        large_request["students"] = []
        suffixes = ["甲", "乙", "丙"]
        for group, suffix in enumerate(suffixes):
            for source in request["students"]:
                student = deepcopy(source)
                student["id"] = f"g{group + 1}-{source['id']}"
                student["name"] = f"{source['name']}{suffix}"
                large_request["students"].append(student)
        large_request["layout"]["rows"] = "auto"
        large_request["rules"] = [{"id":"large-front","type":"front","level":"soft","weight":80,"studentIds":["g1-s001","g2-s001","g3-s001"],"rows":2,"label":"视力关注学生优先前排"}]
        large_request["options"]["candidateCount"] = 1
        large = solve(large_request)
        assert large["status"] == "ok"
        assert len(large["students"]) == 48 and large["layout"]["rows"] == 6 and large["layout"]["capacity"] == 48
        assert sum(student_id is not None for student_id in large["candidates"][0]["assignment"].values()) == 48

        minimal = {
            "className": "只含姓名的班级",
            "students": [{"id": f"m{index}", "name": name} for index, name in enumerate(["张三", "李四", "王小明", "赵六", "欧阳夏"], 1)],
            "layout": {"rows": "auto", "cols": 4, "trimExtraSeats": True},
            "rules": [],
            "options": {"candidateCount": 1, "seed": 7},
        }
        minimal_result = solve(minimal)
        assert minimal_result["status"] == "ok" and len(minimal_result["candidates"]) == 1
        assert minimal_result["layout"]["capacity"] == 5

        conflict = deepcopy(request)
        conflict["layout"]["disabledSeatIds"] = ["seat-0-0"]
        conflict_result = solve(conflict)
        assert conflict_result["status"] == "unsatisfiable" and not conflict_result["candidates"]
        assert any("同时被设为不可用" in issue for issue in conflict_result["issues"])

        rotation_request = deepcopy(request)
        rotation_request["history"] = [{
            "confirmedAt": first["generatedAt"],
            "rows": first["layout"]["rows"],
            "cols": first["layout"]["cols"],
            "assignment": first["candidates"][0]["assignment"],
            "students": [{"id": student["id"], "name": student["name"]} for student in first["students"]],
        }]
        rotation_request["options"]["considerHistory"] = True
        rotated = solve(rotation_request)
        assert_candidate_integrity(rotated)
        assert any(rule["type"] == "fairness" for rule in rotated["rules"])
        assert any(score["id"] == "default-fairness" for score in rotated["candidates"][0]["ruleScores"])

        document, height = render(rotated, 0, "ink", True, True, False)
        html_path = temp / "seat-chart.html"
        html_path.write_text(document, encoding="utf-8")
        assert "三年级二班座位表" in document
        assert "欧阳若曦" in document
        assert "theme-ink" in document
        assert 'aria-label="不可用座位"' in document
        if args.with_png:
            chrome = locate_chrome()
            assert chrome, "--with-png 要求本机已安装 Chrome、Chromium 或 Edge"
            png = temp / "seat-chart.png"
            capture_png(html_path, png, height)
            assert png.read_bytes()[1:4] == b"PNG" and png.stat().st_size > 100_000

    print("SELF_TEST_OK: import, deterministic solving, hard constraints, history fairness, and rendering passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
