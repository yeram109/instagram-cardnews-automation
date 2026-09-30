"""로컬 웹 서버 실행: python run_web.py"""

import argparse
import threading
import webbrowser

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="카드뉴스 웹 UI 로컬 서버")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="브라우저 자동 실행 안 함")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print(f"카드뉴스 생성기: {url}")

    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    uvicorn.run("web.app:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
