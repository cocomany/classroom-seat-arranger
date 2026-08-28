# Rendering and export

`scripts/render_board.py` renders one valid candidate into a self-contained HTML seat chart. It embeds the bundled Chinese fonts and draws theme decoration with CSS, so the preview does not depend on a network connection or binary image assets.

```bash
python scripts/render_board.py result.json \
  --candidate 0 \
  --theme campus \
  --output outputs/三年级二班座位表.html \
  --png outputs/三年级二班座位表.png
```

Themes: `campus` 清新校园（default）、`sports` 活力运动、`ink` 国风书院、`space` 宇宙探索.

Bundled resources live under `assets/templates` and `assets/fonts`. The four themes use compact CSS vector decoration; Noto Sans SC keeps names readable on machines without Chinese system fonts, while Ma Shan Zheng gives the ink theme its title style. Both font licenses are retained.

The PNG option searches for an installed Chrome, Chromium, or Edge and captures the full chart. When none is available, the HTML is still produced and the script exits with a clear message; use the host browser/screenshot capability to capture the `.board` element at its natural size.

Useful flags:

- `--hide-tags`: omit student attribute tags.
- `--hide-roles`: omit class roles.
- `--no-embed-fonts`: faster diagnostic output that uses system font fallbacks; do not use it for final cross-device delivery.

Visual invariants:

- the chart itself contains no theme marketing description;
- student names never wrap; 2–4 Chinese characters scale to fit;
- all cards have equal height, whether or not a student has a role;
- female and male indicators use both icon/text and color;
- unavailable seats are empty dashed outlines, not gray cards or labels;
- podium-side seats sit directly beside the shorter podium;
- aisles are visibly wider than a desk seam but much narrower than a seat;
- preview and PNG use the same HTML, CSS decoration, and local fonts.

Do not add decorative elements that obscure names, roles, seat numbers, or the teacher's view direction.
