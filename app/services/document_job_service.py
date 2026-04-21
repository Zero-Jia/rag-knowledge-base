from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.document_job import DocumentJob, DocumentJobStage, DocumentJobStatus


def _stage_key(stage: DocumentJobStage | str) -> str:
    return stage.value if isinstance(stage, DocumentJobStage) else str(stage)


def _default_stage_payload() -> Dict[str, Any]:
    return {
        stage.value: {
            "status": DocumentJobStatus.PENDING.value,
            "started_at": None,
            "completed_at": None,
            "duration_ms": None,
            "details": {},
            "error": None,
        }
        for stage in DocumentJobStage
    }


def _utc_iso() -> str:
    return datetime.utcnow().isoformat()


def create_document_job(
    db: Session,
    *,
    document_id: int,
    user_id: int,
    metadata: Optional[Dict[str, Any]] = None,
) -> DocumentJob:
    job = DocumentJob(
        document_id=document_id,
        user_id=user_id,
        status=DocumentJobStatus.PENDING,
        current_stage=DocumentJobStage.UPLOAD,
        stages=_default_stage_payload(),
        metadata_json=metadata or {},
    )
    db.add(job)
    db.flush()
    return job


def get_latest_document_job(db: Session, *, document_id: int) -> Optional[DocumentJob]:
    return (
        db.query(DocumentJob)
        .filter(DocumentJob.document_id == document_id)
        .order_by(DocumentJob.id.desc())
        .first()
    )


def ensure_document_job(
    db: Session,
    *,
    document_id: int,
    user_id: int,
) -> DocumentJob:
    job = get_latest_document_job(db, document_id=document_id)
    if job:
        return job
    job = create_document_job(db, document_id=document_id, user_id=user_id)
    db.flush()
    return job


def mark_stage_processing(
    db: Session,
    *,
    job: DocumentJob,
    stage: DocumentJobStage,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    stages = dict(job.stages or _default_stage_payload())
    key = _stage_key(stage)
    payload = dict(stages.get(key) or {})
    payload.update(
        {
            "status": DocumentJobStatus.PROCESSING.value,
            "started_at": payload.get("started_at") or _utc_iso(),
            "completed_at": None,
            "duration_ms": None,
            "details": details or payload.get("details") or {},
            "error": None,
        }
    )
    stages[key] = payload
    job.stages = stages
    job.status = DocumentJobStatus.PROCESSING
    job.current_stage = stage
    job.updated_at = datetime.utcnow()
    db.flush()


def mark_stage_done(
    db: Session,
    *,
    job: DocumentJob,
    stage: DocumentJobStage,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    stages = dict(job.stages or _default_stage_payload())
    key = _stage_key(stage)
    payload = dict(stages.get(key) or {})
    started_at = payload.get("started_at")
    completed_at = _utc_iso()
    payload.update(
        {
            "status": DocumentJobStatus.DONE.value,
            "started_at": started_at,
            "completed_at": completed_at,
            "details": details or payload.get("details") or {},
            "error": None,
        }
    )
    if started_at:
        try:
            start_dt = datetime.fromisoformat(started_at)
            end_dt = datetime.fromisoformat(completed_at)
            payload["duration_ms"] = round((end_dt - start_dt).total_seconds() * 1000.0, 3)
        except Exception:
            payload["duration_ms"] = None
    stages[key] = payload
    job.stages = stages
    job.updated_at = datetime.utcnow()
    db.flush()


def mark_stage_failed(
    db: Session,
    *,
    job: DocumentJob,
    stage: DocumentJobStage,
    error_message: str,
    error_code: str = "DOCUMENT_JOB_STAGE_FAILED",
    details: Optional[Dict[str, Any]] = None,
) -> None:
    stages = dict(job.stages or _default_stage_payload())
    key = _stage_key(stage)
    payload = dict(stages.get(key) or {})
    payload.update(
        {
            "status": DocumentJobStatus.FAILED.value,
            "completed_at": _utc_iso(),
            "details": details or payload.get("details") or {},
            "error": {
                "code": error_code,
                "message": error_message,
            },
        }
    )
    stages[key] = payload
    job.stages = stages
    job.status = DocumentJobStatus.FAILED
    job.current_stage = stage
    job.error_code = error_code
    job.error_message = error_message
    job.completed_at = datetime.utcnow()
    job.updated_at = datetime.utcnow()
    db.flush()


def mark_job_done(db: Session, *, job: DocumentJob) -> None:
    job.status = DocumentJobStatus.DONE
    job.current_stage = DocumentJobStage.VECTOR_STORE
    job.completed_at = datetime.utcnow()
    job.updated_at = datetime.utcnow()
    db.flush()


def serialize_document_job(job: Optional[DocumentJob]) -> Optional[Dict[str, Any]]:
    if not job:
        return None
    return {
        "job_id": job.id,
        "document_id": job.document_id,
        "user_id": job.user_id,
        "status": job.status.value if job.status else None,
        "current_stage": job.current_stage.value if job.current_stage else None,
        "stages": job.stages or {},
        "error_code": job.error_code,
        "error_message": job.error_message,
        "metadata": job.metadata_json or {},
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
