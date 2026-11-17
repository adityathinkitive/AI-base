# Architecture

## Layering (enforced by `scripts/check_boundaries.py`)
```
services/*        deployable apps; may import libs only, never each other
─────────────────────────────────────────────
aibase.api
aibase.guardrails | evals | prompts
aibase.providers                (ports, adapters, config-driven registry/factory)
aibase.observability | audit
aibase.phi
aibase.core
```
A layer may import only from layers below it.

## Request path
`client → rate limit/size limit/request-id → auth (JWT, tenant, scopes) → input guardrails →
service logic → providers (LLM wrapped in GuardedLLM: redact in, redact out) → output guardrails →
audit event → response`. Errors always use one JSON envelope; validation errors never echo input.

## Data handling rules
- PHI is redacted before leaving the trust boundary (LLM calls) and before storage (vector store, transcripts, chat history).
- Logs, tracebacks and spans never carry prompt/completion content; log scrubbing is a global formatter.
- Audit events hold opaque IDs only and are hash-chained.
- Raw audio is deleted after transcription.

## Decisions
- ADR-001 Template repo, not a generator: users delete what they don't need; CI proves deletions are safe.
- ADR-002 Ports & adapters with lazy adapter imports: vendor SDKs are optional extras.
- ADR-003 Regex redaction ships as the offline default; it cannot detect free-text names. Use an NER adapter
  (Presidio built in) for real PHI workloads and evaluate recall on your own data.
- ADR-004 OTel `gen_ai.*` conventions are experimental; pin `OTEL_SEMCONV_STABILITY_OPT_IN` and expect churn.
