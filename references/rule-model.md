# Rule model

Convert teacher language into explicit structured intent. Prefer a small set of composable rules over a long prompt.

All rules have `id`, `type`, `level`, and a Chinese `label`. Soft rules also use `weight` from 1–100. `hard` means failure makes the candidate unusable; `soft` means optimize and explain the degree achieved.

## Supported rules

### Front rows

```json
{"id":"r-front","type":"front","level":"hard","studentIds":["s001"],"rows":2,"label":"林晓必须在前两排"}
```

Use for vision, hearing, attention, or teacher-directed front-row placement. “尽量靠前” is soft; “必须前两排” is hard.

### Avoid nearby

```json
{"id":"r-avoid","type":"avoid","level":"hard","studentIds":["s003","s009"],"distance":1,"label":"两人不能相邻"}
```

`distance: 1` prevents Manhattan-adjacent seats; `2` creates a wider buffer. More than two student IDs means every pair in the group is checked.

### Fixed/locked seat

```json
{"id":"r-fixed","type":"fixed","level":"hard","studentId":"s007","seatId":"seat-0-3","label":"锁定当前座位"}
```

Use after teacher drag-adjustment or an explicit seat assignment. Fixed rules are always hard.

### Height, classroom behavior, and score

```json
{"id":"r-height","type":"height","level":"soft","weight":65,"label":"身高尽量前低后高"}
{"id":"r-order","type":"discipline","level":"soft","weight":75,"label":"课堂活跃学生尽量分散"}
{"id":"r-score","type":"score","level":"soft","weight":55,"label":"同桌成绩尽量互补"}
```

Only use these when the relevant student field exists. Do not infer behavior or achievement from names, gender, roles, or prior seats.

### Gender pairing

```json
{"id":"r-gender","type":"gender","level":"soft","weight":60,"mode":"mixed","label":"男女生优先同桌"}
```

Modes:

- `mixed`: different known genders at a two-person desk;
- `same`: same known gender;
- `female`: female students prefer female desk mates; male-only desks are not penalized;
- `male`: male students prefer male desk mates; female-only desks are not penalized.

Unknown gender is neutral. A phrase such as “女生与女生同桌” maps to `female`, not to historical fairness.

### Fair rotation

```json
{"id":"r-fair","type":"fairness","level":"soft","weight":85,"label":"参考历史进行前中后轮换并减少重复同桌"}
```

Use only with confirmed history and explicit or clearly implied permission to consider it. The solver compares recent front/middle/back zones and repeated desk mates. Fairness is normally soft because strict long-term rotation can conflict with vision or accessibility needs.

## Interpretation rules

- “必须、固定、不能、禁止” usually means hard.
- “尽量、优先、最好、均衡” means soft.
- If wording is ambiguous and switching hard/soft could materially change the result, ask one focused question.
- Preserve accessibility and safety requirements over cosmetic fairness.
- Validate every mentioned student against the roster. Similar names are not interchangeable.
- If hard rules conflict, report the conflict. Never quietly remove, weaken, or relabel one.
