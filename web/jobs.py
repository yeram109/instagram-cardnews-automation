"""잡 저장소 + 워커 스레드.

로컬 1인용이라 인메모리 dict 로 충분하다. 다만 잡별 산출물은
runs/<job_id>/ 아래로 격리해 요청이 겹쳐도 서로 덮어쓰지 않게 한다.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from generator import generate_slide_content
from image_fetcher import fetch_images
from renderer import render_slides
from capture import capture_slides

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "runs"

# Playwright 캡처는 sync API 라 asyncio 루프 안에서 돌 수 없다 → 별도 스레드에서만 실행한다.
# 워커 1개로 직렬화해 Chromium 인스턴스가 여러 개 뜨는 것도 막는다.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cardnews")
_jobs: dict[str, "Job"] = {}
_lock = threading.Lock()

RUN_TTL_SECONDS = 24 * 60 * 60


@dataclass
class Job:
    id: str
    theme: str
    topic: str
    text: str
    use_unsplash: bool = False
    status: str = "pending"  # pending | running | ready | exporting | error
    step: str = "대기 중"
    progress: str = ""
    slide_data: dict | None = None
    slides: list[dict] = field(default_factory=list)
    zip_name: str | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)

    @property
    def dir(self) -> Path:
        return RUNS_DIR / self.id

    @property
    def images_dir(self) -> Path:
        return self.dir / "images"

    @property
    def html_dir(self) -> Path:
        return self.dir / "html"

    @property
    def png_dir(self) -> Path:
        return self.dir / "png"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "step": self.step,
            "progress": self.progress,
            "theme": self.theme,
            "topic": self.topic,
            "slides": self.slides,
            "text": editable_text(self),
            "zip_url": f"/runs/{self.id}/{self.zip_name}" if self.zip_name else None,
            "error": self.error,
        }


def create_job(theme: str, topic: str, text: str, use_unsplash: bool) -> Job:
    job = Job(id=uuid.uuid4().hex[:12], theme=theme, topic=topic, text=text,
              use_unsplash=use_unsplash)
    job.images_dir.mkdir(parents=True, exist_ok=True)
    job.html_dir.mkdir(parents=True, exist_ok=True)
    with _lock:
        _jobs[job.id] = job
    return job


def discard_job(job: Job) -> None:
    """생성 요청이 검증에 걸렸을 때 빈 작업 폴더를 남기지 않는다."""
    with _lock:
        _jobs.pop(job.id, None)
    shutil.rmtree(job.dir, ignore_errors=True)


def get_job(job_id: str) -> Job | None:
    with _lock:
        return _jobs.get(job_id)


def submit_generate(job: Job, feedback: str = "") -> None:
    job.status = "running"
    job.step = "슬라이드 텍스트 생성 중..."
    job.progress = ""   # 직전 캡처의 "8/8" 이 남아 진행 표시에 섞이지 않게 한다
    job.error = None
    _executor.submit(_run_generate, job, feedback)


def submit_export(job: Job, base_url: str) -> None:
    job.status = "exporting"
    job.step = "PNG 캡처 중..."
    job.progress = ""
    job.error = None
    _executor.submit(_run_export, job, base_url)


def _save_slide_data(job: Job) -> None:
    (job.dir / "slide_data.json").write_text(
        json.dumps(job.slide_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def render_job(job: Job) -> None:
    """Render job.slide_data to HTML and refresh job.slides."""
    slide_data = job.slide_data or {}
    html_files = render_slides(
        slide_data=slide_data,
        theme=job.theme,
        images_dir=job.images_dir,
        html_dir=job.html_dir,
        theme_css_url=f"/static/themes/{job.theme}.css",
        image_url_of=lambda p: f"/runs/{job.id}/images/{p.name}",
    )

    # render_slides 가 붙이는 순서: 커버 → 본문(slides 순서) → 요약 → CTA
    kinds: list[tuple[str, int | None]] = [("cover", None)]
    kinds += [("body", s.get("index")) for s in slide_data.get("slides", [])]
    kinds += [("summary", None), ("cta", None)]
    if len(kinds) != len(html_files):  # 렌더러 구조가 바뀌면 조용히 틀어지지 않도록
        raise RuntimeError(
            f"슬라이드 종류({len(kinds)})와 렌더된 파일 수({len(html_files)})가 다릅니다."
        )

    job.slides = [
        {
            "name": path.stem,
            "html_url": f"/runs/{job.id}/html/{path.name}",
            "kind": kind,
            "index": index,
        }
        for path, (kind, index) in zip(html_files, kinds)
    ]
    job.zip_name = None  # 텍스트가 바뀌었으니 직전 PNG·ZIP 은 더 이상 맞지 않는다


def editable_text(job: Job) -> dict:
    """Text fields the browser can edit. CTA 문구는 템플릿에 고정돼 있어 제외."""
    data = job.slide_data or {}
    cover = data.get("cover", {})
    return {
        "topic": data.get("topic", job.topic),
        "cover": {"hook": cover.get("hook", ""), "subtitle": cover.get("subtitle", "")},
        "slides": [
            {
                "index": s.get("index"),
                "title": s.get("title", ""),
                "body": s.get("body", ""),
            }
            for s in data.get("slides", [])
        ],
        "summary": {"points": list(data.get("summary", {}).get("points", []))},
    }


def _as_text(value, where: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{where} 는 문자열이어야 합니다.")
    return value.strip()


def apply_text_edit(job: Job, payload: dict) -> None:
    """Merge edited text into slide_data and re-render. Claude 는 호출하지 않는다."""
    if not isinstance(payload, dict):
        raise ValueError("요청 본문이 올바르지 않습니다.")
    if not job.slide_data:
        raise ValueError("아직 생성된 슬라이드가 없습니다.")

    data = job.slide_data

    if (topic := payload.get("topic")) is not None:
        data["topic"] = _as_text(topic, "topic")
        job.topic = data["topic"]

    if (cover := payload.get("cover")) is not None:
        if not isinstance(cover, dict):
            raise ValueError("cover 는 객체여야 합니다.")
        target = data.setdefault("cover", {})
        for field in ("hook", "subtitle"):
            if (value := cover.get(field)) is not None:
                target[field] = _as_text(value, f"cover.{field}")

    if (slides := payload.get("slides")) is not None:
        if not isinstance(slides, list):
            raise ValueError("slides 는 배열이어야 합니다.")
        # index 로 짝을 맞춰 image_query 같은 다른 키는 건드리지 않는다
        by_index = {s.get("index"): s for s in data.get("slides", [])}
        for edited in slides:
            if not isinstance(edited, dict):
                raise ValueError("slides 의 각 항목은 객체여야 합니다.")
            target = by_index.get(edited.get("index"))
            if target is None:
                continue
            for field in ("title", "body"):
                if (value := edited.get(field)) is not None:
                    target[field] = _as_text(value, f"slides[].{field}")

    if (summary := payload.get("summary")) is not None:
        if not isinstance(summary, dict):
            raise ValueError("summary 는 객체여야 합니다.")
        raw = summary.get("points", [])
        # 문자열을 그냥 순회하면 글자 단위로 쪼개진다
        if not isinstance(raw, list):
            raise ValueError("summary.points 는 배열이어야 합니다.")
        points = [t for p in raw if (t := _as_text(p, "summary.points[]"))]
        data.setdefault("summary", {})["points"] = points

    _save_slide_data(job)
    render_job(job)


def _run_generate(job: Job, feedback: str) -> None:
    try:
        previous = job.slide_data if feedback else None
        slide_data = generate_slide_content(
            topic=job.topic,
            text=job.text,
            feedback=feedback,
            previous_result=previous,
        )
        slide_data["topic"] = job.topic
        job.slide_data = slide_data
        _save_slide_data(job)

        key = os.environ.get("UNSPLASH_ACCESS_KEY")
        if job.use_unsplash and key:
            job.step = "이미지 준비 중..."
            fetch_images(slide_data, key, images_dir=job.images_dir)

        job.step = "HTML 렌더링 중..."
        render_job(job)
        job.step = "완료"
        job.status = "ready"
    except Exception as exc:  # 워커 스레드라 예외를 잡아 잡 상태로 옮긴다
        job.error = f"{type(exc).__name__}: {exc}"
        job.step = "실패"
        job.status = "error"


def _run_export(job: Job, base_url: str) -> None:
    try:
        html_files = sorted(job.html_dir.glob("slide_*.html"))
        if not html_files:
            raise RuntimeError("렌더링된 HTML이 없습니다.")

        # 슬라이드 수가 줄어든 재생성 뒤에는 이전 PNG가 남을 수 있다
        for stale in job.png_dir.glob("slide_*.png"):
            stale.unlink()

        def on_progress(done: int, total: int) -> None:
            job.progress = f"{done}/{total}"

        # 웹 모드 HTML은 CSS·이미지를 http 경로로 참조하므로 file:// 로 열면 깨진다
        png_paths = capture_slides(
            html_files,
            output_dir=job.png_dir,
            on_progress=on_progress,
            url_of=lambda p: f"{base_url}/runs/{job.id}/html/{p.name}",
        )

        zip_name = f"cardnews_{_safe_name(job.topic)}.zip"
        zip_path = job.dir / zip_name
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for png in png_paths:
                zf.write(png, arcname=png.name)

        job.zip_name = zip_name
        job.step = "완료"
        job.status = "ready"
    except Exception as exc:
        job.error = f"{type(exc).__name__}: {exc}"
        job.step = "실패"
        job.status = "error"


def _safe_name(topic: str) -> str:
    # isalnum() 은 한글도 True 라 한국어 제목이 그대로 남는다
    keep = [c for c in topic.strip() if c.isalnum() or c in " _-"]
    name = "".join(keep).strip().replace(" ", "_")[:40]
    return name or "slides"


def cleanup_old_runs() -> None:
    """서버 시작 시 오래된 작업 폴더를 정리한다."""
    if not RUNS_DIR.exists():
        return
    cutoff = time.time() - RUN_TTL_SECONDS
    for entry in RUNS_DIR.iterdir():
        if entry.is_dir() and entry.stat().st_mtime < cutoff:
            shutil.rmtree(entry, ignore_errors=True)
