from __future__ import annotations

import argparse
import csv
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence
import copy

import yaml
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageChops, ImageFilter
try:
    from rembg import remove as rembg_remove
except Exception:  # pragma: no cover - optional dependency
    rembg_remove = None


DEFAULT_BG_COLOR = "#f5f6fa"
DEFAULT_TEXT_COLOR = "#1f2d3d"
PHOTO_SCALE = 1.3  # scale photos to 130% of their boxes when desired


@dataclass
class Overlay:
    path: Path
    x: int
    y: int
    width: Optional[int] = None
    height: Optional[int] = None
    placement: str = "after_photos"  # before_photos, after_photos, top


@dataclass
class PhotoBox:
    x: int
    y: int
    width: int
    height: int
    border_radius: int = 0


@dataclass
class TextBlock:
    text: str
    x: int
    y: int
    font_path: Optional[str] = None
    size: int = 48
    color: str = DEFAULT_TEXT_COLOR
    align: str = "left"
    max_width: Optional[int] = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create thank-you cards with templated layouts."
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=Path("configs/template.yml"),
        help="Path to template config (YAML).",
    )
    parser.add_argument(
        "--jobs",
        type=Path,
        default=Path("jobs/sample_jobs.yml"),
        help="Path to job definitions (YAML or CSV).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output"),
        help="Directory where finished cards will be written.",
    )
    parser.add_argument(
        "--skip-autocolor",
        action="store_true",
        help="Disable automatic color and contrast correction.",
    )
    parser.add_argument(
        "--font",
        type=Path,
        help="Override font for all text blocks.",
    )
    parser.add_argument(
        "--font-scale",
        type=float,
        default=1.3,
        help="Scale text sizes from the template (e.g., 1.1 for +10%).",
    )
    parser.add_argument(
        "--photo-scale",
        type=float,
        default=PHOTO_SCALE,
        help="Scale photos relative to their boxes (e.g., 1.0 fits box, 0.8 shrinks, 1.3 enlarges).",
    )
    parser.add_argument(
        "--remove-bg-jpg",
        action="store_true",
        help="Use rembg to remove background for JPG/JPEG photos only (PNG transparency is preserved).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load everything but do not write output files.",
    )
    return parser.parse_args()


def load_template_config(path: Path, font_override: Optional[Path]) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Template config not found: {path}")
    with path.open("r", encoding="utf-8") as fp:
        cfg = yaml.safe_load(fp)

    cfg = cfg or {}
    cfg.setdefault("canvas", {})
    cfg.setdefault("photo_boxes", [])
    cfg.setdefault("text_blocks", {})
    cfg.setdefault("overlays", [])

    if font_override:
        for block in cfg["text_blocks"].values():
            block["font_path"] = str(font_override)
    return cfg


def load_jobs(path: Path) -> List[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Jobs file not found: {path}")

    if path.suffix.lower() in {".yml", ".yaml"}:
        with path.open("r", encoding="utf-8") as fp:
            jobs = yaml.safe_load(fp) or []
        if isinstance(jobs, dict):
            jobs = jobs.get("jobs", [])
    elif path.suffix.lower() == ".csv":
        jobs = []
        with path.open("r", encoding="utf-8-sig", newline="") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                row["photos"] = [
                    part.strip() for part in str(row.get("photos", "")).split(";") if part.strip()
                ]
                jobs.append(row)
    else:
        raise ValueError("Jobs must be YAML or CSV.")
    return jobs


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def auto_color_correct(image: Image.Image, enabled: bool) -> Image.Image:
    if not enabled:
        return image
    # Pillow's autocontrast does not support RGBA; work in RGB and reattach alpha if present.
    if image.mode == "RGBA":
        alpha = image.getchannel("A")
        work = image.convert("RGB")
    else:
        alpha = None
        work = image

    corrected = ImageOps.autocontrast(work)
    corrected = ImageEnhance.Color(corrected).enhance(1.05)
    corrected = ImageEnhance.Contrast(corrected).enhance(1.02)

    if alpha is not None:
        corrected = corrected.convert("RGBA")
        corrected.putalpha(alpha)
    return corrected


def fit_image(img: Image.Image, width: int, height: int) -> Image.Image:
    # Resize while preserving aspect ratio, then center crop/pad to box.
    img_ratio = img.width / img.height
    target_ratio = width / height

    if img_ratio > target_ratio:
        new_height = height
        new_width = int(height * img_ratio)
    else:
        new_width = width
        new_height = int(width / img_ratio)

    img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    left = (new_width - width) // 2
    top = (new_height - height) // 2
    box = (left, top, left + width, top + height)
    return img_resized.crop(box)


def rounded_mask(width: int, height: int, radius: int) -> Image.Image:
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, width, height), radius=radius, fill=255)
    return mask


def paste_overlay(canvas: Image.Image, overlay: Overlay) -> None:
    img_path = overlay.path
    if not img_path.exists():
        print(f"Overlay not found: {img_path}")
        return

    img = Image.open(img_path).convert("RGBA")
    target_w = int(overlay.width or img.width)
    target_h = int(overlay.height or img.height)
    if img.size != (target_w, target_h):
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    canvas.alpha_composite(img, dest=(overlay.x, overlay.y))


def load_font(font_path: Optional[str], size: int) -> ImageFont.ImageFont:
    try:
        if font_path:
            return ImageFont.truetype(font_path, size=size)
    except Exception:
        print(f"Could not load font at {font_path}, using default.")
    return ImageFont.load_default()


def draw_text(
    canvas: Image.Image,
    block: TextBlock,
    substitutions: dict,
) -> None:
    draw = ImageDraw.Draw(canvas)
    text_value = block.text.format(**substitutions)
    font = load_font(block.font_path, block.size)
    lines = text_value.split("\\n")
    draw.multiline_text(
        (block.x, block.y),
        "\n".join(lines),
        fill=block.color,
        font=font,
        align=block.align,
        spacing=int(block.size * 0.4),
    )


def parse_photo_boxes(raw_boxes: Sequence[dict]) -> List[PhotoBox]:
    boxes: List[PhotoBox] = []
    for box in raw_boxes:
        boxes.append(
            PhotoBox(
                x=int(box["x"]),
                y=int(box["y"]),
                width=int(box["width"]),
                height=int(box["height"]),
                border_radius=int(box.get("border_radius", 0)),
            )
        )
    return boxes


def parse_text_blocks(raw_blocks: dict) -> dict:
    parsed = {}
    for key, value in raw_blocks.items():
        parsed[key] = TextBlock(
            text=value["text"],
            x=int(value["x"]),
            y=int(value["y"]),
            font_path=value.get("font_path"),
            size=int(value.get("size", 48)),
            color=value.get("color", DEFAULT_TEXT_COLOR),
            align=value.get("align", "left"),
            max_width=value.get("max_width"),
        )
    return parsed


def parse_overlays(raw_overlays: Sequence[dict]) -> List[Overlay]:
    overlays: List[Overlay] = []
    for ov in raw_overlays:
        overlays.append(
            Overlay(
                path=Path(ov["path"]),
                x=int(ov["x"]),
                y=int(ov["y"]),
                width=ov.get("width"),
                height=ov.get("height"),
                placement=ov.get("placement", "after_photos"),
            )
        )
    return overlays


def create_base_canvas(canvas_cfg: dict) -> Image.Image:
    width = int(canvas_cfg.get("width", 1600))
    height = int(canvas_cfg.get("height", 900))
    bg_color = canvas_cfg.get("background_color", DEFAULT_BG_COLOR)
    base = Image.new("RGBA", (width, height), bg_color)

    template_path = canvas_cfg.get("template_path")
    if template_path:
        template_path = Path(template_path)
        if template_path.exists():
            template_img = Image.open(template_path).convert("RGBA")
            if template_img.size != base.size:
                template_img = template_img.resize(base.size, Image.Resampling.LANCZOS)
            base = template_img
        else:
            print(f"Template image not found: {template_path}, using solid background.")
    return base


def paste_photo(
    canvas: Image.Image,
    photo: Image.Image,
    box: PhotoBox,
    auto_color: bool,
    remove_bg: bool,
    bg_color: Optional[tuple] = None,
    scale: float = PHOTO_SCALE,
) -> None:
    img = photo.convert("RGBA")
    if remove_bg and rembg_remove is not None:
        try:
            img = rembg_remove(img.convert("RGB")).convert("RGBA")
        except Exception as exc:  # pragma: no cover
            print(f"rembg failed ({exc}); using original image.")
    img = auto_color_correct(img, enabled=auto_color)
    img = fit_image(img, box.width, box.height)

    if scale > 0:
        new_w = max(1, int(img.width * scale))
        new_h = max(1, int(img.height * scale))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    else:
        new_w, new_h = img.width, img.height

    photo_alpha = img.getchannel("A")
    base_mask = photo_alpha

    if remove_bg and bg_color:
        matte = Image.new("RGBA", img.size, bg_color + (255,))
        img = Image.composite(img, matte, photo_alpha)
        base_mask = photo_alpha.filter(ImageFilter.MinFilter(3))

    if box.border_radius > 0:
        radius_scaled = max(1, int(box.border_radius * scale))
        corner_mask = rounded_mask(img.width, img.height, radius_scaled)
        base_mask = ImageChops.multiply(base_mask, corner_mask)

    # Feather edges slightly only when background removal is applied
    if remove_bg:
        base_mask = base_mask.filter(ImageFilter.GaussianBlur(radius=1.5))

    offset_x = box.x + (box.width - new_w) // 2
    offset_y = box.y + (box.height - new_h) // 2
    canvas.paste(img, (offset_x, offset_y), base_mask)


def process_job(
    job: dict,
    template_cfg: dict,
    output_dir: Path,
    auto_color: bool,
    dry_run: bool,
    font_scale: float = 1.0,
    remove_bg_jpg: bool = False,
    photo_scale: float = PHOTO_SCALE,
) -> Path:
    photo_paths = job.get("photos") or []
    if isinstance(photo_paths, str):
        photo_paths = [photo_paths]
    photos = [Path(p) for p in photo_paths]

    cfg = copy.deepcopy(template_cfg)
    if font_scale != 1.0:
        for block in cfg.get("text_blocks", {}).values():
            if "size" in block:
                block["size"] = max(1, int(round(float(block["size"]) * font_scale)))

    base = create_base_canvas(cfg["canvas"]).convert("RGBA")
    bg_rgb = hex_to_rgb(cfg["canvas"].get("background_color", DEFAULT_BG_COLOR))
    photo_boxes = parse_photo_boxes(cfg.get("photo_boxes", []))
    text_blocks = parse_text_blocks(cfg.get("text_blocks", {}))
    overlays = parse_overlays(cfg.get("overlays", []))

    if photos and not photo_boxes:
        raise ValueError("Template does not define any photo boxes.")

    if len(photos) > len(photo_boxes):
        print(
            f"Warning: {len(photos)} photos provided but only {len(photo_boxes)} boxes. Extra photos ignored."
        )

    for overlay in overlays:
        if overlay.placement == "before_photos":
            paste_overlay(base, overlay)

    substitutions = {
        "recipient_name": job.get("recipient_name", ""),
        "giver_name": job.get("giver_name", ""),
        "message": job.get("message", ""),
        "project_name": job.get("project_name", ""),
    }
    last_index = 0
    for idx, photo_path in enumerate(photos[: len(photo_boxes)]):
        last_index = idx
        if not photo_path.exists():
            print(f"Photo not found: {photo_path}, skipping.")
            continue
        img = Image.open(photo_path)
        paste_photo(
            base,
            img,
            photo_boxes[idx],
            auto_color=auto_color,
            remove_bg=remove_bg_jpg and photo_path.suffix.lower() in {".jpg", ".jpeg"},
            bg_color=bg_rgb,
            scale=photo_scale,
        )

    for overlay in overlays:
        if overlay.placement == "after_photos":
            paste_overlay(base, overlay)

    for block in text_blocks.values():
        draw_text(base, block, substitutions=substitutions)

    for overlay in overlays:
        if overlay.placement == "top":
            paste_overlay(base, overlay)

    out_name = job.get("output_name") or f"{substitutions['recipient_name'] or 'card'}_{last_index}.png"
    out_path = output_dir / f"{sanitize_filename(out_name)}.png"
    if not dry_run:
        base.save(out_path)
    return out_path


def sanitize_filename(name: str) -> str:
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch in ("_", "-", " "))
    return "_".join(cleaned.strip().split())


def hex_to_rgb(color: str) -> tuple:
    if not isinstance(color, str):
        return (245, 246, 250)
    color = color.strip()
    if not color.startswith("#"):
        return (245, 246, 250)
    if len(color) == 4:  # #abc
        r, g, b = (int(color[i] * 2, 16) for i in range(1, 4))
    elif len(color) == 7:  # #aabbcc
        r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    else:
        return (245, 246, 250)
    return (r, g, b)


def main() -> None:
    args = parse_args()
    template_cfg = load_template_config(args.template, font_override=args.font)
    jobs = load_jobs(args.jobs)
    ensure_output_dir(args.output)

    if not jobs:
        print("No jobs found. Add entries to your jobs file.")
        return

    for job in jobs:
        dest = process_job(
            job,
            template_cfg=template_cfg,
            output_dir=args.output,
            auto_color=not args.skip_autocolor,
            dry_run=args.dry_run,
            font_scale=args.font_scale,
            remove_bg_jpg=args.remove_bg_jpg,
            photo_scale=args.photo_scale,
        )
        print(f"Built card -> {dest}")


if __name__ == "__main__":
    main()
