# Rendering and export

`scripts/render_board.py` renders one valid candidate into a self-contained HTML seat chart. It embeds the chosen overlay and bundled Chinese fonts by default, so the preview does not depend on a network connection or the target machine's fonts.

```bash
python scripts/render_board.py result.json \
  --candidate 0 \
  --theme campus \
  --output outputs/三年级二班座位表.html \
  --png outputs/三年级二班座位表.png
```

Themes: `campus` 清新校园（default）、`sports` 活力运动、`ink` 国风书院、`space` 宇宙探索.

Bundled resources live under `assets/themes` (full-board transparent overlays), `assets/elements` (optional books, desks, ginkgo, and stationery accents), and `assets/fonts` (Noto Sans SC, Noto Serif SC, and Ma Shan Zheng with their licenses). The standard renderer already uses the overlays and fonts. Use individual elements only for a user-requested custom template; do not stack them over an existing themed overlay by default.

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
- preview and PNG use the same HTML and local fonts.

Do not add decorative elements that obscure names, roles, seat numbers, or the teacher's view direction.
