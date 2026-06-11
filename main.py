import argparse
import sys
from pathlib import Path

from generator import generate_slide_content
from renderer import render_slides
from capture import capture_slides


def parse_args():
    parser = argparse.ArgumentParser(
        description="인스타그램 카드뉴스 자동화 파이프라인"
    )
    parser.add_argument(
        "--theme",
        choices=["tech", "activity", "trend"],
        required=True,
        help="카드뉴스 테마 (tech / activity / trend)",
    )
    parser.add_argument("--topic", required=True, help="카드뉴스 제목/주제")
    parser.add_argument("--text", required=True, help="슬라이드 생성에 사용할 원문 텍스트")
    parser.add_argument(
        "--images",
        default=None,
        help="이미지 폴더 경로 (없으면 text-only로 처리)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    images_dir = Path(args.images) if args.images else None
    if images_dir and not images_dir.exists():
        print(f"[오류] 이미지 폴더를 찾을 수 없습니다: {images_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"[1/3] Claude API로 슬라이드 텍스트 생성 중...")
    slide_data = generate_slide_content(topic=args.topic, text=args.text)
    slide_data["topic"] = args.topic

    print(f"[2/3] HTML 슬라이드 렌더링 중...")
    html_files = render_slides(
        slide_data=slide_data,
        theme=args.theme,
        images_dir=images_dir,
    )

    print(f"[3/3] Playwright PNG 캡처 중...")
    output_paths = capture_slides(html_files)

    print(f"\n완료! 생성된 파일:")
    for path in output_paths:
        print(f"  {path}")


if __name__ == "__main__":
    main()
