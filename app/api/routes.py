import asyncio
import logging
import traceback
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from io import BytesIO

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from scipy.io.wavfile import write as write_wav

logger = logging.getLogger(__name__)

from app.config import settings
from app.job_manager import Job, JobStatus, job_manager
from app.pdf_parser import extract_paragraphs
from app.tts_engine import BUILTIN_VOICES, is_builtin_voice, tts_engine

router = APIRouter()


def _sanitize_book_name(filename: str) -> str:
    """Convert filename to a safe directory name."""
    name = Path(filename).stem
    # Replace spaces and special chars
    name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name)
    return name.strip()


def _get_voice_path(voice_name: Optional[str]) -> Path | str:
    """Resolve a voice: returns a Path for file-based voices, a string for built-in."""
    if voice_name:
        if is_builtin_voice(voice_name):
            return voice_name
        candidate = settings.voice_dir / voice_name
        if candidate.exists():
            return candidate
        raise HTTPException(400, f"Voice not found: {voice_name}")
    # Default: first built-in voice
    return BUILTIN_VOICES[0]


@router.get("/voices")
async def list_voices():
    """List available voices: built-in first, then file-based."""
    result = [
        {"name": v, "filename": v, "type": "builtin"}
        for v in BUILTIN_VOICES
    ]
    file_voices = [
        {"name": f.stem, "filename": f.name, "type": "file"}
        for f in sorted(settings.voice_dir.glob("*.wav"))
    ]
    return result + file_voices


@router.get("/voices/{voice_name}/sample")
async def sample_voice(voice_name: str):
    """Play/sample a voice. For built-in voices, generates a sample on the fly."""
    if is_builtin_voice(voice_name):
        voice_state = tts_engine.load_voice(voice_name)
        data, sample_rate = tts_engine.generate_audio(voice_state, "Hello, this is a sample of the " + voice_name + " voice.")
        buffer = BytesIO()
        write_wav(buffer, sample_rate, data)
        return Response(content=buffer.getvalue(), media_type="audio/wav")

    voice_path = settings.voice_dir / voice_name
    if not voice_path.exists():
        raise HTTPException(404, f"Voice file not found: {voice_name}")
    if not voice_path.suffix.lower() == ".wav":
        raise HTTPException(400, "Only WAV files are supported")

    return FileResponse(
        str(voice_path),
        media_type="audio/wav",
        filename=voice_name,
    )


@router.post("/upload")
async def upload_pdf(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    voice: Optional[str] = Form(None),
):
    """Upload a PDF (via file or URL) and start audio generation job."""
    if not file and not url:
        raise HTTPException(400, "Either a file or a URL must be provided")
    if file and url:
        raise HTTPException(400, "Provide either a file or a URL, not both")

    if url:
        return await _handle_url_upload(url, voice)
    else:
        return await _handle_file_upload(file, voice)


async def _handle_file_upload(file: UploadFile, voice: Optional[str]) -> dict:
    """Handle PDF upload from a file."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            400,
            f"File too large. Max {settings.max_file_size_mb}MB",
        )

    book_name = _sanitize_book_name(file.filename)
    job = job_manager.create(book_name, voice or BUILTIN_VOICES[0])
    job_id = job.job_id

    try:
        voice_resolved = _get_voice_path(voice)
    except HTTPException as e:
        job_manager.set_error(job_id, str(e))
        raise

    temp_path = Path("/tmp") / f"{job_id}.pdf"
    temp_path.write_bytes(content)

    output_dir = settings.output_dir / book_name
    output_dir.mkdir(parents=True, exist_ok=True)
    job_manager.set_output_dir(job_id, output_dir)

    asyncio.create_task(_process_job(job_id, temp_path, output_dir, voice_resolved))

    return {"job_id": job_id, "book_name": book_name}


async def _handle_url_upload(url: str, voice: Optional[str]) -> dict:
    """Handle PDF upload from a URL — download the PDF and process it."""
    # Validate URL looks like a PDF
    if not url.lower().endswith(".pdf"):
        raise HTTPException(400, "URL must point to a PDF file (end with .pdf)")

    # Derive book name from URL
    url_path = urllib.parse.urlparse(url).path
    filename = Path(url_path).name or "downloaded.pdf"
    book_name = _sanitize_book_name(filename)

    job = job_manager.create(book_name, voice or BUILTIN_VOICES[0])
    job_id = job.job_id

    try:
        voice_resolved = _get_voice_path(voice)
    except HTTPException as e:
        job_manager.set_error(job_id, str(e))
        raise

    # Download the PDF
    temp_path = Path("/tmp") / f"{job_id}.pdf"
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _download_pdf, url, temp_path, settings.max_file_size_mb)
    except HTTPException:
        job_manager.set_error(job_id, "Failed to download PDF from URL")
        raise
    except Exception as e:
        logger.error("Job %s: download failed: %s", job_id, e)
        job_manager.set_error(job_id, f"Failed to download PDF: {e}")
        raise HTTPException(400, f"Failed to download PDF: {e}")

    output_dir = settings.output_dir / book_name
    output_dir.mkdir(parents=True, exist_ok=True)
    job_manager.set_output_dir(job_id, output_dir)

    asyncio.create_task(_process_job(job_id, temp_path, output_dir, voice_resolved))

    return {"job_id": job_id, "book_name": book_name}


def _download_pdf(url: str, dest: Path, max_size_mb: int) -> None:
    """Download a PDF from a URL to a local path. Runs in a thread."""
    max_bytes = max_size_mb * 1024 * 1024
    with urllib.request.urlopen(url, timeout=30) as response:
        content_type = response.headers.get("Content-Type", "")
        if "application/pdf" not in content_type and not url.lower().endswith(".pdf"):
            raise HTTPException(400, f"URL does not point to a PDF (Content-Type: {content_type})")

        content = response.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise HTTPException(400, f"File too large. Max {max_size_mb}MB")

        dest.write_bytes(content)


@router.get("/jobs")
async def list_jobs():
    """List all jobs with their status."""
    jobs = job_manager.list_all()
    return [
        {
            "job_id": j.job_id,
            "book_name": j.book_name,
            "voice_name": j.voice_name,
            "status": j.status.value,
            "progress": job_manager.progress.get(j.job_id, 0.0),
            "total_chunks": j.total_chunks,
            "completed_chunks": j.completed_chunks,
            "created_at": j.created_at.isoformat(),
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        }
        for j in jobs
    ]


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Get job status and details."""
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")

    result = {
        "job_id": job.job_id,
        "book_name": job.book_name,
        "voice_name": job.voice_name,
        "status": job.status.value,
        "progress": job_manager.progress.get(job_id, 0.0),
        "total_chunks": job.total_chunks,
        "completed_chunks": job.completed_chunks,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }

    # Include audio file list if completed
    if job.status == JobStatus.COMPLETED and job.output_dir:
        audio_files = sorted(
            {"filename": f.name, "size": f.stat().st_size}
            for f in job.output_dir.glob("*.wav")
        )
        result["audio_files"] = audio_files

    return result


@router.get("/jobs/{job_id}/download/{filename}")
async def download_audio(job_id: str, filename: str):
    """Download a specific audio file from a completed job."""
    job = job_manager.get(job_id)
    if job is None or job.output_dir is None:
        raise HTTPException(404, "Job not found")

    file_path = job.output_dir / filename
    if not file_path.exists():
        raise HTTPException(404, "Audio file not found")

    return FileResponse(
        str(file_path),
        media_type="audio/wav",
        filename=filename,
    )


async def _process_job(
    job_id: str,
    pdf_path: Path,
    output_dir: Path,
    voice_path: Path | str | None = None,
) -> None:
    """Background task: extract text, generate audio, save chunks."""
    logger.info(
        "Job %s: starting processing (pdf=%s, voice=%s)", job_id, pdf_path, voice_path
    )
    job_manager.update_status(job_id, JobStatus.PROCESSING)

    try:
        # Extract paragraphs
        logger.info("Job %s: extracting paragraphs from PDF", job_id)
        paragraphs = extract_paragraphs(pdf_path)
        logger.info("Job %s: extracted %d paragraphs", job_id, len(paragraphs))
        job_manager.update_progress(job_id, 0, len(paragraphs))

        # Load voice
        voice_label = voice_path if voice_path else BUILTIN_VOICES[0]
        logger.info("Job %s: loading voice %s", job_id, voice_label)
        voice_state = tts_engine.load_voice(voice_path)
        logger.info("Job %s: voice loaded successfully", job_id)

        # Generate audio for each paragraph
        for i, paragraph in enumerate(paragraphs):
            chunk_path = output_dir / f"{i:03d}.wav"
            logger.debug(
                "Job %s: generating audio for paragraph %d/%d",
                job_id,
                i + 1,
                len(paragraphs),
            )
            await tts_engine.async_save_audio_chunk(voice_state, paragraph, chunk_path)
            job_manager.update_progress(job_id, i + 1, len(paragraphs))
            logger.info("Job %s: saved chunk %03d.wav (%s)", job_id, i, chunk_path.name)

        # Cleanup temp file
        pdf_path.unlink(missing_ok=True)
        logger.info(
            "Job %s: completed successfully — generated %d chunks",
            job_id,
            len(paragraphs),
        )
        job_manager.update_status(job_id, JobStatus.COMPLETED)

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error("Job %s: processing failed:\n%s", job_id, error_details)
        job_manager.set_error(job_id, error_details)
        # Cleanup temp file on error
        pdf_path.unlink(missing_ok=True)
