import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from aibase.api import Principal, get_audit, get_providers, record_audit, require_scopes
from aibase.api.auth import get_principal
from aibase.audit import AuditSink
from aibase.core.errors import BadRequest, NotFound
from aibase.core.settings import Settings
from aibase.providers.factory import Providers
from transcription_service import pipeline

router = APIRouter(prefix="/v1", tags=["transcription"])
ALLOWED_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/webm",
    "audio/ogg",
    "text/plain",
}
TASK = "transcribe"


class JobCreated(BaseModel):
    job_id: str


class JobResult(BaseModel):
    job_id: str
    state: str
    transcript: pipeline.Transcript | None = None
    error: str | None = None


def make_handler(providers: Providers) -> Any:
    async def handle(payload: dict[str, Any]) -> dict[str, str]:
        audio = await providers.storage.get(payload["audio_key"])
        transcript = await pipeline.run(
            audio, providers.stt, providers.diarizer, providers.phi, payload.get("language")
        )
        await providers.storage.put(payload["result_key"], transcript.model_dump_json().encode())
        await providers.storage.delete(
            payload["audio_key"]
        )  # raw audio is not retained after processing
        return {"tenant_id": payload["tenant_id"], "result_key": payload["result_key"]}

    return handle


@router.post("/transcriptions", response_model=JobCreated, status_code=202)
async def create_transcription(
    file: UploadFile = File(...),  # noqa: B008
    language: str | None = Form(default=None),
    principal: Principal = Depends(require_scopes("transcribe:write")),  # noqa: B008
    providers: Providers = Depends(get_providers),  # noqa: B008
    audit: AuditSink = Depends(get_audit),  # noqa: B008
) -> JobCreated:
    if file.content_type not in ALLOWED_TYPES:
        raise BadRequest("unsupported media type", details={"allowed": sorted(ALLOWED_TYPES)})
    audio = await file.read()
    if not audio:
        raise BadRequest("empty file")
    job_ref = uuid.uuid4().hex
    audio_key = f"{principal.tenant_id}/audio/{job_ref}"
    await providers.storage.put(audio_key, audio)
    job_id = await providers.queue.enqueue(
        TASK,
        {
            "tenant_id": principal.tenant_id,
            "audio_key": audio_key,
            "result_key": f"{principal.tenant_id}/transcripts/{job_ref}.json",
            "language": language,
        },
        idempotency_key=f"{principal.tenant_id}:{job_ref}",
    )
    record_audit(audit, principal, "transcribe.create", job_id)
    return JobCreated(job_id=job_id)


@router.get("/transcriptions/{job_id}", response_model=JobResult)
async def get_transcription(
    job_id: str,
    principal: Principal = Depends(require_scopes("transcribe:read")),  # noqa: B008
    providers: Providers = Depends(get_providers),  # noqa: B008
    audit: AuditSink = Depends(get_audit),  # noqa: B008
) -> JobResult:
    status = await providers.queue.status(job_id)
    if status.state == "succeeded":
        # Same 404 for "not yours" and "doesn't exist" so job IDs can't be probed across tenants.
        if status.result["tenant_id"] != principal.tenant_id:
            raise NotFound("job not found")
        raw = await providers.storage.get(status.result["result_key"])
        record_audit(audit, principal, "transcribe.read", job_id)
        return JobResult(
            job_id=job_id,
            state=status.state,
            transcript=pipeline.Transcript.model_validate(json.loads(raw)),
        )
    return JobResult(job_id=job_id, state=status.state, error=status.error)


@router.websocket("/stream")
async def stream(ws: WebSocket, principal: Principal = Depends(get_principal)) -> None:  # noqa: B008
    """Live dictation: each binary frame is an audio chunk; each reply is its redacted segments.
    Authoritative transcript should still be produced by the batch endpoint at session end."""
    if "*" not in principal.scopes and "transcribe:stream" not in principal.scopes:
        await ws.close(code=1008)
        return
    providers: Providers = ws.app.state.providers
    settings: Settings = ws.app.state.settings
    await ws.accept()
    try:
        index = 0
        while True:
            chunk = await ws.receive_bytes()
            if len(chunk) > settings.limits.max_body_bytes:
                await ws.close(code=1009)
                return
            result = await pipeline.run(chunk, providers.stt, providers.diarizer, providers.phi)
            await ws.send_json(
                {"chunk": index, "lines": [line.model_dump() for line in result.lines]}
            )
            index += 1
    except WebSocketDisconnect:
        return
