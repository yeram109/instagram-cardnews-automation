import json
import os
import shutil
import subprocess
import sys

SYSTEM_PROMPT = """당신은 인스타그램 카드뉴스 콘텐츠 작가입니다.
입력된 원문을 바탕으로 5~6장 분량의 슬라이드 텍스트를 JSON으로 생성하세요.

규칙:
- 커버 훅 문구는 15자 이내, 호기심을 유발해야 합니다
- 본문 각 슬라이드는 제목 + 3~4줄 이내 본문으로 구성합니다
- 정리 슬라이드는 핵심 요점 3가지를 간결하게 작성합니다
- JSON만 반환하고, 마크다운 코드블록(```) 없이 순수 JSON만 출력하세요"""

OUTPUT_FORMAT = """{
  "cover": {
    "hook": "커버 훅 문구 (15자 이내, 호기심 유발)",
    "subtitle": "부제목"
  },
  "slides": [
    {
      "index": 2,
      "title": "슬라이드 제목",
      "body": "본문 내용 (3~4줄 이내)"
    }
  ],
  "summary": {
    "points": ["요점 1", "요점 2", "요점 3"]
  }
}"""


def _claude_cmd() -> list[str]:
    claude_path = shutil.which("claude")
    if not claude_path:
        raise RuntimeError(
            "claude CLI를 찾을 수 없습니다.\n"
            "npm install -g @anthropic-ai/claude-code 로 설치하세요."
        )
    if sys.platform == "win32":
        return ["cmd", "/c", claude_path]
    return [claude_path]


def generate_slide_content(topic: str, text: str) -> dict:
    """Claude Code CLI를 통해 슬라이드 텍스트를 생성한다."""
    # --system-prompt 인자에 멀티라인 한국어를 넣으면 cmd.exe가 인자를 잘못 파싱해
    # --output-format json이 무시되므로, 시스템 지시사항을 stdin에 포함시킨다
    user_message = f"""[지시사항]
{SYSTEM_PROMPT}

[요청]
주제: {topic}

원문:
{text}

위 내용을 바탕으로 인스타그램 카드뉴스 슬라이드 텍스트를 아래 JSON 형식으로 생성하세요.
slides 배열은 index 2~4 (본문 3장)로 구성하세요.

출력 형식:
{OUTPUT_FORMAT}"""

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"

    result = subprocess.run(
        _claude_cmd() + ["--output-format", "json"],
        input=user_message.encode("utf-8"),
        capture_output=True,
        env=env,
    )

    # 출력 디코딩: UTF-8 우선, 실패 시 시스템 인코딩으로 폴백
    try:
        stdout = result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        stdout = result.stdout.decode(sys.getfilesystemencoding(), errors="replace")

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Claude CLI 오류 (returncode={result.returncode}):\n{stderr}"
        )

    if not stdout.strip():
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"Claude CLI 출력이 비어있습니다.\nstderr: {stderr}")

    cli_output = json.loads(stdout)
    raw = cli_output.get("result", "").strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude 응답이 유효한 JSON이 아닙니다: {e}\n응답 내용:\n{raw}")
