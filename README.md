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
| `--theme` | ✓ | `info` / `life` / `tech` |
| `--topic` | ✓ | 카드뉴스 제목 / 주제 |
| `--text`  | ✓ | 슬라이드 생성에 사용할 원문 |
| `--images` | — | 이미지 폴더 경로 (없으면 텍스트 전용) |
| `--capture-only` | — | `output/html/` 의 HTML을 바로 PNG로 변환 |

### 예시

```bash
python main.py \
  --theme info \
  --topic "AI가 바꾸는 개발자의 미래" \
  --text "최근 GitHub Copilot, ChatGPT 등 AI 코딩 도구가 급속히 보급되면서..."
```

## 실행 흐름

명령어를 실행하면 세 단계로 진행되며, HTML 미리보기 확인 후 PNG 변환 여부를 선택할 수 있습니다.

```
[1/3] Claude API로 슬라이드 텍스트 생성 중...
[2/3] HTML 슬라이드 렌더링 중...
  → output/html/ 에 저장됨
  → 브라우저에서 미리보기를 열었습니다

PNG로 변환하시겠습니까?
  [y] PNG 변환
  [r] 다시 생성 (Claude에게 피드백)
  [e] HTML 직접 수정 후 변환
  [n] 취소
```

| 선택 | 동작 |
|------|------|
| `y` | PNG 변환 후 `output/` 에 저장 |
| `r` | 피드백을 입력하면 Claude가 반영해서 재생성, 미리보기 다시 열림 (반복 가능) |
| `e` | `output/html/` 의 HTML 파일을 직접 편집 후 엔터를 누르면 PNG 변환 |
| `n` | HTML은 `output/html/` 에 보관, PNG 변환 없이 종료 |

### HTML 수정 후 나중에 PNG 변환

`output/html/` 의 HTML을 수정해둔 상태에서 언제든 PNG로 변환할 수 있습니다.

```bash
python main.py --capture-only
```

## 이미지 사용

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

원문 분량에 따라 전체 슬라이드 수가 6~8장으로 자동 조정됩니다.

| 슬라이드 | 종류 | 설명 |
|---------|------|------|
| 01 | 커버 | 훅 문구 + 부제목 |
| 02-04 / 02-05 / 02-06 | 본문 | 제목 + 본문, 원문 분량에 따라 3~5장 |
| N | 요약 | 핵심 요점 3가지 |
| N+1 | CTA | 고정 (팔로우 유도) |

| 본문 장수 | 전체 슬라이드 수 |
|----------|--------------|
| 3장 (02~04) | 6장 |
| 4장 (02~05) | 7장 |
| 5장 (02~06) | 8장 |

## 테마

| 테마 | 배경 | 포인트 컬러 |
|------|------|------------|
| `info` | 딥 퍼플 #1A1A2E | #7F77DD |
| `life` | 웜 코럴 #FFF8F5 | #D85A30 |
| `tech` | 나이트 블루 #0F1923 | #378ADD |

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
│   ├── info.css
│   ├── life.css
│   └── tech.css
├── output/
│   ├── html/          # 렌더링된 HTML 중간 결과물
│   └── slide_01.png   # 최종 PNG (자동 생성)
└── requirements.txt
```
