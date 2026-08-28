---
name: classroom-seat-arranger
description: 将学生名单、教室布局、教师排座要求和已确认的历史座位，转换为可解释、可轮换的多套座位方案与精美座位表。适用于导入学生名单、理解排座规则、编排或轮换座位、调整已有方案，以及导出中国中小学班级座位表。
license: MIT
metadata:
  version: "1.0.2"
  author: "越山"
  homepage: "https://seat.sofasay.com/"
  repository: "https://github.com/cocomany/classroom-seat-arranger"
  skillhub-manifest: "./manifest.yaml"
---

# 智能座位编排

直接生成可用的座位方案，不要只给建议或文字计划。由智能体理解不规整的输入，再用技能内置的确定性脚本校验数据、求解约束并渲染成品。

## 根据任务选择工具

- Excel、CSV、Word、JSON 或纯文本名单：使用 `scripts/import_students.py`。映射字段或构造 JSON 时，阅读 [references/input-schema.md](references/input-schema.md)。
- 名单照片、截图、PDF、语音转写或自由粘贴的表格：使用宿主提供的视觉、文档或音频能力识别，先向用户展示提取结果以便纠错，再按数据结构写入标准 JSON。不要声称导入脚本具备它实际没有的图片文字识别能力。
- 自然语言排座要求：阅读 [references/rule-model.md](references/rule-model.md)，转换成结构化规则，并保留硬规则或软规则的原意。
- 新排座、调整方案或公平轮换：完成数据标准化后运行 `scripts/arrange_seats.py`。
- 生成座位表图片：阅读 [references/rendering.md](references/rendering.md)，再运行 `scripts/render_board.py`。

所有路径以本技能目录为基准解析。用户文件应写入当前任务的输出目录，不要把生成的历史记录或学生数据写回技能目录。

## 默认设置

仅在教师没有明确指定时采用以下默认值：

- 教室默认 8 列，每两个相邻座位组成一桌，第 2、4、6 列后设过道。
- 根据学生人数自动计算行数；最后一排多余座位设为不可用；默认不启用讲台两侧座位。
- 中重度近视尽量安排在前两排，个子较矮的尽量靠前，课堂活跃的学生尽量分散。除非教师明确说“必须”“不能”等，否则这些都是软规则。
- 默认生成三套方案：综合均衡、学习搭配、轮换优先。
- 默认使用 `campus` 清新校园主题；也可选择 `sports` 活力运动、`ink` 国风书院或 `space` 宇宙探索。
- 即使没有学生属性，也要正常排座；缺少可选信息不能成为使用门槛。

只有缺失信息会造成实质不同的结果时才追问。常规布局默认值无需确认；名单身份不明确、可用座位不足、硬规则引用未知学生或多条硬规则互相冲突时必须询问或说明。

## 可靠工作流程

1. 提取并标准化学生名单。同一学生的编号在后续轮换中必须保持稳定。
2. 识别结果可能有误时，先提供紧凑的校对预览；任何修改都必须同步影响后续规则和输出。
3. 标准化教室布局与排座规则，求解前校验学生和座位引用。
4. 运行求解器，例如：

   ```bash
   python scripts/arrange_seats.py request.json --output result.json
   ```

5. 检查 `status`、`issues`、候选方案得分、逐条规则得分和 `hardViolations`。不得悄悄把硬规则降级。若 `status` 为 `unsatisfiable`，说明最小可行调整，并停止生成伪造的成功结果。
6. 让教师选择方案或描述调整。锁定座位应转换为 `fixed` 规则后重新求解，不要依赖容易出错的手工 JSON 修改。
7. 渲染自包含预览；本机有 Chrome 或 Chromium 时同时生成 PNG：

   ```bash
   python scripts/render_board.py result.json --candidate 0 --theme campus --output seat-chart.html --png seat-chart.png
   ```

8. 只有教师最终确认的方案才写入历史。下次轮换时传入已确认历史，并将 `options.considerHistory` 设为 `true`；不得把未选方案或草稿推断成历史。

## 交付检查

交付前确认：

- 每名学生恰好出现一次；
- 不可用座位没有安排学生；
- 所有硬规则均无违例；
- 容量、行数和列数与教室布局一致；
- 每套方案都有一句话编排原则和逐条规则说明；
- 姓名在座位卡片中保持单行，讲台侧座位紧贴讲台，不可用座位显示为空白虚线框；
- 嵌入字体和主题资源后，输出文件无需联网即可打开。

安装或修改技能后运行 `python scripts/self_test.py`。该脚本会验证名单导入、确定性求解、硬规则、公平轮换、HTML 渲染，以及可选的 PNG 导出流程。

## 数据边界

学生姓名、成绩、视力、课堂表现和职务可能属于未成年人敏感信息。条件允许时优先在本地处理，只收集排座所需字段；未经用户授权，不得上传或保留原始文件，也不得在日志中暴露学生数据。生成结果和已确认历史应保存到用户指定的位置。
