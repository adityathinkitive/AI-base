from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aibase.api import Principal, get_audit, get_providers, record_audit, require_scopes
from aibase.audit import AuditSink
from aibase.guardrails import default_input_pipeline
from aibase.providers.factory import Providers
from rag_service import engine

router = APIRouter(prefix="/v1", tags=["rag"])
input_guard = default_input_pipeline(max_chars=4_000)


class IngestRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2_000_000)
    metadata: dict[str, str] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    doc_id: str
    chunks: int


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=4, ge=1, le=20)


@router.post("/documents", response_model=IngestResponse, status_code=201)
async def ingest_document(
    body: IngestRequest,
    principal: Principal = Depends(require_scopes("rag:write")),  # noqa: B008
    providers: Providers = Depends(get_providers),  # noqa: B008
    audit: AuditSink = Depends(get_audit),  # noqa: B008
) -> IngestResponse:
    doc_id = engine.new_doc_id()
    count = await engine.ingest(providers, principal.tenant_id, doc_id, body.text, body.metadata)
    record_audit(audit, principal, "rag.ingest", doc_id)
    return IngestResponse(doc_id=doc_id, chunks=count)


@router.post("/query", response_model=engine.Answer)
async def query(
    body: QueryRequest,
    principal: Principal = Depends(require_scopes("rag:read")),  # noqa: B008
    providers: Providers = Depends(get_providers),  # noqa: B008
    audit: AuditSink = Depends(get_audit),  # noqa: B008
) -> engine.Answer:
    input_guard.enforce(body.question)
    result = await engine.answer(providers, principal.tenant_id, body.question, body.top_k)
    record_audit(audit, principal, "rag.query", prompt_version=result.prompt)
    return result
