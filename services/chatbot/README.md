# chatbot

- `POST /v1/chat`, `POST /v1/chat/stream` (SSE), `DELETE /v1/chat/{session_id}` (scope `chat:write`).
- Deterministic emergency escalation runs before any model call (`conversation.EMERGENCY`; tune with clinical owners).
- Session memory lives behind `CachePort`, keyed by tenant + user + session, TTL 1h, **de-identified only**.
- Output is checked for PHI before it is returned.
- Tools: add a registry under `src/chatbot_service/tools/` and call it from `conversation.py`; every tool must
  take `Principal` and enforce tenant scoping.
