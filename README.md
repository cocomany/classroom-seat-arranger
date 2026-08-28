# Classroom Seat Arranger

面向中国中小学教师的智能座位编排 Skill。它能把 Excel、Word、CSV、文本名单与自然语言要求，转换为可解释的多套座位方案，并生成可离线打开的精美座位表图片。

## 能做什么

- 导入 `.xlsx`、`.docx`、`.csv`、`.tsv`、`.txt`、`.json` 学生名单
- 理解硬规则与软规则，如固定座位、避免同桌、视力靠前、身高排序、男女搭配
- 默认按中国常见教室布局生成三套候选方案
- 参考已确认的历史座位，兼顾前后排、区域和同桌轮换公平性
- 提供校园、运动、国风、星空四套主题，导出自包含 HTML 和 PNG
- 内置字体与主题素材，最终座位表可离线打开

## 安装

将本仓库克隆到 Agent 的 Skill 目录即可。Codex 默认目录示例：

```bash
git clone https://github.com/cocomany/classroom-seat-arranger.git ~/.codex/skills/classroom-seat-arranger
```

也可以把整个仓库复制到 WorkBuddy 或其他兼容 `SKILL.md` 的 Agent 技能目录。仓库根目录就是 Skill 根目录，不需要再嵌套一层。

## 使用

安装后直接描述任务，例如：

> 使用 classroom-seat-arranger，根据这份学生名单生成三套座位方案。近视严重的尽量坐前两排，爱讲话的学生分开，参考上次座位兼顾公平性，最后导出校园主题图片。

Agent 会读取 [SKILL.md](SKILL.md)，按需调用确定性脚本完成导入、求解和渲染。图片或 PDF 名单由宿主 Agent 的视觉/文档能力先识别，再进入相同流程。

## 命令行

脚本只依赖 Python 标准库，建议 Python 3.10 及以上。导出 PNG 时需要本机安装 Chrome、Chromium、Edge 或其他兼容浏览器。

```bash
python scripts/import_students.py roster.xlsx --class-name "三年级二班" --output request.json
python scripts/arrange_seats.py request.json --output result.json
python scripts/render_board.py result.json --candidate 0 --theme campus --output seat-chart.html --png seat-chart.png
```

主题可选：`campus`、`sports`、`ink`、`space`。输入结构、规则模型和渲染说明见 [references](references/) 目录。

## 自检

```bash
python scripts/self_test.py
```

自检覆盖名单导入、确定性排座、硬约束、公平轮换、HTML 渲染及可用时的 PNG 导出。

## 隐私

学生姓名、成绩、视力、行为和职务属于敏感信息。Skill 默认支持本地处理；请只保留排座所需字段，不要把真实学生数据、生成历史或 `.env` 提交到仓库。

## 许可证与字体

仓库中的字体遵循各自目录内的许可证文件。使用或再分发前请同时保留对应许可证。
