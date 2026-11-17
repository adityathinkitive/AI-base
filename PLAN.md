# AI-base: Production Template Repo for Healthcare AI Services

## Context
Thinkitive builds healthcare AI (transcription, summarization, RAG, chatbot, preprocessing). Each new project currently re-creates the same plumbing. `AI-base` will be a **template repo** (GitHub "Use this template" / clone). There is no generator engine (no Cookiecutter/Copier): users clone, delete the services they don't need, and keep the rest. So the design priority is **deletability**: every service folder must be removable with `rm -rf` plus a one-line registry edit and nothing else breaking.

Baseline: Python 3.12+, FastAPI, uv, ruff, Pydantic v2. **Vendor agnostic**: every external dependency sits behind a port (Protocol) with swappable adapters selected by config. The repo has only `.gitignore`, `README.md` and `unnamed.png` (the single-agent layout sketch, which this plan supersedes with a monorepo; the png should be deleted).

## Research-backed standards adopted
- Layered FastAPI layout (routers → services → adapters), Pydantic `BaseSettings` for env config, feature/domain-organised code (community FastAPI best-practices guides).
- HIPAA: BAA with every PHI-touching vendor; de-identify before inference; **fail closed** if redaction fails; minimum-necessary prompts; redact PHI from LLM output and from logs/traces/eval datasets; append-only audit log (who/when/which model/which data, never raw PHI). Verify retention periods and 45 CFR 164.312(b) against HHS directly; the sources I found are vendor blogs.
- Observability: OpenTelemetry with `gen_ai.*` semantic conventions (still experimental, so pin version via `OTEL_SEMCONV_STABILITY_OPT_IN`), OTLP export to any backend. OTel doesn't cover quality, so add a separate eval layer.
- Security: OWASP LLM Top 10 (2025), priority on LLM01 prompt injection (incl. indirect injection via retrieved docs), LLM02 sensitive info disclosure, LLM10 unbounded consumption. Guardrails are enforcement; system prompts are not.
- Evals in CI: RAG metrics (faithfulness, answer relevance, context precision/recall) plus cheap IR metrics (Precision@K/Recall@K) as gating thresholds.
- Transcription: batch (REST + queue) and streaming (WebSocket) from one pipeline; stages = ingest → VAD/chunk (overlap-aware for long audio) → ASR → diarization → merge → PII redaction (named, configurable stage) → structured output; suppress low-confidence diarization on cross-talk; never log raw audio/transcripts.

Caveat: most sources were secondary/vendor material; no authoritative primary docs were retrieved. Validate compliance specifics with your compliance owner.

## Repository layout
```
AI-base/
├── README.md                 # how to adopt: clone, delete services, run
├── TEMPLATE_GUIDE.md         # step-by-step "remove a service / add a provider"
├── pyproject.toml            # uv workspace root, ruff, mypy, pytest config
├── uv.lock
├── Makefile                  # make dev|lint|test|eval|up|down
├── docker-compose.yml        # app + redis + postgres + otel-collector (+ optional vector db profile)
├── .env.example
├── .pre-commit-config.yaml   # ruff, mypy, gitleaks, detect-secrets
├── .github/workflows/        # ci.yml, security.yml, eval.yml, release.yml (+ dependabot.yml, CODEOWNERS, PR template)
├── docs/
│   ├── architecture.md, adr/ (decision records), hipaa-checklist.md, threat-model.md
│   └── runbooks/ (incident, PHI-leak response, provider outage)
├── libs/                     # shared, service-agnostic (never imports from services/)
│   ├── core/                 # settings, logging (structlog + PHI scrubber), errors, request-id middleware, retry/timeout/circuit-breaker, health, auth (JWT/OIDC verify), rate limit, idempotency
│   ├── providers/            # PORTS + ADAPTERS, one subpackage per capability
│   │   ├── llm/              # port: generate/stream/structured-output/tool-calls; adapters: openai-compatible, anthropic, bedrock, vertex, azure, local (vLLM/Ollama), fake
│   │   ├── embeddings/       # port + adapters (api, sentence-transformers, fake)
│   │   ├── vectorstore/      # port + adapters (pgvector, qdrant, opensearch, in-memory)
│   │   ├── stt/              # port (batch+stream) + adapters (faster-whisper, cloud STT, fake)
│   │   ├── diarization/      # port + adapters
│   │   ├── storage/          # port: S3-compatible/GCS/Azure blob/local, with encryption + signed URLs
│   │   ├── queue/            # port: Celery/Arq/SQS-compatible; in-memory for tests
│   │   ├── cache/            # port: Redis / in-memory
│   │   └── registry.py       # config-driven factory: provider name → adapter (entry-point style)
│   ├── phi/                  # detect/redact/pseudonymize port + adapters (Presidio, regex-rules, cloud), fail-closed wrapper, reversible token vault
│   ├── guardrails/           # input (injection, PHI, topic) and output (PHI, grounding, schema) checks as composable pipeline
│   ├── observability/        # OTel setup, gen_ai.* span helpers, metrics (tokens, cost, latency), backend-agnostic exporter config
│   ├── audit/                # append-only audit event model + sink port (db, file, SIEM)
│   ├── prompts/              # versioned prompt registry (files + semver + hash), Jinja templates, golden tests
│   ├── evals/                # dataset loaders, metric port (Ragas/DeepEval/custom adapters), CI gate runner
│   └── testing/              # fakes, fixtures, synthetic-PHI generators, VCR-style recorded LLM responses
├── services/                 # each is an independently deployable FastAPI app (own Dockerfile, pyproject, tests, README)
│   ├── _service_template/    # minimal skeleton new services copy from
│   ├── transcription/        # api/, pipeline/ (stages), workers/, streaming/ (WS), schemas/
│   ├── summarization/        # api/, chains/ (chunk→map→reduce, clinical note formats: SOAP etc.), citations-to-source, schemas/
│   ├── rag/                  # ingestion/ (parse, chunk, embed, index), retrieval/ (hybrid, rerank), generation/, access-control filters, api/
│   ├── chatbot/              # api/ (SSE/WS), conversation/ (memory, session store), tools/, orchestration/, handoff/escalation, safety
│   └── preprocessing/        # pipelines/ (DICOM/HL7/FHIR/PDF/OCR/audio normalisation), steps as composable transforms, batch + stream
├── deploy/
│   ├── docker/ (multi-stage, non-root, distroless/slim, read-only fs)
│   ├── k8s/ (kustomize base/overlays: probes, HPA, NetworkPolicy, PodSecurity, resource limits)
│   └── terraform/ (optional, cloud-neutral modules stubbed)
├── data/ (gitignored; sample synthetic data only in tests/fixtures)
└── tests/ (cross-service contract + e2e; per-service tests live in each service)
```
Service dependency rule: `services/* → libs/*` only; no service imports another service (communicate via HTTP/queue contracts defined in OpenAPI/Pydantic). Enforced by `import-linter` in CI. This is what makes deleting a service safe.

## Key design decisions
1. **Ports & adapters**: each port is a `typing.Protocol` + Pydantic request/response models. Provider chosen via `settings.llm.provider = "openai_compat"` etc.; heavy SDKs are **optional extras** (`uv sync --extra anthropic`), so deleting an adapter means deleting its folder and extra. `fake` adapters ship for every port so tests/CI need no network or keys.
2. **PHI by construction**: `PHIGuard` wraps every provider call; default policy is fail-closed; scrubbing logging processor is installed globally; test suite includes synthetic-PHI leak tests asserting no PHI in logs/traces/errors.
3. **12-factor config**: `BaseSettings` with nested models, secrets from env/secret manager port (never `.env` in prod), config validated at startup (fail fast).
4. **Reliability**: timeouts everywhere, retries with jitter only on idempotent calls, circuit breaker + provider fallback chain, bulkheads, graceful shutdown, backpressure on queues, idempotency keys, dead-letter queues.
5. **Security**: OIDC/JWT auth dependency, per-tenant isolation in every store query, RBAC scopes, rate limits, request size limits, upload validation (type, size, AV hook), TLS/CORS strict defaults, SBOM + dependency audit (pip-audit), container scan (trivy), secret scan (gitleaks), SAST (bandit/semgrep).
6. **Observability**: structured JSON logs w/ trace correlation, OTel traces/metrics, per-request token/cost accounting, `/healthz` `/readyz` `/metrics`, dashboards/alerts as code stubs in `deploy/`.
7. **Quality gates (CI)**: ruff (lint+format), mypy strict on libs, pytest + coverage threshold, import-linter, prompt golden tests, eval gate (retrieval + faithfulness thresholds on a small synthetic set), schema/OpenAPI diff check for breaking changes, docker build + scan.
8. **Prompt & model governance**: prompts versioned and hashed, version recorded in every trace and audit event; model IDs only via config (no hard-coded model names).
9. **Deletability**: a `scripts/remove_service.py` (optional) + TEMPLATE_GUIDE checklist: remove folder, remove compose/CI matrix entry, run `make check`.

## Build phases
1. **Foundation**: root `pyproject.toml` (uv workspace), Makefile, pre-commit, CI skeleton, `.env.example`, docs skeleton, delete `unnamed.png`.
2. **libs/core + observability + audit + phi + guardrails** (with fakes and tests).
3. **libs/providers**: ports, registry, `fake` + 1–2 real adapters per port (OpenAI-compatible LLM covers many vendors; pgvector; faster-whisper; Presidio), others stubbed with contract tests.
4. **`_service_template`** and shared API scaffolding (middleware, auth, health, error model, OpenAPI).
5. **Services** in order: preprocessing → rag → summarization → transcription → chatbot (each minimal but runnable end-to-end on fake providers).
6. **Deploy**: Dockerfiles, compose, k8s kustomize, CI workflows incl. security and eval.
7. **Docs**: README, TEMPLATE_GUIDE, ADRs, HIPAA checklist, threat model, runbooks.

## Critical files (representative)
`pyproject.toml`, `libs/providers/registry.py`, `libs/providers/llm/port.py`, `libs/phi/guard.py`, `libs/core/settings.py`, `libs/core/logging.py`, `libs/observability/tracing.py`, `services/_service_template/app/main.py`, `.github/workflows/ci.yml`, `docker-compose.yml`, `TEMPLATE_GUIDE.md`. Nothing existing needs reuse (repo is empty apart from README/.gitignore; keep and extend both).

## Verification
- `uv sync && make check` (ruff, mypy, import-linter, pytest) passes on a fresh clone with no API keys (fake providers).
- `docker compose up` brings up each service; `/healthz`, `/readyz`, `/metrics` respond; one OTel trace with `gen_ai.*` attributes is visible in the collector logs.
- Synthetic-PHI leak test: send PHI-laden request; assert absent from logs, traces, audit log, and error responses; assert fail-closed when the redactor adapter raises.
- Swap test: change `llm.provider`/`vectorstore.provider` via env only and rerun the integration suite.
- Deletability test (CI job): delete each service folder in turn and run `make check` on the rest.
- Eval gate runs on the synthetic RAG set and fails when thresholds are lowered artificially.
