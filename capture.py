from pathlib import Path

from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("output")
SLIDE_WIDTH = 1080
SLIDE_HEIGHT = 1350


def capture_slides(
    html_files: list[Path],
    output_dir: Path = OUTPUT_DIR,
    on_progress=None,
    url_of=None,
) -> list[Path]:
    """Capture each HTML file as a 1080×1350 PNG using Playwright.

    ``url_of`` 는 HTML 파일을 어떤 URL로 열지 정한다. 기본은 file:// URI 이지만,
    웹 모드가 렌더한 HTML은 CSS·이미지를 http 경로로 참조하므로 http URL을 넘겨야 한다.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    output_paths: list[Path] = []
    total = len(html_files)
    to_url = url_of or (lambda path: path.resolve().as_uri())

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(
            viewport={"width": SLIDE_WIDTH, "height": SLIDE_HEIGHT},
            device_scale_factor=1,
        )
        page = context.new_page()

        for i, html_path in enumerate(html_files, start=1):
            url = to_url(html_path)
            page.goto(url, wait_until="networkidle")

            out_path = output_dir / html_path.with_suffix(".png").name
            page.screenshot(
                path=str(out_path),
                clip={"x": 0, "y": 0, "width": SLIDE_WIDTH, "height": SLIDE_HEIGHT},
            )
            output_paths.append(out_path)
            if on_progress:
                on_progress(i, total)
            else:
                print(f"  캡처 완료: {out_path}")

        context.close()
        browser.close()

    return output_paths
