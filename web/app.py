"""로컬 카드뉴스 웹 서버 (FastAPI)."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

load_dotenv()

from web import jobs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
THEMES = ["info", "life", "tech"]
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024

# StaticFiles 는 마운트 시점에 디렉터리가 있어야 하므로 먼저 만든다
jobs.RUNS_DIR.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    jobs.cleanup_old_runs()
    yield


app = FastAPI(title="카드뉴스 생성기", lifespan=lifespan)


# 렌더된 HTML이 참조하는 테마 CSS
app.mount("/static/themes", StaticFiles(directory=str(ROOT / "themes")), name="themes")
# 잡 산출물 (HTML · 업로드 이미지 · PNG · ZIP)
app.mount("/runs", StaticFiles(directory=str(jobs.RUNS_DIR)), name="runs")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/jobs")
async def create_job(
    theme: str = Form(...),
    topic: str = Form(...),
    text: str = Form(...),
    use_unsplash: str = Form("false"),
    images: list[UploadFile] = File(default=[]),
) -> JSONResponse:
    if theme not in THEMES:
        raise HTTPException(400, f"테마는 {', '.join(THEMES)} 중 하나여야 합니다.")
    if not topic.strip():
        raise HTTPException(400, "제목을 입력해주세요.")
    if not text.strip():
        raise HTTPException(400, "본문 텍스트를 입력해주세요.")

    job = jobs.create_job(
        theme=theme,
        topic=topic.strip(),
        text=text.strip(),
        use_unsplash=use_unsplash.lower() == "true",
    )

    # 업로드 순서대로 slide1(커버) → slide2 → ... 로 매핑한다
    try:
        slot = 1
        for upload in images:
            if not upload.filename:
                continue
            ext = Path(upload.filename).suffix.lower()
            if ext not in ALLOWED_EXTS:
                raise HTTPException(400, f"지원하지 않는 이미지 형식입니다: {upload.filename}")
            data = await upload.read()
            if len(data) > MAX_IMAGE_BYTES:
                raise HTTPException(400, f"이미지가 너무 큽니다 (20MB 초과): {upload.filename}")
            dest = job.images_dir / f"slide{slot}{ext}"
            dest.write_bytes(data)
            try:
                with Image.open(dest) as img:
                    img.verify()
            except (UnidentifiedImageError, OSError):
                raise HTTPException(400, f"이미지를 읽을 수 없습니다: {upload.filename}")
            slot += 1
    except HTTPException:
        jobs.discard_job(job)
        raise

    jobs.submit_generate(job)
    return JSONResponse({"job_id": job.id})


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> JSONResponse:
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(404, "존재하지 않는 작업입니다.")
    return JSONResponse(job.to_dict())


@app.post("/api/jobs/{job_id}/feedback")
def regenerate(job_id: str, feedback: str = Form(...)) -> JSONResponse:
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(404, "존재하지 않는 작업입니다.")
    if job.status in ("running", "exporting"):
        raise HTTPException(409, "이미 작업이 진행 중입니다.")
    if not feedback.strip():
        raise HTTPException(400, "피드백 내용을 입력해주세요.")
    jobs.submit_generate(job, feedback=feedback.strip())
    return JSONResponse({"job_id": job.id})


@app.post("/api/jobs/{job_id}/export")
def export(job_id: str, request: Request) -> JSONResponse:
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(404, "존재하지 않는 작업입니다.")
    if job.status != "ready":
        raise HTTPException(409, "아직 미리보기가 준비되지 않았습니다.")
    base_url = str(request.base_url).rstrip("/")
    jobs.submit_export(job, base_url)
    return JSONResponse({"job_id": job.id})


# 프런트엔드 정적 파일 (마운트 순서상 마지막에 둔다)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
