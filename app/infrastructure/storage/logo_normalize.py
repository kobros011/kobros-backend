"""Normaliza un logo subido: recorta márgenes transparentes, lo reduce de tamaño
y calcula su proporción y tono para que el frontend lo muestre siempre bien."""
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

MAX_SIDE = 512
_VIEWBOX_RE = re.compile(rb'viewBox=["\']\s*[\d.+-]+\s+[\d.+-]+\s+([\d.]+)\s+([\d.]+)', re.IGNORECASE)
_WIDTH_RE = re.compile(rb'\bwidth=["\']\s*([\d.]+)', re.IGNORECASE)
_HEIGHT_RE = re.compile(rb'\bheight=["\']\s*([\d.]+)', re.IGNORECASE)


@dataclass
class NormalizedLogo:
    data: bytes
    content_type: str
    ext: str
    width: int
    height: int
    tone: str  # "dark" | "light" | "mixed"


def _tone_from_luminance(mean_luminance: float, spread: float) -> str:
    if spread > 60:
        return "mixed"
    return "dark" if mean_luminance < 128 else "light"


def normalize_raster(data: bytes, content_type: str) -> NormalizedLogo:
    from PIL import Image

    img = Image.open(BytesIO(data))
    img.load()
    img = img.convert("RGBA")

    # Recortar márgenes transparentes (si el canal alfa tiene algo que recortar).
    alpha = img.getchannel("A")
    bbox = alpha.getbbox()
    if bbox and bbox != (0, 0, img.width, img.height):
        img = img.crop(bbox)

    # Reducir si excede el lado máximo, manteniendo proporción.
    if max(img.width, img.height) > MAX_SIDE:
        ratio = MAX_SIDE / max(img.width, img.height)
        img = img.resize((max(1, round(img.width * ratio)), max(1, round(img.height * ratio))), Image.LANCZOS)

    # Tono: luminancia media de los píxeles con alfa visible (ignora el fondo transparente).
    pixels = list(img.getdata())
    visible = [(r, g, b) for r, g, b, a in pixels if a > 16]
    if visible:
        luminances = [0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in visible]
        mean_l = sum(luminances) / len(luminances)
        spread = (max(luminances) - min(luminances)) if luminances else 0
        tone = _tone_from_luminance(mean_l, spread)
    else:
        tone = "mixed"

    has_alpha = any(a < 255 for *_, a in pixels[:10000]) or bbox != (0, 0, img.width, img.height)
    buf = BytesIO()
    if has_alpha:
        img.save(buf, format="PNG", optimize=True)
        out_content_type, out_ext = "image/png", "png"
    else:
        img.convert("RGB").save(buf, format="WEBP", quality=90, method=6)
        out_content_type, out_ext = "image/webp", "webp"

    return NormalizedLogo(
        data=buf.getvalue(),
        content_type=out_content_type,
        ext=out_ext,
        width=img.width,
        height=img.height,
        tone=tone,
    )


def describe_svg(data: bytes) -> NormalizedLogo:
    width = height = None
    vb = _VIEWBOX_RE.search(data)
    if vb:
        try:
            width, height = float(vb.group(1)), float(vb.group(2))
        except ValueError:
            width = height = None
    if not width or not height:
        w = _WIDTH_RE.search(data)
        h = _HEIGHT_RE.search(data)
        try:
            width = float(w.group(1)) if w else None
            height = float(h.group(1)) if h else None
        except ValueError:
            width = height = None
    if not width or not height:
        width, height = 100, 100
    # Normaliza a una proporción manejable (los valores exactos no importan, solo la razón).
    scale = 256 / max(width, height)
    return NormalizedLogo(
        data=data,
        content_type="image/svg+xml",
        ext="svg",
        width=max(1, round(width * scale)),
        height=max(1, round(height * scale)),
        tone="mixed",
    )


def normalize_logo(data: bytes, content_type: str) -> Optional[NormalizedLogo]:
    if content_type == "image/svg+xml":
        return describe_svg(data)
    if content_type in ("image/png", "image/jpeg", "image/webp"):
        return normalize_raster(data, content_type)
    return None
