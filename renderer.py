from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from PIL import Image

TEMPLATES_DIR = Path(__file__).parent / "templates"
THEMES_DIR = Path(__file__).parent / "themes"
HTML_DIR = Path(__file__).parent / "output" / "html"

_SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _find_image(images_dir: Path, slide_index: int) -> Path | None:
    if images_dir is None:
        return None
    for ext in _SUPPORTED_EXTS:
        candidate = images_dir / f"slide{slide_index}{ext}"
        if candidate.exists():
            return candidate
    return None


# 이 비율 이상이면 가로형으로 본다 (1080px 폭 기준 자연 높이 720px)
WIDE_RATIO = 1.5


def _select_layout(image_path: Path | None) -> str:
    """Wide images get the band layout, everything else fills the card."""
    if image_path is None:
        return "text-only"

    with Image.open(image_path) as img:
        w, h = img.size

    return "image-band-blur" if w / h >= WIDE_RATIO else "image-blur-bg"


def render_slides(slide_data: dict, theme: str, images_dir: Path | None) -> list[Path]:
    """Render all slides to output/html/ and return list of file paths."""
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    # 이전 실행이 더 많은 슬라이드를 만들었을 수 있으므로 먼저 비운다
    for stale in HTML_DIR.glob("slide_*.html"):
        stale.unlink()

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    theme_css = (THEMES_DIR / f"{theme}.css").as_uri()

    html_files: list[Path] = []

    cover = slide_data.get("cover", {})
    cover_image = _find_image(images_dir, 1)
    cover_layout = _select_layout(cover_image)
    html = env.get_template("cover.html").render(
        theme_css=theme_css,
        topic=slide_data.get("topic", ""),
        hook=cover.get("hook", ""),
        subtitle=cover.get("subtitle", ""),
        layout=cover_layout,
        image_path=cover_image.resolve().as_uri() if cover_image else "",
    )
    p = HTML_DIR / "slide_01.html"
    p.write_text(html, encoding="utf-8")
    html_files.append(p)

    last_body_index = 4
    for slide in slide_data.get("slides", []):
        idx = slide.get("index", 2)
        last_body_index = max(last_body_index, idx)
        image_path = _find_image(images_dir, idx)
        layout = _select_layout(image_path)

        html = env.get_template("body.html").render(
            theme_css=theme_css,
            slide_index=idx,
            title=slide.get("title", ""),
            body=slide.get("body", ""),
            layout=layout,
            image_path=image_path.resolve().as_uri() if image_path else "",
        )
        p = HTML_DIR / f"slide_{idx:02d}.html"
        p.write_text(html, encoding="utf-8")
        html_files.append(p)

    summary_index = last_body_index + 1
    cta_index = last_body_index + 2

    summary = slide_data.get("summary", {})
    html = env.get_template("summary.html").render(
        theme_css=theme_css,
        slide_index=summary_index,
        points=summary.get("points", []),
    )
    p = HTML_DIR / f"slide_{summary_index:02d}.html"
    p.write_text(html, encoding="utf-8")
    html_files.append(p)

    html = env.get_template("cta.html").render(
        theme_css=theme_css,
        slide_index=cta_index,
    )
    p = HTML_DIR / f"slide_{cta_index:02d}.html"
    p.write_text(html, encoding="utf-8")
    html_files.append(p)

    return html_files
