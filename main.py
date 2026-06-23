import argparse
import json
import os
import sys
import webbrowser
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from generator import generate_slide_content
from image_fetcher import fetch_images, IMAGES_DIR
from renderer import render_slides, HTML_DIR
from capture import capture_slides

SLIDE_DATA_PATH = Path("output/slide_data.json")


def parse_args():
    parser = argparse.ArgumentParser(
        description="인스타그램 카드뉴스 자동화 파이프라인"
    )
    parser.add_argument(
        "--theme",
        choices=["info", "life", "tech"],
        default=None,
        help="카드뉴스 테마 (tech / activity / trend)",
    )
    parser.add_argument("--topic", default=None, help="카드뉴스 제목/주제")
    parser.add_argument("--text", default=None, help="슬라이드 생성에 사용할 원문 텍스트")
    parser.add_argument(
        "--unsplash-key",
        default=os.environ.get("UNSPLASH_ACCESS_KEY"),
        help="Unsplash API access key (또는 환경변수 UNSPLASH_ACCESS_KEY)",
    )
    parser.add_argument(
        "--render-only",
        action="store_true",
        help="output/slide_data.json 으로 HTML 재렌더링 (텍스트/이미지 생성 생략)",
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


def save_slide_data(slide_data: dict) -> None:
    SLIDE_DATA_PATH.parent.mkdir(exist_ok=True)
    SLIDE_DATA_PATH.write_text(json.dumps(slide_data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_slide_data() -> dict:
    if not SLIDE_DATA_PATH.exists():
        print(f"[오류] {SLIDE_DATA_PATH} 파일이 없습니다. 먼저 카드뉴스를 생성하세요.", file=sys.stderr)
        sys.exit(1)
    return json.loads(SLIDE_DATA_PATH.read_text(encoding="utf-8"))


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

    # --render-only: 저장된 slide_data로 HTML 재렌더링
    if args.render_only:
        if not args.theme:
            parser.error("--render-only 사용 시 --theme 는 필수입니다.")
        slide_data = load_slide_data()
        images_dir = IMAGES_DIR if IMAGES_DIR.exists() else None
        print(f"[2/3] HTML 슬라이드 재렌더링 중... (테마: {args.theme})")
        html_files = render_slides(slide_data=slide_data, theme=args.theme, images_dir=images_dir)
        print(f"  → output/html/ 에 저장됨")
        open_preview(html_files)
        print("  → 브라우저에서 미리보기를 열었습니다\n")
        input("  [엔터] PNG 변환 시작...")
        print("\n[3/3] Playwright PNG 캡처 중...")
        output_paths = capture_slides(html_files)
        print("\n완료! 생성된 파일:")
        for path in output_paths:
            print(f"  {path}")
        return

    # 일반 모드: --theme / --topic / --text 필수
    if not args.theme or not args.topic or not args.text:
        parser.error("--theme, --topic, --text 는 필수 인자입니다.")

    print("[1/3] Claude API로 슬라이드 텍스트 생성 중...")
    slide_data = generate_slide_content(topic=args.topic, text=args.text)
    slide_data["topic"] = args.topic
    save_slide_data(slide_data)

    if args.unsplash_key:
        print("[1.5/3] 이미지 준비 중... (images/ 직접 추가 파일 우선, 나머지 Unsplash 다운로드)")
        images_dir = fetch_images(slide_data, args.unsplash_key)
    elif IMAGES_DIR.exists():
        print(f"  [참고] images/ 폴더의 파일 사용 (Unsplash 키 없음)")
        images_dir = IMAGES_DIR
    else:
        print("  [참고] 이미지 없음 → 텍스트 전용으로 처리")
        images_dir = None

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
            save_slide_data(slide_data)
            if args.unsplash_key:
                print("[1.5/3] 이미지 재준비 중...")
                images_dir = fetch_images(slide_data, args.unsplash_key)
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
