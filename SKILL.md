---
name: classroom-seat-arranger
description: Turn class rosters, classroom layouts, teacher requirements, and confirmed seating history into explainable seating candidates and polished seat-chart files. Use for importing student lists, interpreting seating rules, arranging or rotating classroom seats, revising an existing chart, or exporting a Chinese classroom seat chart.
license: MIT
metadata:
  version: "1.0.1"
  author: "越山"
  homepage: "https://seat.sofasay.com/"
  repository: "https://github.com/cocomany/classroom-seat-arranger"
  skillhub-manifest: "./manifest.yaml"
---

# Classroom Seat Arranger

Create a usable seating result, not merely advice or a prose plan. Let the agent understand messy input; let the bundled deterministic scripts validate data, solve constraints, and render the result.

## Route the request

- For Excel, CSV, Word, JSON, or plain-text rosters, use `scripts/import_students.py`. Read [references/input-schema.md](references/input-schema.md) when mapping fields or constructing JSON.
- For a roster photo, screenshot, PDF, voice transcript, or free-form pasted table, use the host's available vision/document/audio capability, show the extracted roster for correction, then write the normalized JSON described in the schema. Do not claim that the importer can OCR files it cannot read.
- For natural-language rules, read [references/rule-model.md](references/rule-model.md). Convert meaning to structured rules; preserve whether a requirement is hard or soft.
- For new arrangements, revisions, or fair rotations, run `scripts/arrange_seats.py` after normalization.
- For a visual seat chart, read [references/rendering.md](references/rendering.md), then run `scripts/render_board.py`.

Resolve paths relative to this skill folder. Use a task output directory for user artifacts; never write generated histories or student data back into the skill folder.

## Defaults that keep the workflow moving

Use these only when the teacher did not specify otherwise:

- 8 classroom columns, paired as two adjacent seats with aisles after columns 2, 4, and 6.
- Row count calculated from the student count. Extra seats in the last row become unavailable; podium-side seats are off.
- Moderate/severe myopia prefers the first two rows; shorter students prefer the front; talkative students prefer separation. These are soft unless the teacher says “必须”, “不能”, or equivalent.
- Produce three candidates: comprehensive balance, learning pairing, and rotation priority.
- Use the bundled `campus` visual theme unless the teacher chooses `sports`, `ink`, or `space`.
- If no student attributes exist, still arrange everyone. Missing information must not become a prerequisite.

Ask only for information that blocks a materially different result. Reasonable layout defaults do not require confirmation. Do ask when the roster identity is ambiguous, usable seats are insufficient, a hard rule refers to an unknown student, or mutually incompatible hard rules cannot be resolved.

## Reliable workflow

1. Extract and normalize the roster. Keep stable student IDs across later rotations.
2. Present a compact correction preview when extraction may be inaccurate. Corrections must flow into every later rule and output.
3. Normalize the classroom and rules. Validate student and seat references before solving.
4. Run the solver, for example:

   ```bash
   python scripts/arrange_seats.py request.json --output result.json
   ```

5. Inspect `status`, `issues`, candidate scores, rule scores, and `hardViolations`. Never silently downgrade a hard rule. If `status` is `unsatisfiable`, explain the smallest useful change and stop before rendering a fake success.
6. Let the teacher choose a candidate or describe adjustments. Encode locks as `fixed` rules and rerun; do not rely on fragile manual JSON edits.
7. Render a self-contained preview and, when local Chrome/Chromium is available, a PNG:

   ```bash
   python scripts/render_board.py result.json --candidate 0 --theme campus --output seat-chart.html --png seat-chart.png
   ```

8. Treat only the teacher-confirmed candidate as history. For a later rotation, pass confirmed history and set `options.considerHistory` to `true`; never invent or infer history from rejected candidates.

## Completion checks

Before handing off the result, verify:

- every current student appears exactly once;
- no unavailable seat has a student;
- all hard rules have zero violations;
- capacity and row/column counts match the classroom;
- candidates include a one-line principle and per-rule explanation;
- names remain single-line in the rendered chart, podium-side seats touch the podium, and unavailable seats are empty dashed boxes;
- the output opens without network access when fonts and theme assets are embedded.

Run `python scripts/self_test.py` after installing or modifying this skill. It exercises import, deterministic solving, hard constraints, fair rotation, HTML rendering, and the optional PNG path.

## Data boundary

Student names, scores, vision, behavior, and roles can be sensitive information about minors. Keep processing local when practical, minimize fields, do not upload or retain source files without the user's authorization, and do not expose student data in logs. Generated output and confirmed history belong in the user's chosen location.
