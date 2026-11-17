# Runbooks

## Suspected PHI leak (logs, traces, vector store, responses)
1. Contain: scale affected service to 0 or block at ingress; rotate exposed credentials.
2. Identify: search by `request_id`/`tenant_id` in logs; audit log shows actors and actions (verify chain with `FileAuditSink.verify`).
3. Purge: delete affected log indices/spans, vector records (`VectorStorePort.delete`), cached sessions (`DELETE /v1/chat/{id}`).
4. Notify privacy/compliance officer immediately; follow your breach-notification policy.
5. Add a regression test using `SYNTHETIC_PHI` that reproduces the leak.

## LLM provider outage
Symptoms: 503 `provider_unavailable`, circuit open. Actions: switch `AIBASE_LLM__PROVIDER`/options to the fallback
vendor (config-only change), restart; confirm via `/metrics` error rate. Do not disable PHI redaction to "get unblocked".

## Redactor failure
`PHIRedactionError` (500 `phi_redaction_failed`) means requests are being blocked by design. Fix or roll back the
redactor adapter; never switch `fail_closed` off in production.

## Rollback a prompt
Prompts are versioned files; revert to the previous `vN.j2` by pinning the version in the caller or reverting the commit.
