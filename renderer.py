from pathlib import Path
from typing import Callable

from jinja2 import Environment, FileSystemLoader
from PIL import Image

TEMPLATES_DIR = Path(__file__).parent / "templates"
THEMES_DIR = Path(__file__).parent / "themes"
HTML_DIR = Path(__file__).parent / "output" / "html"

_SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _find_image(images_dir: Path | None, slide_index: int) -> Path | None:
    if images_dir is None:
        return None
    for ext in _SUPPORTED_EXTS:
        candidate = images_dir / f"slide{slide_index}{ext}"
        if candidate.exists():
            return candidate
    return None


# 이 비율 이상이면 가로형으로 본다 (1080px 폭 기준 자연 높이 720px)
WIDE_RATIO = 1.5


# EXIF orientation 5~8 은 90°/270° 회전이라 브라우저가 가로세로를 바꿔 그린다.
# 휴대폰 세로 사진은 가로로 저장되고 이 태그만 붙는 경우가 많다.
_SWAPPED_ORIENTATIONS = {5, 6, 7, 8}
_ORIENTATION_TAG = 0x0112


def _displayed_size(img: Image.Image) -> tuple[int, int]:
    """Return the size the browser will actually render, honoring EXIF orientation."""
    w, h = img.size
    if img.getexif().get(_ORIENTATION_TAG) in _SWAPPED_ORIENTATIONS:
        return h, w
    return w, h


def _select_layout(image_path: Path | None) -> str:
    """Wide images get the band layout, everything else fills the card."""
    if image_path is None:
        return "text-only"

    with Image.open(image_path) as img:
        w, h = _displayed_size(img)

    return "image-band-blur" if w / h >= WIDE_RATIO else "image-blur-bg"


def _file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def render_slides(
    slide_data: dict,
    theme: str,
    images_dir: Path | None,
    html_dir: Path = HTML_DIR,
    theme_css_url: str | None = None,
    image_url_of: Callable[[Path], str] | None = None,
) -> list[Path]:
    """Render all slides to ``html_dir`` and return list of file paths.

    CLI 모드는 기본값(file:// URI)을 그대로 쓰고, 웹 모드는 http 경로를 넘긴다.
    브라우저가 http 문서 안에서 file:// 리소스를 차단하기 때문이다.
    """
    html_dir.mkdir(parents=True, exist_ok=True)

    # 이전 실행이 더 많은 슬라이드를 만들었을 수 있으므로 먼저 비운다
    for stale in html_dir.glob("slide_*.html"):
        stale.unlink()

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    if theme_css_url is None:
        theme_css_url = _file_uri(THEMES_DIR / f"{theme}.css")
    to_url = image_url_of or _file_uri

    html_files: list[Path] = []

    cover = slide_data.get("cover", {})
    cover_image = _find_image(images_dir, 1)
    cover_layout = _select_layout(cover_image)
    html = env.get_template("cover.html").render(
        theme_css=theme_css_url,
        topic=slide_data.get("topic", ""),
        hook=cover.get("hook", ""),
        subtitle=cover.get("subtitle", ""),
        layout=cover_layout,
        image_path=to_url(cover_image) if cover_image else "",
    )
    p = html_dir / "slide_01.html"
    p.write_text(html, encoding="utf-8")
    html_files.append(p)

    last_body_index = 4
    for slide in slide_data.get("slides", []):
        idx = slide.get("index", 2)
        last_body_index = max(last_body_index, idx)
        image_path = _find_image(images_dir, idx)
        layout = _select_layout(image_path)

        html = env.get_template("body.html").render(
            theme_css=theme_css_url,
            slide_index=idx,
            title=slide.get("title", ""),
            body=slide.get("body", ""),
            layout=layout,
            image_path=to_url(image_path) if image_path else "",
        )
        p = html_dir / f"slide_{idx:02d}.html"
        p.write_text(html, encoding="utf-8")
        html_files.append(p)

    summary_index = last_body_index + 1
    cta_index = last_body_index + 2

    summary = slide_data.get("summary", {})
    html = env.get_template("summary.html").render(
        theme_css=theme_css_url,
        slide_index=summary_index,
        points=summary.get("points", []),
    )
    p = html_dir / f"slide_{summary_index:02d}.html"
    p.write_text(html, encoding="utf-8")
    html_files.append(p)

    html = env.get_template("cta.html").render(
        theme_css=theme_css_url,
        slide_index=cta_index,
    )
    p = html_dir / f"slide_{cta_index:02d}.html"
    p.write_text(html, encoding="utf-8")
    html_files.append(p)

    return html_files
