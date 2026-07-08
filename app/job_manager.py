import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    job_id: str
    book_name: str
    voice_name: str
    status: JobStatus = JobStatus.PENDING
    total_chunks: int = 0
    completed_chunks: int = 0
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    output_dir: Optional[Path] = None


class JobManager:
    def __init__(self):
        self._jobs: dict[str, Job] = {}

    def create(self, book_name: str, voice_name: str) -> Job:
        job_id = uuid.uuid4().hex[:12]
        job = Job(job_id=job_id, book_name=book_name, voice_name=voice_name)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list_all(self) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def update_status(self, job_id: str, status: JobStatus) -> Optional[Job]:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        job.status = status
        if status == JobStatus.COMPLETED:
            job.completed_at = datetime.now()
        elif status == JobStatus.FAILED:
            job.completed_at = datetime.now()
        return job

    def update_progress(self, job_id: str, completed: int, total: int) -> Optional[Job]:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        job.completed_chunks = completed
        job.total_chunks = total
        return job

    def set_error(self, job_id: str, message: str) -> Optional[Job]:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        job.status = JobStatus.FAILED
        job.error_message = message
        job.completed_at = datetime.now()
        return job

    def set_output_dir(self, job_id: str, output_dir: Path) -> Optional[Job]:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        job.output_dir = output_dir
        return job

    @property
    def progress(self) -> dict[str, float]:
        return {
            j.job_id: (j.completed_chunks / j.total_chunks * 100) if j.total_chunks > 0 else 0.0
            for j in self._jobs.values()
        }


job_manager = JobManager()
