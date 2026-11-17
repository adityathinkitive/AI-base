from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aibase.api import Principal, get_audit, get_providers, record_audit, require_scopes
from aibase.audit import AuditSink
from aibase.guardrails import default_input_pipeline
from aibase.providers.factory import Providers
from summarization_service.chains import NoteFormat, Summary, summarize

router = APIRouter(prefix="/v1", tags=["summarization"])
input_guard = default_input_pipeline(max_chars=500_000)


class SummarizeRequest(BaseModel):
    text: str = Field(min_length=1)
    format: NoteFormat = "general"


@router.post("/summaries", response_model=Summary)
async def create_summary(
    body: SummarizeRequest,
    principal: Principal = Depends(require_scopes("summarize:run")),  # noqa: B008
    providers: Providers = Depends(get_providers),  # noqa: B008
    audit: AuditSink = Depends(get_audit),  # noqa: B008
) -> Summary:
    input_guard.enforce(body.text)
    result = await summarize(providers.llm, body.text, body.format)
    record_audit(audit, principal, "summarize.run", prompt_version=",".join(result.prompts))
    return result
