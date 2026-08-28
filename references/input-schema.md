# 输入与结果数据结构

统一使用 UTF-8 编码的 JSON。未知的可选字段可以保留，但求解器只读取下列字段。

## 请求结构

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

### 学生字段

- `id`：必填且稳定的学生编号，后续轮换时保持不变。导入脚本会依次生成 `s001`、`s002` 等编号。
- `name`：必填且不能为空。重名学生必须使用不同编号，并请教师确认身份。
- `gender`：可选值为 `male`、`female` 或 `unknown`。
- `vision`：可选值为 `normal`、`mild`、`moderate`、`severe` 或 `unknown`。
- `discipline`：可选值为 `quiet`、`normal`、`talkative` 或 `unknown`。
- `heightCm`、`score`、`role` 和 `tags` 为可选字段，不得编造缺失值。

导入脚本可识别姓名、性别、身高、视力、近视、成绩、纪律、课堂表现、职务、标签等常见中文表头，同时兼容相应英文表头。

### 教室布局

- `cols` 必须是 4 至 10 的整数。
- `rows` 可以是正整数或 `"auto"`。
- 普通座位编号格式为 `seat-{从零开始的行号}-{从零开始的列号}`；可选讲台侧座位为 `podium-left` 和 `podium-right`。
- `aislesAfter` 使用从 1 开始的列号。8 列教室设置 `[2,4,6]`，表示每两个座位后有一条过道。
- `trimExtraSeats` 为 `true` 时，自动计算出的多余座位会从最后一排右侧开始设为不可用；明确指定的不可用座位始终保留。

### 已确认历史

历史记录只需保存公平轮换所需的信息：

```json
{
  "confirmedAt": "2026-08-28T09:00:00+08:00",
  "rows": 6,
  "cols": 8,
  "assignment": { "seat-0-0": "s001" },
  "students": [{ "id": "s001", "name": "林晓" }]
}
```

除非用户另有要求，最多使用最近六次已确认记录。候选方案和未采用方案不属于历史。

## 导入命令

```bash
python scripts/import_students.py roster.xlsx --class-name 三年级二班 --output request.json
```

无需安装额外软件包即可读取 `.xlsx`、`.docx` 表格、`.csv`、`.tsv`、`.txt` 和 `.json`。图片与 PDF 需先由宿主智能体的视觉或文档能力识别，再进行标准化。

## 结果结构

求解器会输出标准化后的学生、布局、座位、规则、问题说明和 `candidates`。每套候选方案包含：

- `assignment`：座位编号到学生编号的对应关系，空座位为 `null`；
- `score`：0 至 100 的加权得分；
- `hardViolations`：可用方案必须为空；
- `ruleScores`：每条规则的得分和简短说明；
- `title` 和 `summary`：该方案的名称与一句话原则。

`status` 的值为 `ok` 或 `unsatisfiable`。不得把 `unsatisfiable` 的结果渲染成有效方案。
