# Threat model (OWASP LLM Top 10, 2025)

| Risk | Mitigation in template | Gap / your action |
|---|---|---|
| LLM01 Prompt injection (direct + indirect) | `guardrails` heuristics on input; RAG drops injection-looking chunks and wraps sources as untrusted data | Heuristics are weak; add a model-based classifier for high-risk flows; red-team regularly |
| LLM02 Sensitive info disclosure | PHI guard in/out, scrubbed logs, no content in spans, de-identified storage | Measure redaction recall; restrict egress |
| LLM03 Supply chain | uv lockfile, pip-audit, Dependabot, Trivy, optional extras | Pin images by digest; review model provenance |
| LLM05 Improper output handling | Pydantic schema validation (`generate_structured`), output PHI check | Never execute model output; encode when rendering |
| LLM06 Excessive agency | Chatbot has no tools by default; tools must take `Principal` | Add least-privilege tool allowlists + human approval for writes |
| LLM07 System prompt leakage | Prompts assumed public; no secrets in prompts | Keep secrets out of prompt files |
| LLM08 Vector/embedding weaknesses | Tenant-scoped store API; ingestion redaction | Verify tenant filters in every real adapter (contract test) |
| LLM09 Misinformation | Grounded answers + citations, refusal when no context, SOAP "Not documented" | Faithfulness evals on gold data; clinician review |
| LLM10 Unbounded consumption | Rate limit, body-size limit, input length caps, provider timeouts/breaker, bounded map concurrency | Per-tenant token budgets; the in-memory limiter is per-process, use a shared store in production |
