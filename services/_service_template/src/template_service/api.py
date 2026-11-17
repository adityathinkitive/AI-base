from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aibase.api import Principal, get_audit, get_providers, record_audit, require_scopes
from aibase.audit import AuditSink
from aibase.guardrails import default_input_pipeline
from aibase.providers.factory import Providers
from aibase.providers.llm import LLMMessage

router = APIRouter(prefix="/v1", tags=["template"])
input_guard = default_input_pipeline()


class AskRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20_000)


class AskResponse(BaseModel):
    answer: str
    model: str


@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    principal: Principal = Depends(require_scopes("template:ask")),  # noqa: B008
    providers: Providers = Depends(get_providers),  # noqa: B008
    audit: AuditSink = Depends(get_audit),  # noqa: B008
) -> AskResponse:
    input_guard.enforce(body.prompt)
    response = await providers.llm.generate([LLMMessage(role="user", content=body.prompt)])
    record_audit(audit, principal, "template.ask", model=response.model)
    return AskResponse(answer=response.text, model=response.model)
