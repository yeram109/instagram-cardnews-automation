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
        (job.dir / "slide_data.json").write_text(
            json.dumps(slide_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        key = os.environ.get("UNSPLASH_ACCESS_KEY")
        if job.use_unsplash and key:
            job.step = "이미지 준비 중..."
            fetch_images(slide_data, key, images_dir=job.images_dir)

        job.step = "HTML 렌더링 중..."
        html_files = render_slides(
            slide_data=slide_data,
            theme=job.theme,
            images_dir=job.images_dir,
            html_dir=job.html_dir,
            theme_css_url=f"/static/themes/{job.theme}.css",
            image_url_of=lambda p: f"/runs/{job.id}/images/{p.name}",
        )

        job.slides = [
            {"name": p.stem, "html_url": f"/runs/{job.id}/html/{p.name}"}
            for p in html_files
        ]
        job.zip_name = None
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
