#!/usr/bin/env python3
"""Deterministic constraint solver for classroom seat arrangements."""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


SUPPORTED_RULES = {"front", "avoid", "fixed", "height", "discipline", "score", "gender", "fairness"}
PROFILES = [
    ("综合平衡", "兼顾视力、身高、课堂秩序与同桌搭配", {}),
    ("学习搭配", "更看重成绩互补、身高顺序与同桌关系", {"score": 1.9, "height": 1.45, "gender": 1.35}),
    ("轮换优先", "更看重历史区域轮换、减少重复同桌与课堂秩序", {"fairness": 2.2, "discipline": 1.55}),
]


def as_number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def seat_row_from_id(seat_id: str) -> int | None:
    parts = seat_id.split("-")
    if len(parts) == 3 and parts[0] == "seat" and parts[1].isdigit():
        return int(parts[1])
    if seat_id.startswith("podium-"):
        return -1
    return None


def seat_col_from_id(seat_id: str) -> int | None:
    parts = seat_id.split("-")
    return int(parts[2]) if len(parts) == 3 and parts[0] == "seat" and parts[2].isdigit() else None


def default_aisles(cols: int) -> list[int]:
    return [value for value in range(2, cols, 2)]


def normalize_students(raw_students: Any) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(raw_students, list):
        return [], ["students 必须是数组。"]
    students: list[dict[str, Any]] = []
    issues: list[str] = []
    ids: set[str] = set()
    names: dict[str, int] = {}
    for index, raw in enumerate(raw_students):
        if not isinstance(raw, dict):
            issues.append(f"第 {index + 1} 条学生记录不是对象。")
            continue
        name = str(raw.get("name", "")).strip()
        student_id = str(raw.get("id") or f"s{index + 1:03d}").strip()
        if not name:
            issues.append(f"第 {index + 1} 条学生记录缺少姓名。")
            continue
        if student_id in ids:
            issues.append(f"学生 ID 重复：{student_id}。")
            continue
        ids.add(student_id)
        names[name] = names.get(name, 0) + 1
        gender = str(raw.get("gender", "unknown")).lower()
        vision = str(raw.get("vision", "unknown")).lower()
        discipline = str(raw.get("discipline", "unknown")).lower()
        student: dict[str, Any] = {
            "id": student_id,
            "name": name,
            "gender": gender if gender in {"male", "female", "unknown"} else "unknown",
            "vision": vision if vision in {"normal", "mild", "moderate", "severe", "unknown"} else "unknown",
            "discipline": discipline if discipline in {"quiet", "normal", "talkative", "unknown"} else "unknown",
        }
        height = as_number(raw.get("heightCm"))
        score = as_number(raw.get("score"))
        if height is not None and height > 0:
            student["heightCm"] = height
        if score is not None:
            student["score"] = score
        role = str(raw.get("role", "")).strip()
        if role and role != "无":
            student["role"] = role
        tags = raw.get("tags")
        if isinstance(tags, list):
            cleaned = [str(item).strip() for item in tags if str(item).strip() and str(item).strip() != "无"]
            if cleaned:
                student["tags"] = cleaned
        students.append(student)
    duplicate_names = [name for name, count in names.items() if count > 1]
    if duplicate_names:
        issues.append(f"存在同名学生，需要用 ID 区分：{'、'.join(duplicate_names)}。")
    return students, issues


def normalize_rules(raw_rules: Any, students: list[dict[str, Any]], consider_history: bool, history: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    student_ids = {student["id"] for student in students}
    unique_names = {student["name"]: student["id"] for student in students if sum(item["name"] == student["name"] for item in students) == 1}
    issues: list[str] = []
    rules: list[dict[str, Any]] = []

    def resolve(value: Any) -> str:
        text = str(value or "").strip()
        return text if text in student_ids else unique_names.get(text, text)

    if not isinstance(raw_rules, list):
        raw_rules = []
    for index, raw in enumerate(raw_rules):
        if not isinstance(raw, dict):
            issues.append(f"第 {index + 1} 条规则不是对象。")
            continue
        rule_type = str(raw.get("type", "")).lower()
        if rule_type not in SUPPORTED_RULES:
            issues.append(f"不支持的规则类型：{rule_type or '空'}。")
            continue
        level = "hard" if raw.get("level") == "hard" or rule_type == "fixed" else "soft"
        rule = dict(raw)
        rule.update({
            "id": str(raw.get("id") or f"r{index + 1:03d}"),
            "type": rule_type,
            "level": level,
            "label": str(raw.get("label") or rule_type),
        })
        if level == "soft":
            rule["weight"] = int(clamp(as_number(raw.get("weight")) or 50, 1, 100))
        if rule_type in {"front", "avoid"}:
            references = raw.get("studentIds", [])
            rule["studentIds"] = [resolve(item) for item in references] if isinstance(references, list) else []
            unknown = [item for item in rule["studentIds"] if item not in student_ids]
            if unknown:
                issues.append(f"规则“{rule['label']}”引用未知学生：{'、'.join(unknown)}。")
        if rule_type == "front":
            rule["rows"] = max(1, int(as_number(raw.get("rows")) or 2))
            if not rule["studentIds"]:
                issues.append(f"规则“{rule['label']}”没有目标学生。")
        if rule_type == "avoid":
            rule["distance"] = max(1, int(as_number(raw.get("distance")) or 1))
            if len(rule["studentIds"]) < 2:
                issues.append(f"规则“{rule['label']}”至少需要两名学生。")
        if rule_type == "fixed":
            rule["studentId"] = resolve(raw.get("studentId"))
            rule["seatId"] = str(raw.get("seatId", "")).strip()
            if rule["studentId"] not in student_ids:
                issues.append(f"固定规则引用未知学生：{rule['studentId']}。")
            if not rule["seatId"]:
                issues.append(f"固定规则“{rule['label']}”缺少 seatId。")
        if rule_type == "gender":
            mode = str(raw.get("mode", "mixed")).lower()
            rule["mode"] = mode if mode in {"mixed", "same", "female", "male"} else "mixed"
        rules.append(rule)

    fixed_rules = [rule for rule in rules if rule["type"] == "fixed"]
    fixed_students = [rule["studentId"] for rule in fixed_rules]
    fixed_seats = [rule["seatId"] for rule in fixed_rules]
    if len(fixed_students) != len(set(fixed_students)):
        issues.append("同一学生不能同时固定到多个座位。")
    if len(fixed_seats) != len(set(fixed_seats)):
        issues.append("同一座位不能同时固定给多名学生。")

    if not rules:
        vision_ids = [student["id"] for student in students if student["vision"] in {"moderate", "severe"}]
        if vision_ids:
            rules.append({"id": "default-front", "type": "front", "level": "soft", "weight": 85, "studentIds": vision_ids, "rows": 2, "label": "中重度近视学生尽量安排前两排"})
        if any("heightCm" in student for student in students):
            rules.append({"id": "default-height", "type": "height", "level": "soft", "weight": 65, "label": "身高尽量前低后高"})
        if any(student["discipline"] == "talkative" for student in students):
            rules.append({"id": "default-discipline", "type": "discipline", "level": "soft", "weight": 70, "label": "课堂活跃学生尽量分散"})
    if consider_history and history and not any(rule["type"] == "fairness" for rule in rules):
        rules.append({"id": "default-fairness", "type": "fairness", "level": "soft", "weight": 85, "label": "参考历史进行前中后轮换并减少重复同桌"})
    return rules, issues


def fixed_seat_ids(rules: list[dict[str, Any]]) -> set[str]:
    return {rule["seatId"] for rule in rules if rule["type"] == "fixed" and rule.get("seatId")}


def make_layout(raw_layout: Any, student_count: int, rules: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    raw = raw_layout if isinstance(raw_layout, dict) else {}
    cols = int(as_number(raw.get("cols")) or 8)
    issues: list[str] = []
    if not 4 <= cols <= 10:
        issues.append("教室列数必须是 4–10 的整数。")
        cols = int(clamp(cols, 4, 10))
    aisles = sorted({int(value) for value in raw.get("aislesAfter", default_aisles(cols)) if as_number(value) is not None and 0 < int(value) < cols})
    podium = bool(raw.get("podiumSideSeats", False))
    explicit_disabled = {str(value) for value in raw.get("disabledSeatIds", []) if str(value)}
    fixed_ids = fixed_seat_ids(rules)
    rows_value = raw.get("rows", "auto")
    auto_rows = rows_value == "auto" or rows_value is None
    rows = max(1, math.ceil(max(0, student_count - (2 if podium else 0)) / cols)) if auto_rows else max(1, int(as_number(rows_value) or 1))
    referenced_rows = [seat_row_from_id(value) for value in explicit_disabled | fixed_ids]
    rows = max(rows, max((row + 1 for row in referenced_rows if row is not None and row >= 0), default=1))

    def build(current_rows: int) -> list[dict[str, Any]]:
        seats: list[dict[str, Any]] = []
        for row in range(current_rows):
            desk = 0
            desk_size = 0
            for col in range(cols):
                seat_id = f"seat-{row}-{col}"
                seats.append({"id": seat_id, "row": row, "col": col, "zone": "classroom", "deskId": f"desk-{row}-{desk}", "usable": seat_id not in explicit_disabled})
                desk_size += 1
                if desk_size == 2 or col + 1 in aisles:
                    desk += 1
                    desk_size = 0
        if podium:
            seats.extend([
                {"id": "podium-left", "row": -1, "col": max(0, cols // 2 - 1), "zone": "podium", "deskId": "podium-left", "usable": "podium-left" not in explicit_disabled},
                {"id": "podium-right", "row": -1, "col": cols // 2, "zone": "podium", "deskId": "podium-right", "usable": "podium-right" not in explicit_disabled},
            ])
        return seats

    seats = build(rows)
    while auto_rows and sum(seat["usable"] for seat in seats) < student_count:
        rows += 1
        seats = build(rows)
    known_seats = {seat["id"] for seat in seats}
    for seat_id in fixed_ids:
        if seat_id not in known_seats:
            issues.append(f"固定座位不存在：{seat_id}。")
        elif seat_id in explicit_disabled:
            issues.append(f"固定座位同时被设为不可用：{seat_id}。")
    if bool(raw.get("trimExtraSeats", True)):
        surplus = sum(seat["usable"] for seat in seats) - student_count
        for seat in reversed([item for item in seats if item["zone"] == "classroom"]):
            if surplus <= 0:
                break
            if seat["usable"] and seat["id"] not in fixed_ids:
                seat["usable"] = False
                surplus -= 1
    capacity = sum(seat["usable"] for seat in seats)
    if capacity < student_count:
        issues.append(f"可用座位只有 {capacity} 个，少于 {student_count} 名学生。")
    layout = {
        "rows": rows,
        "cols": cols,
        "aislesAfter": aisles,
        "podiumSideSeats": podium,
        "trimExtraSeats": bool(raw.get("trimExtraSeats", True)),
        "disabledSeatIds": [seat["id"] for seat in seats if not seat["usable"]],
        "capacity": capacity,
    }
    return layout, seats, issues


def student_locations(assignment: dict[str, str | None], students: list[dict[str, Any]], seats: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    by_student = {student["id"]: student for student in students}
    by_seat = {seat["id"]: seat for seat in seats}
    return [(by_student[student_id], by_seat[seat_id]) for seat_id, student_id in assignment.items() if student_id in by_student and seat_id in by_seat]


def distance(first: dict[str, Any], second: dict[str, Any]) -> int:
    if first["zone"] == second["zone"] == "classroom":
        return abs(first["row"] - second["row"]) + abs(first["col"] - second["col"])
    if first["id"] == second["id"]:
        return 0
    return abs(first["row"] - second["row"]) + abs(first["col"] - second["col"]) + 1


def gender_pair_eligible(pair: list[dict[str, Any]], mode: str) -> bool:
    if len(pair) != 2 or any(student["gender"] == "unknown" for student in pair):
        return False
    if mode == "female":
        return any(student["gender"] == "female" for student in pair)
    if mode == "male":
        return any(student["gender"] == "male" for student in pair)
    return True


def gender_pair_matches(pair: list[dict[str, Any]], mode: str) -> bool:
    if not gender_pair_eligible(pair, mode):
        return True
    genders = [student["gender"] for student in pair]
    if mode == "mixed":
        return genders[0] != genders[1]
    if mode == "same":
        return genders[0] == genders[1]
    if mode == "female":
        return all(gender == "female" for gender in genders)
    return all(gender == "male" for gender in genders)


def desk_groups(located: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for student, seat in located:
        groups.setdefault(seat["deskId"], []).append(student)
    return groups


def hard_violations(assignment: dict[str, str | None], students: list[dict[str, Any]], seats: list[dict[str, Any]], rules: list[dict[str, Any]]) -> list[str]:
    located = student_locations(assignment, students, seats)
    student_seat = {student["id"]: seat for student, seat in located}
    students_by_id = {student["id"]: student for student in students}
    desks = desk_groups(located)
    scores = [student["score"] for student in students if "score" in student]
    average = sum(scores) / len(scores) if scores else 0
    violations: list[str] = []
    for rule in rules:
        if rule["level"] != "hard":
            continue
        label = rule["label"]
        if rule["type"] == "fixed" and student_seat.get(rule["studentId"], {}).get("id") != rule["seatId"]:
            violations.append(label)
        elif rule["type"] == "front" and any(student_id in student_seat and student_seat[student_id]["row"] >= rule["rows"] for student_id in rule["studentIds"]):
            violations.append(label)
        elif rule["type"] == "avoid":
            target_seats = [student_seat[student_id] for student_id in rule["studentIds"] if student_id in student_seat]
            if any(distance(a, b) <= rule["distance"] for a, b in itertools.combinations(target_seats, 2)):
                violations.append(label)
        elif rule["type"] == "gender" and any(gender_pair_eligible(pair, rule.get("mode", "mixed")) and not gender_pair_matches(pair, rule.get("mode", "mixed")) for pair in desks.values()):
            violations.append(label)
        elif rule["type"] == "discipline":
            active = [(student, seat) for student, seat in located if student["discipline"] == "talkative"]
            if any(distance(a[1], b[1]) <= 1 for a, b in itertools.combinations(active, 2)):
                violations.append(label)
        elif rule["type"] == "height":
            known = [(student, seat) for student, seat in located if "heightCm" in student and seat["zone"] == "classroom"]
            if any((a[0]["heightCm"] - b[0]["heightCm"]) * (a[1]["row"] - b[1]["row"]) < 0 for a, b in itertools.combinations(known, 2)):
                violations.append(label)
        elif rule["type"] == "score" and scores:
            if any(len(pair) == 2 and all(student.get("score", average) > average for student in pair) or len(pair) == 2 and all(student.get("score", average) < average for student in pair) for pair in desks.values()):
                violations.append(label)
    return list(dict.fromkeys(violations))


def row_zone(row: int, rows: int) -> int:
    if row < 0:
        return 0
    return min(2, math.floor(row * 3 / max(1, rows)))


def historic_seat_for(history: dict[str, Any], student: dict[str, Any]) -> str | None:
    assignment = history.get("assignment", {})
    if not isinstance(assignment, dict):
        return None
    candidate_ids = {student["id"]}
    for item in history.get("students", []) if isinstance(history.get("students"), list) else []:
        if isinstance(item, dict) and item.get("name") == student["name"]:
            candidate_ids.add(str(item.get("id", "")))
    return next((seat_id for seat_id, student_id in assignment.items() if student_id in candidate_ids), None)


def historic_mate_ids(history: dict[str, Any], seat_id: str) -> set[str]:
    row = seat_row_from_id(seat_id)
    col = seat_col_from_id(seat_id)
    if row is None or col is None:
        return set()
    desk_key = (row, col // 2)
    mates = set()
    for other_seat, student_id in history.get("assignment", {}).items():
        other_row = seat_row_from_id(other_seat)
        other_col = seat_col_from_id(other_seat)
        if other_row is not None and other_col is not None and (other_row, other_col // 2) == desk_key and other_seat != seat_id:
            mates.add(str(student_id))
    return mates


def fairness_score(located: list[tuple[dict[str, Any], dict[str, Any]]], rows: int, history: list[dict[str, Any]]) -> tuple[int, str]:
    recent = [item for item in history[:6] if isinstance(item, dict)]
    if not recent:
        return 100, "首个正式版本，建立轮换基线"
    current_desk_students: dict[str, set[str]] = {}
    for student, seat in located:
        current_desk_students.setdefault(seat["deskId"], set()).add(student["id"])
    total = 0.0
    considered = 0
    for student, seat in located:
        repeat_zone = 0.0
        repeat_mate = 0.0
        weight_total = 0.0
        current_mates = current_desk_students.get(seat["deskId"], set()) - {student["id"]}
        for index, version in enumerate(recent):
            historic_seat = historic_seat_for(version, student)
            if not historic_seat:
                continue
            weight = 0.78 ** index
            weight_total += weight
            historic_rows = int(as_number(version.get("rows")) or rows)
            historic_row = seat_row_from_id(historic_seat)
            if historic_row is not None and row_zone(historic_row, historic_rows) == row_zone(seat["row"], rows):
                repeat_zone += weight
            if current_mates & historic_mate_ids(version, historic_seat):
                repeat_mate += weight
        if weight_total:
            total += 1 - (repeat_zone / weight_total * 0.7 + repeat_mate / weight_total * 0.3)
            considered += 1
    score = round(total / considered * 100) if considered else 100
    return int(clamp(score, 0, 100)), f"参考最近 {len(recent)} 次前中后区域与同桌轮换"


def score_rule(rule: dict[str, Any], located: list[tuple[dict[str, Any], dict[str, Any]]], students: list[dict[str, Any]], rows: int, history: list[dict[str, Any]]) -> tuple[int, str]:
    student_seat = {student["id"]: seat for student, seat in located}
    desks = desk_groups(located)
    rule_type = rule["type"]
    if rule_type == "front":
        targets = [student_id for student_id in rule["studentIds"] if student_id in student_seat]
        good = sum(student_seat[student_id]["row"] < rule["rows"] for student_id in targets)
        return (round(good / len(targets) * 100) if targets else 100, f"{good}/{len(targets)} 人在前{rule['rows']}排")
    if rule_type == "avoid":
        target_seats = [student_seat[student_id] for student_id in rule["studentIds"] if student_id in student_seat]
        pairs = list(itertools.combinations(target_seats, 2))
        good = sum(distance(a, b) > rule["distance"] for a, b in pairs)
        return (round(good / len(pairs) * 100) if pairs else 100, f"{good}/{len(pairs)} 组已保持距离")
    if rule_type == "fixed":
        good = student_seat.get(rule["studentId"], {}).get("id") == rule["seatId"]
        return (100 if good else 0, "已锁定" if good else "未到指定座位")
    if rule_type == "height":
        known = [(student, seat) for student, seat in located if "heightCm" in student and seat["zone"] == "classroom"]
        pairs = list(itertools.combinations(known, 2))
        good = sum((a[0]["heightCm"] - b[0]["heightCm"]) * (a[1]["row"] - b[1]["row"]) >= 0 for a, b in pairs)
        score = round(good / len(pairs) * 100) if pairs else 100
        return score, f"{score}% 的身高顺序合理"
    if rule_type == "discipline":
        active = [(student, seat) for student, seat in located if student["discipline"] == "talkative"]
        pairs = list(itertools.combinations(active, 2))
        too_close = sum(distance(a[1], b[1]) <= 1 for a, b in pairs)
        score = round((1 - too_close / len(pairs)) * 100) if pairs else 100
        return score, "活跃学生已分散" if not too_close else f"仍有 {too_close} 组距离较近"
    if rule_type == "score":
        scores = [student["score"] for student in students if "score" in student]
        if not scores:
            return 100, "未提供成绩，不参与扣分"
        average = sum(scores) / len(scores)
        eligible = [pair for pair in desks.values() if len(pair) == 2 and all("score" in student for student in pair)]
        matched = sum((pair[0]["score"] - average) * (pair[1]["score"] - average) <= 0 for pair in eligible)
        return (round(matched / len(eligible) * 100) if eligible else 100, f"{matched}/{len(eligible)} 组实现强弱互补")
    if rule_type == "gender":
        mode = rule.get("mode", "mixed")
        eligible = [pair for pair in desks.values() if gender_pair_eligible(pair, mode)]
        matched = sum(gender_pair_matches(pair, mode) for pair in eligible)
        labels = {"mixed": "男女搭配", "same": "同性搭配", "female": "女生同桌", "male": "男生同桌"}
        return (round(matched / len(eligible) * 100) if eligible else 100, f"{matched}/{len(eligible)} 组符合{labels[mode]}")
    if rule_type == "fairness":
        return fairness_score(located, rows, history)
    return 100, "已满足"


def evaluate(assignment: dict[str, str | None], students: list[dict[str, Any]], seats: list[dict[str, Any]], rules: list[dict[str, Any]], rows: int, history: list[dict[str, Any]], profile_factors: dict[str, float] | None = None) -> dict[str, Any]:
    violations = hard_violations(assignment, students, seats, rules)
    located = student_locations(assignment, students, seats)
    rule_scores: list[dict[str, Any]] = []
    weighted_total = 0.0
    weight_total = 0.0
    profile_factors = profile_factors or {}
    for rule in rules:
        score, detail = score_rule(rule, located, students, rows, history)
        rule_scores.append({"id": rule["id"], "label": rule["label"], "score": score, "detail": detail})
        weight = 130 if rule["level"] == "hard" else rule.get("weight", 50) * profile_factors.get(rule["type"], 1.0)
        weighted_total += (0 if rule["level"] == "hard" and rule["label"] in violations else score) * weight
        weight_total += weight
    overall = round(weighted_total / weight_total) if weight_total else 100
    if violations:
        overall = min(overall, 59)
    return {"score": overall, "hardViolations": violations, "ruleScores": rule_scores}


def initial_assignment(students: list[dict[str, Any]], seats: list[dict[str, Any]], rules: list[dict[str, Any]], rng: random.Random) -> dict[str, str | None] | None:
    usable = [seat for seat in seats if seat["usable"]]
    if len(usable) < len(students):
        return None
    assignment: dict[str, str | None] = {seat["id"]: None for seat in seats}
    students_by_id = {student["id"]: student for student in students}
    placed: set[str] = set()
    occupied: set[str] = set()
    for rule in [item for item in rules if item["type"] == "fixed"]:
        if rule["studentId"] in placed or rule["seatId"] in occupied or rule["studentId"] not in students_by_id:
            return None
        seat = next((item for item in usable if item["id"] == rule["seatId"]), None)
        if not seat:
            return None
        assignment[rule["seatId"]] = rule["studentId"]
        placed.add(rule["studentId"])
        occupied.add(rule["seatId"])
    remaining_students = [student for student in students if student["id"] not in placed]
    rng.shuffle(remaining_students)
    front_limits = {
        student["id"]: min([rule["rows"] for rule in rules if rule["type"] == "front" and rule["level"] == "hard" and student["id"] in rule["studentIds"]], default=10**6)
        for student in remaining_students
    }
    remaining_students.sort(key=lambda student: (front_limits[student["id"]], student.get("heightCm", 165) + rng.random() * 4))
    available = [seat for seat in usable if seat["id"] not in occupied]
    for student in remaining_students:
        choices = [seat for seat in available if seat["row"] < front_limits[student["id"]]]
        if not choices:
            return None
        seat = rng.choice(choices)
        assignment[seat["id"]] = student["id"]
        available.remove(seat)
    return assignment


def optimize(students: list[dict[str, Any]], seats: list[dict[str, Any]], rules: list[dict[str, Any]], rows: int, history: list[dict[str, Any]], seed: int, profile_factors: dict[str, float]) -> tuple[dict[str, str | None] | None, dict[str, Any] | None]:
    rng = random.Random(seed)
    current = initial_assignment(students, seats, rules, rng)
    if current is None:
        return None, None
    current_eval = evaluate(current, students, seats, rules, rows, history, profile_factors)
    best = deepcopy(current)
    best_eval = current_eval
    locked = fixed_seat_ids(rules)
    movable = [seat["id"] for seat in seats if seat["usable"] and seat["id"] not in locked]
    turns = max(900, min(1800, len(students) * 28))
    for turn in range(turns):
        first, second = rng.sample(movable, 2)
        candidate = dict(current)
        candidate[first], candidate[second] = candidate[second], candidate[first]
        candidate_eval = evaluate(candidate, students, seats, rules, rows, history, profile_factors)
        current_value = current_eval["score"] - len(current_eval["hardViolations"]) * 1200
        candidate_value = candidate_eval["score"] - len(candidate_eval["hardViolations"]) * 1200
        temperature = max(0.15, 5.0 * (1 - turn / turns))
        if candidate_value >= current_value or rng.random() < math.exp(max(-50, candidate_value - current_value) / temperature):
            current, current_eval = candidate, candidate_eval
        best_key = (-len(best_eval["hardViolations"]), best_eval["score"])
        candidate_key = (-len(candidate_eval["hardViolations"]), candidate_eval["score"])
        if candidate_key > best_key:
            best, best_eval = deepcopy(candidate), candidate_eval
    return best, best_eval


def solve(request: dict[str, Any]) -> dict[str, Any]:
    students, student_issues = normalize_students(request.get("students"))
    history = request.get("history") if isinstance(request.get("history"), list) else []
    options = request.get("options") if isinstance(request.get("options"), dict) else {}
    rules, rule_issues = normalize_rules(request.get("rules"), students, bool(options.get("considerHistory", False)), history)
    layout, seats, layout_issues = make_layout(request.get("layout"), len(students), rules)
    issues = student_issues + rule_issues + layout_issues
    student_fatal = any("同名学生" not in issue for issue in student_issues)
    fatal = not students or student_fatal or bool(rule_issues) or bool(layout_issues)
    base_result: dict[str, Any] = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "className": str(request.get("className") or "未命名班级"),
        "students": students,
        "layout": layout,
        "seats": seats,
        "rules": rules,
        "historyCount": len(history),
        "issues": issues,
        "candidates": [],
    }
    if fatal:
        return {**base_result, "status": "unsatisfiable"}

    count = int(clamp(as_number(options.get("candidateCount")) or 3, 1, 3))
    base_seed = int(as_number(options.get("seed")) or 20260824)
    best_failed: dict[str, Any] | None = None
    for profile_index, (title, summary, factors) in enumerate(PROFILES[:count]):
        best_assignment = None
        best_evaluation = None
        for restart in range(4):
            seed = base_seed + profile_index * 5003 + restart * 997
            assignment, evaluation = optimize(students, seats, rules, layout["rows"], history, seed, factors)
            if assignment is None or evaluation is None:
                continue
            if best_failed is None or (-len(evaluation["hardViolations"]), evaluation["score"]) > (-len(best_failed["evaluation"]["hardViolations"]), best_failed["evaluation"]["score"]):
                best_failed = {"assignment": assignment, "evaluation": evaluation}
            if evaluation["hardViolations"]:
                continue
            if best_evaluation is None or evaluation["score"] > best_evaluation["score"]:
                best_assignment, best_evaluation = assignment, evaluation
        if best_assignment is not None and best_evaluation is not None:
            neutral_evaluation = evaluate(best_assignment, students, seats, rules, layout["rows"], history)
            base_result["candidates"].append({
                "id": f"candidate-{profile_index + 1}",
                "title": title,
                "summary": summary,
                "score": neutral_evaluation["score"],
                "hardViolations": neutral_evaluation["hardViolations"],
                "ruleScores": neutral_evaluation["ruleScores"],
                "assignment": best_assignment,
            })
    if not base_result["candidates"]:
        if best_failed:
            base_result["issues"].append("硬规则无法同时满足：" + "；".join(best_failed["evaluation"]["hardViolations"]))
        else:
            base_result["issues"].append("无法生成完整座位方案，请检查容量和固定座位。")
        return {**base_result, "status": "unsatisfiable"}
    return {**base_result, "status": "ok"}


def main() -> int:
    parser = argparse.ArgumentParser(description="根据学生、教室、规则和历史生成可解释座位方案。")
    parser.add_argument("request", type=Path, help="请求 JSON")
    parser.add_argument("--output", "-o", type=Path, required=True, help="结果 JSON")
    args = parser.parse_args()
    try:
        request = json.loads(args.request.read_text(encoding="utf-8-sig"))
        if not isinstance(request, dict):
            raise ValueError("请求 JSON 顶层必须是对象。")
        result = solve(request)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if result["status"] == "ok":
            print(f"已生成 {len(result['candidates'])} 个方案 → {args.output}")
            return 0
        print("无法生成满足全部硬规则的方案：", file=sys.stderr)
        for issue in result["issues"]:
            print(f"- {issue}", file=sys.stderr)
        return 3
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"编排失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
