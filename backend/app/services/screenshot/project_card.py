"""Pillow-rendered 1200x630 project card for LinkedIn posts."""

from __future__ import annotations

import io
import logging
import textwrap

from PIL import Image, ImageDraw, ImageFont

from app.services.image_processor import get_dimensions
from app.services.r2_storage import upload_image

logger = logging.getLogger(__name__)

# Card dimensions (LinkedIn recommended)
_CARD_WIDTH = 1200
_CARD_HEIGHT = 630

# Colors
_BG_COLOR = (30, 41, 59)  # Dark slate
_ACCENT_COLOR = (59, 130, 246)  # Blue
_TEXT_COLOR = (248, 250, 252)  # Near-white
_MUTED_COLOR = (148, 163, 184)  # Slate-400
_TAG_BG = (51, 65, 85)  # Slate-700


def _get_font(
    size: int, bold: bool = False
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try system fonts, fall back to Pillow default."""
    font_names = (
        ["DejaVuSans-Bold", "Helvetica-Bold", "Arial-Bold"]
        if bold
        else ["DejaVuSans", "Helvetica", "Arial"]
    )
    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    # Try common system paths
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_tag(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> int:
    """Draw a rounded tag and return the x position after it."""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pad_x, pad_y = 12, 6
    tag_w = text_w + pad_x * 2
    tag_h = text_h + pad_y * 2

    draw.rounded_rectangle(
        [x, y, x + tag_w, y + tag_h],
        radius=6,
        fill=_TAG_BG,
    )
    draw.text((x + pad_x, y + pad_y), text, fill=_TEXT_COLOR, font=font)
    return x + tag_w + 8  # 8px gap between tags


def generate_project_card(
    name: str,
    description: str,
    tech_stack: list[str],
    stars: int,
    language: str,
    key_features: list[str],
    run_id: str,
) -> list[dict]:
    """Render a 1200x630 project card and upload to R2.

    Returns a list with one Screenshot dict.
    """
    img = Image.new("RGB", (_CARD_WIDTH, _CARD_HEIGHT), _BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Accent bar at top
    draw.rectangle([0, 0, _CARD_WIDTH, 6], fill=_ACCENT_COLOR)

    # Fonts
    title_font = _get_font(42, bold=True)
    desc_font = _get_font(22)
    tag_font = _get_font(16)
    meta_font = _get_font(18)
    feature_font = _get_font(18)

    y_cursor = 40

    # Project name
    draw.text((60, y_cursor), name[:60], fill=_TEXT_COLOR, font=title_font)
    y_cursor += 60

    # Description (wrapped to 2 lines)
    if description:
        wrapped = textwrap.fill(description, width=70)
        lines = wrapped.split("\n")[:2]
        for line in lines:
            draw.text((60, y_cursor), line, fill=_MUTED_COLOR, font=desc_font)
            y_cursor += 30
    y_cursor += 20

    # Tech stack tags
    if tech_stack:
        tag_x = 60
        for tech in tech_stack[:6]:
            tag_x = _draw_tag(draw, tech, tag_x, y_cursor, tag_font)
            if tag_x > _CARD_WIDTH - 100:
                break
        y_cursor += 50

    # Key features (bullet points)
    if key_features:
        for feature in key_features[:4]:
            text = f"•  {feature[:50]}"
            draw.text((60, y_cursor), text, fill=_TEXT_COLOR, font=feature_font)
            y_cursor += 28

    # Bottom metadata bar
    meta_y = _CARD_HEIGHT - 50
    meta_parts: list[str] = []
    if language:
        meta_parts.append(language)
    if stars:
        meta_parts.append(f"★ {stars:,}")
    if meta_parts:
        meta_text = "  ·  ".join(meta_parts)
        draw.text((60, meta_y), meta_text, fill=_MUTED_COLOR, font=meta_font)

    # Serialize to PNG
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    card_bytes = buf.getvalue()

    width, height = get_dimensions(card_bytes)
    filename = f"{name.lower().replace(' ', '_')[:30]}_card.png"

    public_url = upload_image(card_bytes, run_id, filename)

    return [
        {
            "url": public_url,
            "alt_text": f"Project card for {name}",
            "source": "project_card",
            "width": width,
            "height": height,
        }
    ]
