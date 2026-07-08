from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.job_manager import JobStatus, job_manager

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parents[2] / "templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # return templates.TemplateResponse("index.html", {"request": request})
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )


@router.get("/jobs/list", response_class=HTMLResponse)
async def job_list_partial(request: Request):
    """Return job cards as HTML partial for HTMX swapping."""
    jobs = job_manager.list_all()
    if not jobs:
        return HTMLResponse("<p class='text-sm text-gray-500 py-4'>No jobs yet.</p>")
    job = jobs[0]
    progress = job_manager.progress.get(job.job_id, 0.0)
    job_dict = {
        "job_id": job.job_id,
        "book_name": job.book_name,
        "voice_name": job.voice_name,
        "status": job.status.value,
        "total_chunks": job.total_chunks,
        "completed_chunks": job.completed_chunks,
        "error_message": job.error_message,
        "created_at": job.created_at.strftime("%Y-%b-%d"),
        "progress": progress,
    }
    return templates.TemplateResponse(
        request=request,
        name="partials/job_card.html",
        context={"job": job_dict},
    )


@router.get("/jobs/list-all", response_class=HTMLResponse)
async def job_list_all_partial(request: Request):
    """Return all job cards as HTML partial for HTMX swapping."""
    jobs = job_manager.list_all()
    if not jobs:
        return HTMLResponse("<p class='text-sm text-gray-500 py-4'>No jobs yet.</p>")
    progress_map = job_manager.progress
    enriched = []
    for job in jobs:
        job_dict = {
            "job_id": job.job_id,
            "book_name": job.book_name,
            "voice_name": job.voice_name,
            "status": job.status.value,
            "total_chunks": job.total_chunks,
            "completed_chunks": job.completed_chunks,
            "error_message": job.error_message,
            "created_at": job.created_at.strftime("%Y-%b-%d"),
            "progress": progress_map.get(job.job_id, 0.0),
        }
        enriched.append(job_dict)
    return templates.TemplateResponse(
        request=request,
        name="partials/job_list_all.html",
        context={"jobs": enriched},
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: str):
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")

    progress = job_manager.progress.get(job_id, 0.0)
    audio_files = []
    if job.status == JobStatus.COMPLETED and job.output_dir:
        audio_files = sorted(
            [{"filename": f.name, "size": f.stat().st_size, "idx": int(f.stem)}
             for f in job.output_dir.glob("*.wav")],
            key=lambda a: a["idx"],
        )

    return templates.TemplateResponse(
        request = request,
        name = "job_detail.html",
        context = {
            "job": job,
            "job_id": job_id,
            "progress": progress,
            "audio_files": audio_files,
        },
    )
