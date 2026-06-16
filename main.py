import argparse
import sys
import webbrowser
from pathlib import Path

from generator import generate_slide_content
from renderer import render_slides, HTML_DIR
from capture import capture_slides


def parse_args():
    parser = argparse.ArgumentParser(
        description="인스타그램 카드뉴스 자동화 파이프라인"
    )
    parser.add_argument(
        "--theme",
        choices=["tech", "activity", "trend"],
        default=None,
        help="카드뉴스 테마 (tech / activity / trend)",
    )
    parser.add_argument("--topic", default=None, help="카드뉴스 제목/주제")
    parser.add_argument("--text", default=None, help="슬라이드 생성에 사용할 원문 텍스트")
    parser.add_argument(
        "--images",
        default=None,
        help="이미지 폴더 경로 (없으면 text-only로 처리)",
    )
    parser.add_argument(
        "--capture-only",
        action="store_true",
        help="output/html/ 의 HTML을 그대로 PNG로 변환 (생성/렌더링 생략)",
    )
    return parser, parser.parse_args()


def open_preview(html_files: list[Path]) -> None:
    for html_path in html_files:
        webbrowser.open(html_path.as_uri())


def main():
    parser, args = parse_args()

    # --capture-only: output/html/ 의 HTML을 바로 PNG로 변환
    if args.capture_only:
        html_files = sorted(HTML_DIR.glob("slide_*.html"))
        if not html_files:
            print(
                f"[오류] {HTML_DIR} 에 HTML 파일이 없습니다. 먼저 카드뉴스를 생성하세요.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"[PNG 변환] {len(html_files)}개 슬라이드 캡처 중...")
        output_paths = capture_slides(html_files)
        print("\n완료! 생성된 파일:")
        for path in output_paths:
            print(f"  {path}")
        return

    # 일반 모드: --theme / --topic / --text 필수
    if not args.theme or not args.topic or not args.text:
        parser.error("--theme, --topic, --text 는 필수 인자입니다.")

    images_dir = Path(args.images) if args.images else None
    if images_dir and not images_dir.exists():
        print(f"[오류] 이미지 폴더를 찾을 수 없습니다: {images_dir}", file=sys.stderr)
        sys.exit(1)

    print("[1/3] Claude API로 슬라이드 텍스트 생성 중...")
    slide_data = generate_slide_content(topic=args.topic, text=args.text)
    slide_data["topic"] = args.topic

    round_num = 1
    while True:
        label = "재렌더링" if round_num > 1 else "렌더링"
        print(f"[2/3] HTML 슬라이드 {label} 중...")
        html_files = render_slides(
            slide_data=slide_data,
            theme=args.theme,
            images_dir=images_dir,
        )
        print(f"  → output/html/ 에 저장됨")

        open_preview(html_files)
        print("  → 브라우저에서 미리보기를 열었습니다\n")

        print("PNG로 변환하시겠습니까?")
        print("  [y] PNG 변환")
        print("  [r] 다시 생성 (Claude에게 피드백)")
        print("  [e] HTML 직접 수정 후 변환 (output/html/ 편집 뒤 엔터)")
        print("  [n] 취소")
        choice = input("선택: ").strip().lower()

        if choice == "y":
            break

        elif choice == "r":
            feedback = input("피드백 입력: ").strip()
            if not feedback:
                print("피드백을 입력해주세요.\n")
                continue
            print(f"\n[1/3] Claude API로 슬라이드 재생성 중...")
            slide_data = generate_slide_content(
                topic=args.topic,
                text=args.text,
                feedback=feedback,
                previous_result=slide_data,
            )
            slide_data["topic"] = args.topic
            round_num += 1

        elif choice == "e":
            print(f"\n  output/html/ 폴더의 HTML 파일을 수정하세요.")
            print(f"  수정 완료 후 엔터를 누르면 PNG로 변환합니다.")
            input("  [엔터] PNG 변환 시작...")
            html_files = sorted(HTML_DIR.glob("slide_*.html"))
            break

        elif choice == "n":
            print("취소했습니다. HTML 파일은 output/html/ 에 보관됩니다.")
            return

        else:
            print("y / r / e / n 중 하나를 입력하세요.\n")

    print("\n[3/3] Playwright PNG 캡처 중...")
    output_paths = capture_slides(html_files)

    print("\n완료! 생성된 파일:")
    for path in output_paths:
        print(f"  {path}")


if __name__ == "__main__":
    main()
