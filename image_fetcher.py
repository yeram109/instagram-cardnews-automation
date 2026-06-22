import json
import urllib.parse
import urllib.request
from pathlib import Path

UNSPLASH_API = "https://api.unsplash.com/search/photos"
IMAGES_DIR = Path(__file__).parent / "images"

_SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _existing(slide_index: int) -> bool:
    """Return True if a user-provided image already exists for this slide."""
    for ext in _SUPPORTED_EXTS:
        if (IMAGES_DIR / f"slide{slide_index}{ext}").exists():
            return True
    return False


def fetch_images(slide_data: dict, access_key: str) -> Path:
    """Download Unsplash images for slides that have image_query and no existing file."""
    IMAGES_DIR.mkdir(exist_ok=True)

    cover = slide_data.get("cover", {})
    if query := cover.get("image_query"):
        if _existing(1):
            print(f"  slide1 ← 직접 추가한 이미지 사용")
        else:
            _download(query, access_key, IMAGES_DIR / "slide1.jpg")

    for slide in slide_data.get("slides", []):
        idx = slide.get("index")
        if not (query := slide.get("image_query")) or not idx:
            continue
        if _existing(idx):
            print(f"  slide{idx} ← 직접 추가한 이미지 사용")
        else:
            _download(query, access_key, IMAGES_DIR / f"slide{idx}.jpg")

    return IMAGES_DIR


def _download(query: str, access_key: str, dest: Path) -> None:
    params = urllib.parse.urlencode({
        "query": query,
        "per_page": 1,
        "orientation": "portrait",
        "content_filter": "high",
    })
    req = urllib.request.Request(
        f"{UNSPLASH_API}?{params}",
        headers={"Authorization": f"Client-ID {access_key}"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"  [경고] 이미지 검색 실패 ({query}): {e}")
        return

    results = data.get("results", [])
    if not results:
        print(f"  [경고] 검색 결과 없음: '{query}' → 해당 슬라이드 텍스트 전용으로 처리")
        return

    img_url = results[0]["urls"]["regular"]
    try:
        urllib.request.urlretrieve(img_url, dest)
        print(f"  {dest.name} ← Unsplash '{query}'")
    except Exception as e:
        print(f"  [경고] 이미지 다운로드 실패 ({query}): {e}")
