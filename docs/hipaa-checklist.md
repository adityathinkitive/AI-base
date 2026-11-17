# HIPAA readiness checklist (template-level, not legal advice)

Verify every item against current HHS guidance (e.g. 45 CFR 164.312) with your compliance owner. The research behind
this template came largely from vendor/practitioner material, not primary regulatory text.

## Provided by the template
- [x] PHI redaction before LLM calls and on LLM output; fail-closed default; production refuses to start otherwise
- [x] Logs/tracebacks scrubbed; validation errors don't echo input; spans carry no content
- [x] Audit log (who/when/action/model/prompt version; opaque IDs; hash-chained)
- [x] AuthN (JWT) + scope authZ + tenant scoping; docs/OpenAPI disabled in staging/production
- [x] Minimum-necessary: services pass task-specific prompts; chat history stored de-identified with TTL
- [x] Container hardening: non-root, read-only fs, dropped caps; k8s NetworkPolicy default-deny egress

## You must still do
- [ ] BAA with every vendor that can touch PHI (LLM, STT, vector DB, hosting, observability); zero-retention terms for LLM APIs
- [ ] Replace dev adapters: encrypted object storage, durable queue, real vector store, NER-grade redactor, real diarizer
- [ ] Validate redaction recall on representative data; regex alone is insufficient
- [ ] Encryption at rest/in transit (TLS termination, KMS), secret manager, key rotation
- [ ] Write-once/off-box audit sink with retention per your policy (the six-year figure in some sources is unverified)
- [ ] Access reviews, MFA at the IdP, break-glass procedure, workforce training
- [ ] Risk assessment, incident response test, backup/restore test
- [ ] Clinical safety review of emergency-escalation rules and any generated clinical text (human in the loop)
