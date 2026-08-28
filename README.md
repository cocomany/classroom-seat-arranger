# Classroom Seat Arranger

面向中国中小学教师的智能座位编排 Skill。它能把 Excel、Word、CSV、文本名单与自然语言要求，转换为可解释的多套座位方案，并生成可离线打开的精美座位表图片。

## 能做什么

- 导入 `.xlsx`、`.docx`、`.csv`、`.tsv`、`.txt`、`.json` 学生名单
- 理解硬规则与软规则，如固定座位、避免同桌、视力靠前、身高排序、男女搭配
- 默认按中国常见教室布局生成三套候选方案
- 参考已确认的历史座位，兼顾前后排、区域和同桌轮换公平性
- 提供校园、运动、国风、星空四套主题，导出自包含 HTML 和 PNG
- 内置中文字体与纯 CSS 主题装饰，最终座位表可离线打开

## 安装

将本仓库克隆到 Agent 的 Skill 目录即可。Codex 默认目录示例：

```bash
git clone https://github.com/cocomany/classroom-seat-arranger.git ~/.codex/skills/classroom-seat-arranger
```

也可以把整个仓库复制到 WorkBuddy 或其他兼容 `SKILL.md` 的 Agent 技能目录。仓库根目录就是 Skill 根目录，不需要再嵌套一层。

WorkBuddy 默认目录示例：

```bash
git clone https://github.com/cocomany/classroom-seat-arranger.git ~/.workbuddy/skills/classroom-seat-arranger
```

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

## 发布到 SkillHub

当前仓库同时兼容 Codex 与 [SkillHub](https://skillhub.cn/)：源码中的 `SKILL.md` 遵循 Codex frontmatter；`manifest.yaml` 保存 SkillHub 的 `slug`、`displayName`、SemVer 版本和作者资料。打包脚本会自动把 SkillHub 必填字段注入上传包，不需要人工维护两份 Skill。

Skill 文件不超过 200 个、总大小不超过 10 MiB，且不包含平台禁止上传的图片、文档或压缩包格式。主题装饰使用 CSS，PNG 图标在发布页单独上传。

生成可直接上传的 ZIP，并同时执行本地限制校验：

```bash
python scripts/package_skillhub.py --output ../classroom-seat-arranger-1.0.1.zip
```

网页端直接上传生成的 ZIP。若使用官方 CLI，请先解压该 ZIP，再对解压后的目录执行：

```bash
skillhub publish <解压后的目录> --host https://api.skillhub.cn --dry-run
```

作者信息：越山（GitHub [@cocomany](https://github.com/cocomany)）。商店页面显示的发布者身份以实际登录的 SkillHub 账号或发布者资料为准。

## 隐私

学生姓名、成绩、视力、行为和职务属于敏感信息。Skill 默认支持本地处理；请只保留排座所需字段，不要把真实学生数据、生成历史或 `.env` 提交到仓库。

## 许可证与字体

项目代码采用 [MIT License](LICENSE)。仓库中的字体遵循各自目录内的许可证文件，使用或再分发时请同时保留对应许可证。
