import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from PIL import Image

TEMPLATES_DIR = Path(__file__).parent / "templates"
THEMES_DIR = Path(__file__).parent / "themes"

_SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _find_image(images_dir: Path, slide_index: int) -> Path | None:
    """Return the image path for a given slide index, or None."""
    if images_dir is None:
        return None
    for ext in _SUPPORTED_EXTS:
        candidate = images_dir / f"slide{slide_index}{ext}"
        if candidate.exists():
            return candidate
    return None


def _select_layout(image_path: Path | None) -> str:
    """Choose layout based on image presence and aspect ratio."""
    if image_path is None:
        return "text-only"

    with Image.open(image_path) as img:
        w, h = img.size

    ratio = w / h

    if ratio >= 1.5:
        return "image-top"
    elif ratio >= 0.85:
        return "image-split"
    else:
        return "image-blur-bg"


def render_slides(slide_data: dict, theme: str, images_dir: Path | None) -> list[Path]:
    """Render all slides to HTML files and return list of file paths."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    theme_css = (THEMES_DIR / f"{theme}.css").as_uri()

    out_dir = Path(tempfile.mkdtemp(prefix="cardnews_"))
    html_files: list[Path] = []

    # Slide 1: cover
    cover = slide_data.get("cover", {})
    html = env.get_template("cover.html").render(
        theme_css=theme_css,
        topic=slide_data.get("topic", ""),
        hook=cover.get("hook", ""),
        subtitle=cover.get("subtitle", ""),
    )
    p = out_dir / "slide_01.html"
    p.write_text(html, encoding="utf-8")
    html_files.append(p)

    # Slides 2-4: body
    for slide in slide_data.get("slides", []):
        idx = slide.get("index", 2)
        image_path = _find_image(images_dir, idx)
        layout = _select_layout(image_path)

        html = env.get_template("body.html").render(
            theme_css=theme_css,
            slide_index=idx,
            title=slide.get("title", ""),
            body=slide.get("body", ""),
            layout=layout,
            image_path=image_path.as_uri() if image_path else "",
        )
        p = out_dir / f"slide_{idx:02d}.html"
        p.write_text(html, encoding="utf-8")
        html_files.append(p)

    # Slide 5: summary
    summary = slide_data.get("summary", {})
    html = env.get_template("summary.html").render(
        theme_css=theme_css,
        points=summary.get("points", []),
    )
    p = out_dir / "slide_05.html"
    p.write_text(html, encoding="utf-8")
    html_files.append(p)

    # Slide 6: CTA (fixed)
    html = env.get_template("cta.html").render(theme_css=theme_css)
    p = out_dir / "slide_06.html"
    p.write_text(html, encoding="utf-8")
    html_files.append(p)

    return html_files
