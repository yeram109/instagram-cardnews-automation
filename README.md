# Instagram Card News Automation

Claude Code CLI + Playwright 기반 인스타그램 카드뉴스 자동 생성 파이프라인.

## 사전 요구 사항

- Python 3.10+
- [Claude Code CLI](https://github.com/anthropics/claude-code) (`npm install -g @anthropic-ai/claude-code`)
- Claude Code 로그인 완료 (`claude` 명령어 실행 가능 상태)

## 설치

```bash
pip install -r requirements.txt
playwright install chromium
```

API 키 설정 불필요 — Claude Code CLI 인증을 그대로 사용합니다.

## 사용법

```bash
python main.py --theme <테마> --topic <주제> --text <원문> [--images <이미지폴더>]
```

| 옵션 | 필수 | 설명 |
|------|------|------|
| `--theme` | ✓ | `tech` / `activity` / `trend` |
| `--topic` | ✓ | 카드뉴스 제목 / 주제 |
| `--text`  | ✓ | 슬라이드 생성에 사용할 원문 |
| `--images` | — | 이미지 폴더 경로 (없으면 텍스트 전용) |

### 예시

```bash
python main.py \
  --theme tech \
  --topic "AI가 바꾸는 개발자의 미래" \
  --text "최근 GitHub Copilot, ChatGPT 등 AI 코딩 도구가 급속히 보급되면서..."
```

결과물은 `output/` 폴더에 `slide_01.png` ~ `slide_06.png` 로 저장됩니다.

### 이미지 사용

이미지 파일을 슬라이드 인덱스에 맞게 이름을 지정하세요.

```
images/
  slide2.jpg   # 본문 슬라이드 2에 적용
  slide3.png   # 본문 슬라이드 3에 적용
```

이미지 비율에 따라 레이아웃이 자동 선택됩니다.

| 비율 (가로/세로) | 레이아웃 |
|---------|---------|
| >= 1.5 (가로형) | image-top |
| 0.85 ~ 1.5 (정방형) | image-split |
| < 0.85 (세로형) | image-blur-bg |

## 슬라이드 구성

| 슬라이드 | 종류 | 설명 |
|---------|------|------|
| 01 | 커버 | 훅 문구 + 부제목 |
| 02-04 | 본문 | 제목 + 본문 (이미지 선택) |
| 05 | 요약 | 핵심 요점 3가지 |
| 06 | CTA | 고정 (팔로우 유도) |

## 테마

| 테마 | 배경 | 포인트 컬러 |
|------|------|------------|
| `tech` | 딥 퍼플 #1A1A2E | #7F77DD |
| `activity` | 웜 코럴 #FFF8F5 | #D85A30 |
| `trend` | 나이트 블루 #0F1923 | #378ADD |

## 프로젝트 구조

```
.
├── main.py            # CLI 진입점
├── generator.py       # Claude Code CLI로 슬라이드 텍스트 생성
├── renderer.py        # Jinja2 HTML 렌더링 + 레이아웃 선택
├── capture.py         # Playwright PNG 캡처
├── templates/
│   ├── cover.html
│   ├── body.html
│   ├── summary.html
│   └── cta.html
├── themes/
│   ├── tech.css
│   ├── activity.css
│   └── trend.css
├── output/            # 생성된 PNG (자동 생성)
└── requirements.txt
```
