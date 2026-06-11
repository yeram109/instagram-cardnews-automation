from pathlib import Path

from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("output")
SLIDE_WIDTH = 1080
SLIDE_HEIGHT = 1350


def capture_slides(html_files: list[Path]) -> list[Path]:
    """Capture each HTML file as a 1080×1350 PNG using Playwright."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    output_paths: list[Path] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(
            viewport={"width": SLIDE_WIDTH, "height": SLIDE_HEIGHT},
            device_scale_factor=1,
        )
        page = context.new_page()

        for html_path in html_files:
            url = html_path.as_uri()
            page.goto(url, wait_until="networkidle")

            out_path = OUTPUT_DIR / html_path.with_suffix(".png").name
            page.screenshot(
                path=str(out_path),
                clip={"x": 0, "y": 0, "width": SLIDE_WIDTH, "height": SLIDE_HEIGHT},
            )
            output_paths.append(out_path)
            print(f"  캡처 완료: {out_path}")

        context.close()
        browser.close()

    return output_paths
