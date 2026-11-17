from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aibase.api import Principal, get_audit, get_providers, record_audit, require_scopes
from aibase.audit import AuditSink
from aibase.providers.factory import Providers
from preprocessing_service.pipeline import Document, build_steps, chunk_text

router = APIRouter(prefix="/v1", tags=["preprocessing"])

DEFAULT_STEPS = ["normalize_unicode", "strip_control_chars", "collapse_whitespace", "deidentify"]


class PreprocessRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2_000_000)
    steps: list[str] = Field(default_factory=lambda: list(DEFAULT_STEPS))
    chunk_size: int = Field(default=1000, ge=50, le=20_000)
    chunk_overlap: int = Field(default=100, ge=0)


class PreprocessResponse(BaseModel):
    chunks: list[str]
    phi_entities_removed: int


@router.post("/preprocess", response_model=PreprocessResponse)
async def preprocess(
    body: PreprocessRequest,
    principal: Principal = Depends(require_scopes("preprocess:run")),  # noqa: B008
    providers: Providers = Depends(get_providers),  # noqa: B008
    audit: AuditSink = Depends(get_audit),  # noqa: B008
) -> PreprocessResponse:
    doc = Document(body.text)
    for step in build_steps(body.steps, providers.phi):
        doc = step(doc)
    chunks = chunk_text(doc.text, body.chunk_size, body.chunk_overlap)
    record_audit(audit, principal, "preprocess.run")
    return PreprocessResponse(chunks=chunks, phi_entities_removed=doc.phi_entities)
