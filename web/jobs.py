"""In-memory job store for the web UI.

Each job tracks pipeline progress as events are emitted, so the frontend can
poll /api/jobs/{id} and render the step timeline.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Job:
    id: str
    spec: str
    status: str = "running"  # running | done | failed
    events: list = field(default_factory=list)
    success: bool = False
    final_dir: Optional[str] = None
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "spec": self.spec,
            "status": self.status,
            "events": self.events,
            "success": self.success,
            "final_dir": self.final_dir,
            "error": self.error,
        }


class JobStore:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, spec: str) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], spec=spec)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def on_progress(self, job: Job):
        """Return a callback that appends pipeline events into the job."""
        def _cb(event: str, data: dict) -> None:
            with self._lock:
                job.events.append({"event": event, "data": data})
                if event == "done":
                    job.status = "done" if data.get("success") else "failed"
                    job.success = bool(data.get("success"))
                    job.final_dir = data.get("final_dir")
        return _cb

    def mark_error(self, job: Job, msg: str) -> None:
        with self._lock:
            job.status = "failed"
            job.error = msg


job_store = JobStore()
