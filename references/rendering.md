# 渲染与导出

`scripts/render_board.py` 会把一套有效候选方案渲染成自包含 HTML 座位表。它会嵌入内置中文字体，并使用 CSS 绘制主题装饰，因此预览不依赖网络或外部图片资源。

```bash
python scripts/render_board.py result.json \
  --candidate 0 \
  --theme campus \
  --output outputs/三年级二班座位表.html \
  --png outputs/三年级二班座位表.png
```

主题包括：`campus` 清新校园（默认）、`sports` 活力运动、`ink` 国风书院、`space` 宇宙探索。

内置资源位于 `assets/templates` 和 `assets/fonts`。四套主题使用紧凑的 CSS 矢量装饰；Noto Sans SC 用于保证未安装中文字体的电脑也能清晰显示姓名，Ma Shan Zheng 用于国风主题标题。两套字体的许可证均已保留。

启用 PNG 参数后，脚本会查找本机已安装的 Chrome、Chromium 或 Edge，并截取完整座位表。若没有可用浏览器，HTML 仍会正常生成，脚本会给出明确提示；此时可用宿主的浏览器或截图能力，按 `.board` 元素的原始尺寸导出。

常用参数：

- `--hide-tags`：隐藏学生属性标签；
- `--hide-roles`：隐藏班级职务；
- `--no-embed-fonts`：诊断时不嵌入字体，生成更快但依赖系统字体；跨设备交付的最终成品不要使用。

视觉要求：

- 座位表中不显示主题营销说明；
- 学生姓名不换行，2 至 4 个汉字自动缩放适配；
- 无论学生是否有职务，所有卡片高度一致；
- 男女生标记同时使用文字和颜色区分；
- 不可用座位只显示空白虚线框，不显示灰色卡片或文字；
- 讲台侧座位紧贴较短的讲台；
- 过道明显宽于同桌间距，但远窄于一个座位；
- 预览与 PNG 共用同一套 HTML、CSS 装饰和本地字体。

不得添加会遮挡姓名、职务、座位号或教师视线方向的装饰元素。
