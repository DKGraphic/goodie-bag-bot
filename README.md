# Goodie Bag Bot

 Automate turning HR photos into thank-you cards with templated layouts. Point the tool at your photos (PNG keeps transparency), a YAML/CSV job list, and a template configuration; it will export polished cards into an output folder.

## Quick start

1) Install dependencies (Python 3.10+):

```bash
python -m venv .venv
.venv/Scripts/activate  # Windows
pip install -r requirements.txt
```

2) Put your template and photos in the repo (see `configs/template.yml` and `input_photos/`).

3) Run the generator:

```bash
python -m goodie_bot --template configs/template.yml --jobs jobs/sample_jobs.yml --output output
```

Each job entry becomes one exported card in `output/`. The default template is built from the provided `template/assets` files and sized to 1920x1080.

Or use the simple dashboard (no CLI needed):

Run it from the project root:

- Preferred (module path works both inside and outside a venv):
  ```bash
  python -m streamlit run goodie_bot/ui.py
  ```
- If installed as a package and `goodie-bag-ui` is on PATH:
  ```bash
  goodie-bag-ui
  ```

Adjust template/jobs/output paths in the left sidebar and click **Generate All**.
For PNGs with premade transparency, just upload and generate (no background removal is applied).

## How it works

- **Background removal** is disabled; upload pre-cut PNGs (transparency preserved).
- **Color correction** is optional; defaults off in the UI. Enable if you want a slight auto-contrast/vibrancy boost (no background changes).
- **Templates** are defined in YAML: canvas size, optional template image, photo box coordinates, and text block styling.
- **Jobs** can be YAML or CSV. A job maps photos to the template plus recipient/giver names and a message.

## Template config (`configs/template.yml`)

```yaml
canvas:
  width: 1920
  height: 1080
  template_path: template/assets/background.png

overlays:
  - { path: template/assets/element 1.png, x: 1118, y: 0, width: 805, height: 426, placement: before_photos }
  - { path: template/assets/element 3.png, x: 0, y: 386, width: 1262, height: 607 }
  - { path: template/assets/element 2.png, x: 0, y: 540, width: 1920, height: 549 }
  - { path: template/assets/congrats text.png, x: 60, y: 40, width: 650, height: 212 }
  - { path: template/assets/logo.png, x: 1260, y: 941, width: 531, height: 40 }

photo_boxes:
  - { x: 290, y: 36, width: 1189, height: 920, border_radius: 24 }

text_blocks:
  recipient: { text: "{recipient_name}", x: 75, y: 720, size: 30, color: "#ffffff", font_path: template/assets/font/BAHNSCHRIFT.TTF, max_width: 500 }
  project:   { text: "{project_name}", x: 75, y: 760, size: 26, color: "#ffffff", font_path: template/assets/font/BAHNSCHRIFT.TTF, max_width: 500 }
  message:   { text: "{message}", x: 75, y: 800, size: 24, color: "#ffc000", font_path: template/assets/font/BAHNSCHRIFT.TTF, max_width: 500 }
  giver:     { text: "{giver_name}", x: 75, y: 840, size: 24, color: "#ffffff", font_path: template/assets/font/BAHNSCHRIFT.TTF, max_width: 500 }
```

Notes:
- Overlays are layered from top to bottom in the order listed. `placement` can be `before_photos`, `after_photos` (default), or `top` (above text).
- `photo_boxes` are where the processed portraits land; tweak x/y/width/height to align with your template.
- Text uses Pillow fonts; to use your own font, set `font_path` in a block or pass `--font path/to/font.ttf` to override all blocks. If a font cannot be loaded, the default PIL font is used.

## Jobs file (YAML or CSV)

Example YAML (`jobs/sample_jobs.yml`) with two sample cards:

```yaml
- recipient_name: Jane Doe
  giver_name: HR Team
  message: "Receiving goodie bag from"
  project_name: "Project Phoenix"
  photos: [input_photos/jane.png]
  output_name: jane-card

- recipient_name: Product Crew
  giver_name: Alan & Priya
  message: "Receiving goodie bag from"
  project_name: "Project Skyline"
  photos:
    - input_photos/crew.jpg
  output_name: product-crew
```

CSV headers: `recipient_name,giver_name,message,photos,output_name` (`photos` is semicolon-separated).

## CLI options

```
python -m goodie_bot --template configs/template.yml --jobs jobs/sample_jobs.yml --output output
  --skip-autocolor   # do not auto-adjust color/contrast
  --font-scale 1.0   # scale template text sizes (e.g., 1.1 for +10%)
  --font path.ttf    # override font for all text blocks
  --dry-run          # parse everything without writing files
```

## Folder layout (suggested)

- `configs/` – template YAML configs.
- `jobs/` – job lists (YAML/CSV).
- `input_photos/` – raw HR photos to process.
- `assets/` – template images or fonts you want to reference.
- `output/` – generated cards.

## Adapting to your template

1. Measure the canvas size of your real template (e.g., 1600x900) and set `canvas.width/height`.
2. For each face spot, record its top-left `x/y` coordinates and `width/height` in `photo_boxes`.
3. Decide on text positions and sizes; update `text_blocks`.
4. Add your template image path to `canvas.template_path` if you want the design baked in.

## Troubleshooting

- `rembg` missing? Install via `pip install rembg` or run with `--skip-rembg`.
- Wrong font or non-existent path? The tool falls back to the default PIL font and logs a notice.
- More photos than boxes? Extra photos are ignored; add more `photo_boxes` for multi-person cards.

## Next improvements (if needed)

- Add per-person positioning rules (e.g., automatic grid when >2 people).
- Connect to a spreadsheet or webhook for HR uploads.
- Export both PNG and print-ready PDF.
