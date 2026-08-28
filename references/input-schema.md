# Input and result schema

Use UTF-8 JSON. Unknown optional fields may be preserved, but the solver reads the fields below.

## Request

```json
{
  "schemaVersion": 1,
  "className": "三年级二班",
  "students": [
    {
      "id": "s001",
      "name": "林晓",
      "gender": "female",
      "heightCm": 154,
      "vision": "severe",
      "score": 88,
      "discipline": "quiet",
      "role": "班长",
      "tags": ["需要关注"]
    }
  ],
  "layout": {
    "rows": "auto",
    "cols": 8,
    "aislesAfter": [2, 4, 6],
    "disabledSeatIds": [],
    "podiumSideSeats": false,
    "trimExtraSeats": true
  },
  "rules": [],
  "history": [],
  "options": {
    "candidateCount": 3,
    "seed": 20260824,
    "considerHistory": false
  }
}
```

### Student values

- `id`: required stable identifier. Keep it unchanged between rotations. The importer creates `s001`, `s002`, and so on.
- `name`: required non-empty display name. Duplicate names require distinct IDs and teacher confirmation.
- `gender`: `male`, `female`, or `unknown`.
- `vision`: `normal`, `mild`, `moderate`, `severe`, or `unknown`.
- `discipline`: `quiet`, `normal`, `talkative`, or `unknown`.
- `heightCm`, `score`, `role`, and `tags` are optional. Do not invent absent values.

The importer recognizes common Chinese/English headers such as 姓名/name、性别/gender、身高/height、视力/近视/vision、成绩/score、纪律/课堂表现/discipline、职务/role、标签/tags.

### Layout

- `cols` must be an integer from 4 to 10.
- `rows` is a positive integer or `"auto"`.
- Seat IDs are `seat-{zeroBasedRow}-{zeroBasedColumn}`. Optional podium seats are `podium-left` and `podium-right`.
- `aislesAfter` uses one-based column numbers. `[2,4,6]` means an aisle follows each pair in an 8-column room.
- With `trimExtraSeats: true`, automatically calculated surplus seats become unavailable from the back-right of the final row. Explicit disabled seats are preserved.

### Confirmed history

History entries need only the information required for fair rotation:

```json
{
  "confirmedAt": "2026-08-28T09:00:00+08:00",
  "rows": 6,
  "cols": 8,
  "assignment": { "seat-0-0": "s001" },
  "students": [{ "id": "s001", "name": "林晓" }]
}
```

Use at most the most recent six confirmed versions unless the user requests another policy. Candidate/rejected layouts are not history.

## Import command

```bash
python scripts/import_students.py roster.xlsx --class-name 三年级二班 --output request.json
```

Supported locally without extra packages: `.xlsx`, `.docx` tables, `.csv`, `.tsv`, `.txt`, and `.json`. Images and PDFs require the host agent's vision/document capability before normalization.

## Result

The solver writes normalized students, layout, seats, rules, issues, and `candidates`. Each candidate contains:

- `assignment`: seat ID to student ID or `null`;
- `score`: weighted 0–100 score;
- `hardViolations`: must be empty for a usable result;
- `ruleScores`: per-rule score and concise detail;
- `title` and `summary`: the candidate's principle.

`status` is `ok` or `unsatisfiable`. Do not render an `unsatisfiable` result as if it were valid.
