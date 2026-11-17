import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from aibase.api import Principal, get_audit, get_providers, record_audit, require_scopes
from aibase.audit import AuditSink
from aibase.guardrails import default_input_pipeline, default_output_pipeline
from aibase.providers.factory import Providers
from chatbot_service import conversation as conv

router = APIRouter(prefix="/v1", tags=["chatbot"])
input_guard = default_input_pipeline(max_chars=4_000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{8,64}$")


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    escalated: bool = False


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    principal: Principal = Depends(require_scopes("chat:write")),  # noqa: B008
    providers: Providers = Depends(get_providers),  # noqa: B008
    audit: AuditSink = Depends(get_audit),  # noqa: B008
) -> ChatResponse:
    input_guard.enforce(body.message)
    session_id = body.session_id or uuid.uuid4().hex
    if conv.is_emergency(body.message):
        record_audit(audit, principal, "chat.escalate", session_id)
        return ChatResponse(session_id=session_id, reply=conv.ESCALATION_REPLY, escalated=True)

    store = conv.SessionStore(providers.cache, providers.phi)
    key = store.key(principal.tenant_id, principal.subject, session_id)
    history = await store.load(key)
    messages, prompt_tag = conv.build_messages(history, body.message)
    answer = await conv.reply(providers.llm, messages)
    default_output_pipeline(providers.phi).enforce(answer)
    await store.append(key, history, body.message, answer)
    record_audit(audit, principal, "chat.message", session_id, prompt_version=prompt_tag)
    return ChatResponse(session_id=session_id, reply=answer)


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    principal: Principal = Depends(require_scopes("chat:write")),  # noqa: B008
    providers: Providers = Depends(get_providers),  # noqa: B008
    audit: AuditSink = Depends(get_audit),  # noqa: B008
) -> StreamingResponse:
    input_guard.enforce(body.message)
    session_id = body.session_id or uuid.uuid4().hex

    async def events() -> AsyncIterator[str]:
        if conv.is_emergency(body.message):
            record_audit(audit, principal, "chat.escalate", session_id)
            yield f"data: {json.dumps({'token': conv.ESCALATION_REPLY, 'escalated': True})}\n\n"
            return
        store = conv.SessionStore(providers.cache, providers.phi)
        key = store.key(principal.tenant_id, principal.subject, session_id)
        history = await store.load(key)
        messages, prompt_tag = conv.build_messages(history, body.message)
        collected: list[str] = []
        async for token in conv.reply_stream(providers.llm, messages, collected):
            yield f"data: {json.dumps({'token': token})}\n\n"
        await store.append(key, history, body.message, "".join(collected))
        record_audit(audit, principal, "chat.message", session_id, prompt_version=prompt_tag)
        yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.delete("/chat/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    principal: Principal = Depends(require_scopes("chat:write")),  # noqa: B008
    providers: Providers = Depends(get_providers),  # noqa: B008
    audit: AuditSink = Depends(get_audit),  # noqa: B008
) -> None:
    store = conv.SessionStore(providers.cache, providers.phi)
    await store.clear(store.key(principal.tenant_id, principal.subject, session_id))
    record_audit(audit, principal, "chat.delete", session_id)
