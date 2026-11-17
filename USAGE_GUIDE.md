# AI-base Usage Guide

Everything you need to start a project from this template, run it, change it, and ship it.
Every command below was run against this repo unless marked **(untested)**.

Contents
1. [Mental model](#1-mental-model)
2. [Prerequisites and first run](#2-prerequisites-and-first-run)
3. [Starting a new project from the template](#3-starting-a-new-project-from-the-template)
4. [Configuration reference](#4-configuration-reference)
5. [Running the services](#5-running-the-services)
6. [Authentication and tenants](#6-authentication-and-tenants)
7. [Service API reference with examples](#7-service-api-reference-with-examples)
8. [Connecting real vendors](#8-connecting-real-vendors)
9. [Writing your own vendor adapter](#9-writing-your-own-vendor-adapter)
10. [Adding a new service](#10-adding-a-new-service)
11. [Adding an endpoint to an existing service](#11-adding-an-endpoint-to-an-existing-service)
12. [Prompts](#12-prompts)
13. [PHI handling rules for your code](#13-phi-handling-rules-for-your-code)
14. [Testing](#14-testing)
15. [Evals](#15-evals)
16. [Observability and audit](#16-observability-and-audit)
17. [Docker, compose and Kubernetes](#17-docker-compose-and-kubernetes)
18. [CI](#18-ci)
19. [Going to production checklist](#19-going-to-production-checklist)
20. [Troubleshooting](#20-troubleshooting)
21. [Known gaps](#21-known-gaps)

---

## 1. Mental model

```
services/<name>/   A deployable FastAPI app. Thin: routes + domain logic. Imports only from libs/.
libs/aibase/       Shared code. Never imports from services/.
```

Three ideas drive everything:

1. **Ports and adapters.** Services never import a vendor. They ask for `providers.llm`, `providers.vectorstore`, etc.
   Those are interfaces (`Protocol`s in `libs/aibase/providers/<kind>/port.py`). Which implementation you get is
   decided by environment variables, so switching vendor = changing config (or adding one adapter file).
2. **PHI never leaves unredacted.** `providers.llm` is automatically wrapped so prompts are de-identified before
   the call and the reply is de-identified after it. If redaction fails, the request is blocked (fail-closed).
3. **Fakes by default.** Out of the box every provider is an offline fake. You can run, test and demo everything
   with no API keys and no network. You turn real vendors on one at a time.

Request flow in every service:

```
rate limit / size limit / request id  ->  JWT auth + scope + tenant  ->  input guardrails
  ->  your logic  ->  providers (LLM guarded)  ->  output guardrails  ->  audit event  ->  response
```

Naming rules you must follow:
- Service folder: `services/<name>/`. Python package inside: `services/<name>/src/<name>_service/` (**must end in `_service`**).
- Entry point of every service: `<name>_service/main.py` with `create_service_app(...)`.

## 2. Prerequisites and first run

Needed: `uv` (https://docs.astral.sh/uv/), `git`. Python 3.12+ is fetched by `uv` automatically.
Optional: Docker (for compose/containers), `make`.

```bash
git clone <your-repo> && cd <your-repo>
uv sync                 # installs core deps + dev tools into .venv (use `uv sync --all-extras` for optional vendor SDKs, large)
make check              # lint + types + boundaries + tests + eval gate. Must be green before you change anything.
```

If `make` is not available, run what it runs:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy libs/aibase
uv run python scripts/check_boundaries.py
uv run pytest --cov
PYTHONPATH=libs uv run python -m aibase.evals.run evals/datasets
```

## 3. Starting a new project from the template

1. On GitHub: **Use this template -> Create a new repository** (or clone and `rm -rf .git && git init`).
2. Remove what you do not need. For each service you do not want (example: chatbot):
   ```bash
   rm -rf services/chatbot
   ```
   Then edit these three places (all are simple deletions):
   - `docker-compose.yml`: delete the `chatbot:` block.
   - `.github/workflows/ci.yml`: remove `chatbot` from both `matrix.service` lists.
   - `deploy/k8s/base/`: delete its manifest and its line in `kustomization.yaml` (only `rag.yaml` exists as the example).
   Test discovery, lint paths and Docker builds are glob-based and need no change.
3. Remove `PLAN.md`, `unnamed.png`, and (if you do not want them) `docs/` entries you will not maintain.
4. Rename the project in `pyproject.toml` (`name`, `description`).
5. Replace placeholders: `registry.example.com` in `deploy/k8s/base/rag.yaml`; create a `.github/CODEOWNERS`.
6. `cp .env.example .env` (never commit `.env`; it is git-ignored).
7. `uv sync && make check`. It must still pass after your deletions.
8. Commit.

Do not delete `libs/aibase/` pieces unless you are sure: `phi`, `audit`, `guardrails` and `core` are used by every service.

## 4. Configuration reference

Config is read from environment variables (and from a `.env` file in the current directory when running locally).
Prefix `AIBASE_`, nested fields use a double underscore: `AIBASE_PHI__FAIL_CLOSED=true`.
Values that are lists/dicts are JSON: `AIBASE_CORS_ORIGINS='["https://app.example.com"]'`.

| Variable | Default | Meaning |
|---|---|---|
| `AIBASE_ENV` | `local` | `local`, `test`, `staging`, `production`. In staging/production the app **refuses to start** unless auth is enabled and PHI is enabled + fail-closed. Also hides `/docs` and `/openapi.json`. |
| `AIBASE_SERVICE_NAME` | per service | Used in logs/traces. Each service sets its own default. |
| `AIBASE_LOG_LEVEL` | `INFO` | Standard levels. |
| `AIBASE_CORS_ORIGINS` | `[]` | JSON list of allowed origins. Empty = no CORS middleware. |
| `AIBASE_LLM__PROVIDER` / `__MODEL` / `__OPTIONS` | `fake` | Adapter name, default model name, constructor kwargs as JSON. |
| `AIBASE_EMBEDDINGS__*` | `fake` | Same shape. |
| `AIBASE_VECTORSTORE__*` | `memory` | Same shape. |
| `AIBASE_STT__*` | `fake` | Speech-to-text. |
| `AIBASE_DIARIZATION__*` | `fake` | Speaker separation. |
| `AIBASE_STORAGE__*` | `local` | Object storage. |
| `AIBASE_QUEUE__*` | `memory` | Background jobs. |
| `AIBASE_CACHE__*` | `memory` | Key/value cache (chat sessions). |
| `AIBASE_PHI__ENABLED` | `true` | Wrap the LLM with redaction. |
| `AIBASE_PHI__REDACTOR` | `regex` | `regex` or `presidio` (or your registered one). |
| `AIBASE_PHI__FAIL_CLOSED` | `true` | If redaction errors, block the request. Never turn off in production. |
| `AIBASE_AUTH__ENABLED` | `false` | Require a JWT. |
| `AIBASE_AUTH__PUBLIC_KEY` | none | PEM public key (or secret for HS256) used to verify tokens. |
| `AIBASE_AUTH__ISSUER` / `__AUDIENCE` | none | Expected `iss` / `aud` claims. Set both in real deployments. |
| `AIBASE_AUTH__ALGORITHMS` | `["RS256"]` | JSON list. |
| `AIBASE_AUTH__TENANT_CLAIM` | `tenant_id` | Claim holding the tenant. |
| `AIBASE_AUTH__SCOPE_CLAIM` | `scope` | Claim holding scopes (space-separated string or list). |
| `AIBASE_OTEL__ENDPOINT` | none | OTLP/HTTP traces endpoint, e.g. `http://otel-collector:4318/v1/traces`. Unset = no export. |
| `AIBASE_AUDIT__PATH` | `./data/audit/audit.jsonl` | Where the audit log is written. |
| `AIBASE_LIMITS__MAX_BODY_BYTES` | 26214400 | Reject larger request bodies (413). |
| `AIBASE_LIMITS__RATE_LIMIT_PER_MINUTE` | 600 | Per client IP, per process (429). |

`request_timeout_s` exists in settings but is **not enforced anywhere yet**; set timeouts at your ingress and on
provider calls (`OpenAICompatLLM(timeout_s=...)`).

`__OPTIONS` is passed as keyword arguments to the adapter constructor, so the keys must match that adapter's
`__init__` parameters. A wrong key fails at startup with a `TypeError` naming it (see Troubleshooting).

## 5. Running the services

Each service is its own app. `PYTHONPATH` must contain `libs` and that service's `src`:

```bash
PYTHONPATH=libs:services/rag/src uv run uvicorn rag_service.main:create_service_app --factory --reload --port 8002
```

Note `--factory`: `create_service_app` is a function that builds the app.

Port suggestions (match `docker-compose.yml`): preprocessing 8001, rag 8002, summarization 8003, transcription 8004, chatbot 8005.

Endpoints present on every service:
- `GET /healthz`: liveness, always `{"status":"ok"}` if the process is up.
- `GET /readyz`: readiness (200 `ready`, or 503 if a readiness check fails; no checks are registered by default, see section 11).
- `GET /metrics`: Prometheus metrics (`http_requests_total`, `http_request_seconds`).
- `GET /docs`: interactive Swagger UI, **only in `local`/`test`**.

All errors use one shape:

```json
{"error": {"code": "guardrail_violation", "message": "request blocked by guardrails",
           "details": {"checks": ["prompt_injection"]}, "request_id": "9f2c..."}}
```

Send `X-Request-ID: <id>` to supply your own; it is echoed back and appears in logs and the audit log.

With Docker: `cp .env.example .env && docker compose up --build` (needs Docker access; not tested in the authoring
environment, see Known gaps).

## 6. Authentication and tenants

**Local dev:** `AIBASE_AUTH__ENABLED=false` (default). Every request acts as user `dev-user`, tenant `dev-tenant`, all scopes.

**Real deployments:** your identity provider issues a JWT; the service only **verifies** it. Required claims:
`sub`, `exp`, the tenant claim (default `tenant_id`), and scopes in `scope`.

Scopes used by the built-in services:

| Service | Scopes |
|---|---|
| preprocessing | `preprocess:run` |
| rag | `rag:write` (ingest), `rag:read` (query) |
| summarization | `summarize:run` |
| transcription | `transcribe:write`, `transcribe:read`, `transcribe:stream` |
| chatbot | `chat:write` |
| template | `template:ask` |

A token with scope `*` passes every check (the dev principal uses it; do not mint it in production).

How to try auth locally (verified): generate a key pair, run a service with auth on, mint a token.

```bash
openssl genrsa -out /tmp/priv.pem 2048 && openssl rsa -in /tmp/priv.pem -pubout -out /tmp/pub.pem

AIBASE_ENV=production AIBASE_AUTH__ENABLED=true \
AIBASE_AUTH__PUBLIC_KEY="$(cat /tmp/pub.pem)" AIBASE_AUTH__AUDIENCE=ai-api AIBASE_AUTH__ISSUER=https://idp.local \
PYTHONPATH=libs:services/rag/src uv run uvicorn rag_service.main:create_service_app --factory --port 8124
```

```python
import time, jwt

token = jwt.encode(
    {
        "sub": "dr-1",
        "tenant_id": "clinic-a",
        "aud": "ai-api",
        "iss": "https://idp.local",
        "exp": int(time.time()) + 3600,
        "scope": "rag:read rag:write",
    },
    open("/tmp/priv.pem").read(),
    algorithm="RS256",
)
print(token)
```

Observed behaviour: no token -> 401; valid token -> 200/201; token lacking the scope -> 403; `/docs` -> 404 in production.

**Tenants.** The tenant comes from the token, never from the request body. RAG data is stored per tenant; a tenant
can never read another tenant's chunks. Chat sessions are keyed by tenant + user + session id. Transcription jobs
return 404 (not 403) for another tenant's job so IDs cannot be probed.

## 7. Service API reference with examples

Examples assume local dev (auth off). With auth on, add `-H "Authorization: Bearer $TOKEN"`.

### preprocessing: `POST /v1/preprocess`

De-identifies and chunks text. Steps run in order: `normalize_unicode`, `strip_control_chars`, `collapse_whitespace`, `deidentify`.

```bash
curl -s localhost:8001/v1/preprocess -H 'content-type: application/json' -d '{
  "text": "Patient   Jane, SSN 123-45-6789, email jane@example.com. Long note ...",
  "steps": ["normalize_unicode","strip_control_chars","collapse_whitespace","deidentify"],
  "chunk_size": 1000, "chunk_overlap": 100 }'
# {"chunks":["Patient Jane, SSN [SSN_1], email [EMAIL_1]. Long note ..."],"phi_entities_removed":2}
```
`steps` defaults to all four. Unknown step -> 400 listing the available ones. `chunk_overlap` must be smaller than `chunk_size`.
Add a step: write `def my_step(doc: Document) -> Document` in `pipeline.py`, register the name in `build_steps`.

### rag: ingest then query

```bash
curl -s localhost:8002/v1/documents -H 'content-type: application/json' \
  -d '{"text":"Metformin is first line therapy for type 2 diabetes.","metadata":{"source":"guideline-12"}}'
# 201 {"doc_id":"6b02...","chunks":1}

curl -s localhost:8002/v1/query -H 'content-type: application/json' \
  -d '{"question":"first line therapy for type 2 diabetes","top_k":4}'
# {"answer":"...","citations":[{"id":"6b02...:0","score":0.53,"text":"..."}],"prompt":"answer@v1#697c74f8"}
```
Behaviour to know:
- Text is de-identified **before** indexing, so the vector store never holds raw PHI.
- Retrieved chunks that look like prompt-injection are dropped. If nothing relevant remains, the answer is the fixed
  refusal "I don't have enough information in the provided documents." and the LLM is **not called**.
- Questions over 4000 chars or containing injection patterns return 422.
- With default fakes the "answer" just echoes the prompt. Connect a real LLM (section 8) to get real answers.
- `memory` vector store loses data on restart; fine for dev only.

### summarization: `POST /v1/summaries`

```bash
curl -s localhost:8003/v1/summaries -H 'content-type: application/json' \
  -d '{"text":"Patient reports cough for 3 days ...","format":"soap"}'
# {"summary":"...","chunks":1,"prompts":["map@v1#...","reduce@v1#..."]}
```
`format`: `general` (default; a single-chunk text needs one LLM call) or `soap` (always adds a reduce step that forces
Subjective/Objective/Assessment/Plan and "Not documented" for missing sections). Long text is split at ~6000 chars,
summarised in parallel (max 4 at once), then combined.

### transcription: batch (jobs) and streaming

```bash
# 1) upload -> 202 + job id. Allowed types: audio/wav, audio/x-wav, audio/mpeg, audio/mp4, audio/webm, audio/ogg, text/plain
curl -s localhost:8004/v1/transcriptions -F "file=@visit.wav;type=audio/wav" -F "language=en"
# {"job_id":"ab12..."}

# 2) poll until state is succeeded or failed
curl -s localhost:8004/v1/transcriptions/ab12...
# {"job_id":"...","state":"succeeded","transcript":{"lines":[{"start":0,"end":2,"speaker":"SPEAKER_0",
#   "text":"...","confidence":0.93,"low_confidence":false}],"redacted_entities":1,"duration_s":2}}
```
- With the fake STT you can test without audio: send a `text/plain` file; each line becomes a 2-second segment.
- The transcript is already PHI-redacted. Raw audio is deleted after processing.
- Cross-talk or no speaker overlap -> speaker `UNKNOWN` (no guessing). Confidence < 0.5 -> `low_confidence: true`.
- States: `queued`, `running`, `succeeded`, `failed` (`error` holds the exception class name only).
- The default queue is in-process: jobs are lost if the process restarts and are not shared across replicas.
  Use a real queue adapter in production (section 9).

Streaming: `WS /v1/stream`. Send one binary frame per audio chunk; you get `{"chunk":0,"lines":[...]}` back per chunk.
Needs scope `transcribe:stream`. Treat it as a live preview; create the authoritative record via the batch endpoint.

### chatbot

```bash
curl -s localhost:8005/v1/chat -H 'content-type: application/json' \
  -d '{"message":"What is metformin used for?"}'
# {"session_id":"dde0...","reply":"...","escalated":false}

# continue the conversation: pass the session_id back (8-64 chars, letters/digits/_/-)
curl -s localhost:8005/v1/chat -H 'content-type: application/json' \
  -d '{"message":"Any side effects?","session_id":"dde056f565fe42efba09127f343043ce"}'

# server-sent events stream
curl -N localhost:8005/v1/chat/stream -H 'content-type: application/json' -d '{"message":"hello"}'
# data: {"token":"..."} ... data: {"done":true,"session_id":"..."}

curl -X DELETE localhost:8005/v1/chat/<session_id>      # 204, erases history
```
- Emergency words (suicide, chest pain, can't breathe, stroke, overdose, severe bleeding ...) return a fixed
  escalation message with `"escalated": true` and **never call the model**. The list is `EMERGENCY` in
  `conversation.py`; have clinical owners review it.
- History keeps the last 10 turns, 1 hour TTL, de-identified.
- Streaming output is redacted per word chunk by the guarded LLM; non-streaming replies are also rejected (422) if
  PHI remains after redaction.
- There are no tools yet; add them in a `tools/` module (see the README of the service).

## 8. Connecting real vendors

All vendor choices are environment variables. Example, an OpenAI-format server (OpenAI, Azure OpenAI gateway, vLLM,
Ollama, LiteLLM, Together, ...):

```bash
AIBASE_LLM__PROVIDER=openai_compat
AIBASE_LLM__MODEL=my-model
AIBASE_LLM__OPTIONS='{"base_url":"https://my-host/v1","api_key":"sk-..."}'
AIBASE_EMBEDDINGS__PROVIDER=openai_compat
AIBASE_EMBEDDINGS__OPTIONS='{"base_url":"https://my-host/v1","model":"text-embed","dimension":1024,"api_key":"sk-..."}'
```
Verified with a mock server: the upstream received `Authorization: Bearer sk-...`, the configured model, and the
user message **already redacted** (`Email me at [EMAIL_1] ...`).

Adapters that exist:

| Kind | Name | Needs | Options (constructor kwargs) |
|---|---|---|---|
| llm | `fake`, `openai_compat` | none | `base_url`, `api_key`, `model`, `timeout_s` |
| embeddings | `fake`, `openai_compat` | none | `base_url`, `model`, `dimension`, `api_key`, `timeout_s` |
| vectorstore | `memory` | none | none |
| stt | `fake`, `faster_whisper` | `uv sync --extra faster-whisper` | `model_size`, `device`, `compute_type` |
| diarization | `fake` | none | none |
| storage | `local` | none | `root` |
| queue | `memory` | none | none |
| cache | `memory`, `redis` | `uv sync --extra redis` | `url` |
| redactor (`AIBASE_PHI__REDACTOR`) | `regex`, `presidio` | `uv sync --extra presidio` + a spaCy model | `language`, `score_threshold` |

Listing what is registered: `uv run python -c "from aibase.providers import registry; print(registry.available('llm'))"`
(run with `PYTHONPATH=libs`).

Important: `regex` redaction only finds structured identifiers (SSN, email, phone, MRN, dates, IPs, titled names like
"Dr. Smith"). It **cannot find ordinary names or addresses**. For real PHI use `presidio` or your own NER adapter and
measure its recall on your data.

In containers, install the extras you need: `docker build --build-arg SERVICE=rag --build-arg EXTRAS="--extra presidio" ...`.

## 9. Writing your own vendor adapter

Example: a custom LLM vendor. (Verified end to end: with `AIBASE_LLM__PROVIDER=my_vendor` the chatbot replied "yo!".)

1. Create `libs/aibase/providers/llm/my_vendor.py` implementing the port (`libs/aibase/providers/llm/port.py`):

```python
from collections.abc import AsyncIterator
from aibase.providers.llm import LLMMessage, LLMResponse, Usage


class MyVendorLLM:
    provider_name = "my_vendor"

    def __init__(self, api_key: str, base_url: str, model: str = "") -> None:
        # import the vendor SDK HERE (inside the adapter), never at package top level
        self._model = model
        ...

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse: ...  # call the vendor, return LLMResponse(text=..., model=..., usage=Usage(input_tokens=..., output_tokens=...))

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        ...
        yield "token "
```
2. Register it, in one of two ways:
   - Permanent: add `("llm", "my_vendor"): "aibase.providers.llm.my_vendor:MyVendorLLM",` to `_BUILTIN` in
     `libs/aibase/providers/registry.py`. Adapters are imported lazily, so a missing SDK only fails if you select it.
   - From app code, before the app is created: `registry.register("llm", "my_vendor", MyVendorLLM)`
     (put it at the top of a service's `main.py`, above `create_app(...)`).
3. Add the SDK as an optional extra in `pyproject.toml` (`[project.optional-dependencies]`), never in core `dependencies`.
4. Select it: `AIBASE_LLM__PROVIDER=my_vendor` and `AIBASE_LLM__OPTIONS='{"api_key":"...","base_url":"..."}'`.
5. Errors: raise `ProviderError` (vendor rejected request), `ProviderUnavailable` (down/timeouts). Use
   `aibase.core.resilience.retry_async` and `CircuitBreaker` as `openai_compat.py` does. Never put prompt text in an
   exception message or span.
6. Test it. For stores and caches, reuse the contract tests:

```python
from aibase.testing.contracts import vectorstore_contract, cache_contract


async def test_my_store_honours_the_port():
    await vectorstore_contract(MyVectorStore(...))
```
The vectorstore contract checks ranking, metadata filters, delete and, importantly, **tenant isolation**.

For other kinds, implement the matching port and register under the same kind string:
`embeddings`, `vectorstore`, `stt`, `diarization`, `storage`, `queue`, `cache`, `redactor`. Ports:
`libs/aibase/providers/<kind>/port.py` (redactor: `libs/aibase/phi/ports.py`). Rules specific to each:
- vectorstore: `tenant_id` is the first argument of every call and must scope every query.
- storage: must encrypt at rest and reject path traversal (see `local.py`).
- queue: external brokers must carry opaque IDs, not PHI, in payloads. Handlers are registered via `register(task, fn)`.
- redactor: only needs `detect(text) -> list[Entity]` (label, start, end); masking is done for you by `PHIGuard`.

## 10. Adding a new service

Verified in a temp copy: boundaries pass and the copied test passes.

```bash
cp -r services/_service_template services/billing
mv services/billing/src/template_service services/billing/src/billing_service
sed -i 's/template_service/billing_service/g; s/"template"/"billing"/; s/Template Service/Billing Service/' \
  services/billing/src/billing_service/*.py services/billing/tests/*.py
uv run python scripts/check_boundaries.py
uv run pytest -q services/billing
PYTHONPATH=libs:services/billing/src uv run uvicorn billing_service.main:create_service_app --factory --port 8006
```
Then:
1. Edit `api.py`: change the router prefix/tags, scope name (`template:ask` -> `billing:run`), request/response models, logic.
2. Add it to `docker-compose.yml` (copy a block, change `SERVICE: billing` and the port) and to both `matrix.service`
   lists in `.github/workflows/ci.yml`. Add a k8s manifest by copying `deploy/k8s/base/rag.yaml` and replacing `rag`.
3. Add a `README.md` listing endpoints and scopes.
4. Rules enforced by `scripts/check_boundaries.py`: a service may import `aibase.*` but never another `*_service`.
   If two services need the same code, move it into `libs/aibase/` (respecting the layers in `docs/architecture.md`).

## 11. Adding an endpoint to an existing service

Template for every endpoint (this is the pattern all five services use):

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from aibase.api import Principal, get_audit, get_providers, record_audit, require_scopes
from aibase.audit import AuditSink
from aibase.guardrails import default_input_pipeline
from aibase.providers.factory import Providers
from aibase.providers.llm import LLMMessage

router = APIRouter(prefix="/v1", tags=["billing"])
input_guard = default_input_pipeline(max_chars=10_000)


class CodeRequest(BaseModel):
    note: str = Field(min_length=1, max_length=10_000)


class CodeResponse(BaseModel):
    codes: list[str]


@router.post("/codes", response_model=CodeResponse)
async def suggest_codes(
    body: CodeRequest,
    principal: Principal = Depends(
        require_scopes("billing:run")
    ),  # 1. auth + scope (principal.tenant_id available)
    providers: Providers = Depends(get_providers),  # 2. vendor-agnostic providers
    audit: AuditSink = Depends(get_audit),
) -> CodeResponse:
    input_guard.enforce(body.note)  # 3. injection / length (raises 422)
    reply = await providers.llm.generate(
        [LLMMessage(role="user", content=body.note)]
    )  # 4. PHI auto-redacted in/out
    record_audit(audit, principal, "billing.codes")  # 5. audit event (opaque IDs only)
    return CodeResponse(codes=reply.text.split(","))
```
Checklist for every endpoint: scope, tenant scoping on any storage/vector access, input guardrail on user text,
audit event, Pydantic models with length limits, **no PHI in `resource`/audit/log fields**.

Structured JSON from a model: `from aibase.providers.llm import generate_structured; result = await generate_structured(providers.llm, messages, MyPydanticModel)`
(validates and retries once; raises `ProviderError` if still invalid).

Readiness checks (so `/readyz` reflects dependencies): pass `readiness=[check_fn]` to `create_app(...)` in `main.py`,
where `async def check_fn() -> bool`.

Errors: raise from `aibase.core.errors` (`BadRequest`, `NotFound`, `Forbidden`, `ProviderError`, ...). They are
rendered in the standard envelope. Do not return raw exception text to clients.

## 12. Prompts

Location: `services/<svc>/src/<pkg>/prompts/<prompt_name>/v1.j2` (Jinja2, undefined variables are an error).

```python
from pathlib import Path
from aibase.prompts import PromptRegistry

PROMPTS = PromptRegistry(Path(__file__).parent / "prompts")
p = PROMPTS.render("answer", sources=[...], question="...")  # latest version
p = PROMPTS.render("answer", "v1", sources=[...], question="...")  # pinned version
p.text  # the rendered prompt;   p.tag -> "answer@v1#697c74f8" (name@version#content-hash)
```
- **Never edit a released version.** Copy to `v2.j2`, edit, ship; roll back by pinning `v1` or reverting.
- Put `p.tag` into the audit event (`prompt_version=p.tag`) so any output can be traced to the exact prompt.
- Treat retrieved/user content as untrusted inside prompts (the RAG prompt shows how).
- Prompts must contain no secrets; assume they can leak.

## 13. PHI handling rules for your code

The template handles most of this for you; the rules are about not undoing it.

1. Call the model only through `providers.llm`. Never instantiate an adapter yourself in a route.
2. Do not log request bodies, prompts, transcripts or model output. Log IDs, counts, durations. (A global scrubber
   catches regex-detectable identifiers in logs and tracebacks as a safety net, not a licence.)
3. Do not put PHI in audit `resource`, span attributes, queue payloads to external brokers, cache keys, file names, or metrics labels.
4. Store only de-identified text (RAG chunks, transcripts and chat history already are).
5. Never copy real patient data into tests/fixtures/evals. Use `aibase.testing.SYNTHETIC_PHI` and `assert_no_phi(...)`.
6. Need the original values back? `PHIGuard.redact(text)` returns `.mapping`; `result.restore(text)` swaps placeholders
   back. Keep the mapping in memory for the request only.
7. Do not set `AIBASE_PHI__FAIL_CLOSED=false` outside throwaway experiments.

## 14. Testing

Run: `uv run pytest` (all), `uv run pytest services/rag` (one service), `uv run pytest -k phi` (by name),
`uv run pytest --cov` (coverage; fails under 80%).

Tests live next to the code: `libs/aibase/tests/`, `services/<svc>/tests/`. Everything runs offline on fakes.

Patterns used (copy from the existing tests):

```python
from fastapi.testclient import TestClient
from aibase.providers.factory import build_providers
from aibase.providers.guarded import GuardedLLM
from aibase.providers.llm.fake import FakeLLM
from aibase.testing import SYNTHETIC_PHI, assert_no_phi, make_settings

settings = make_settings()  # env="test", ignores your .env
providers = build_providers(settings)
llm = FakeLLM("fixed reply")  # or FakeLLM(lambda messages: "dynamic")
providers.llm = GuardedLLM(
    llm, providers.phi
)  # keep the PHI guard in the loop when testing PHI behaviour
client = TestClient(create_service_app(settings, providers))
...
assert_no_phi(
    " ".join(m.content for call in llm.calls for m in call)
)  # what the "vendor" actually received
```
- `FakeLLM.calls` records every prompt sent, so you can assert on what left the system.
- Background jobs (transcription) need the client as a context manager: `with TestClient(app) as c:` so the event loop
  stays alive until the job finishes (see `services/transcription/tests/test_api.py`).
- Test auth by building settings with `make_settings(auth={"enabled": True, "public_key": ..., ...})` (see `libs/aibase/tests/test_core_api.py`).

Quality gates (run all with `make check`): `ruff` (lint+format; `make format` to autofix), `mypy` (strict, libs only),
`scripts/check_boundaries.py`, pytest with coverage, eval gate.

## 15. Evals

`make eval` runs every `evals/datasets/*.json` through the configured embeddings + vector store and fails the build if
a metric drops below its threshold. The shipped `retrieval_smoke.json` is a tiny toy (4 documents).

Dataset format:

```json
{ "thresholds": {"precision@3": 0.3, "recall@3": 0.9, "mrr": 0.8},
  "documents": [{"id": "d1", "text": "..."}],
  "cases": [{"query": "...", "relevant": ["d1"]}] }
```
To make it meaningful: add your own **synthetic or properly de-identified** documents/questions, raise thresholds to
just below current scores, and run with real embeddings
(`AIBASE_EMBEDDINGS__PROVIDER=openai_compat ... make eval`). Metrics provided: `precision_at_k`, `recall_at_k`, `mrr`
in `libs/aibase/evals/metrics.py`. For LLM-judged metrics (faithfulness, relevance) implement `MetricPort` with your
tool of choice (Ragas, DeepEval, your own judge). None is wired into CI by default because it needs a model and costs money.

## 16. Observability and audit

**Logs:** one JSON object per line on stdout, with `request_id` and `tenant_id`. Collect with your platform's log agent.

**Metrics:** scrape `GET /metrics`.

**Traces:** set `AIBASE_OTEL__ENDPOINT` to any OTLP/HTTP traces endpoint. The compose stack ships a collector
(`deploy/otel-collector.yaml`) printing spans to its log; edit the `exporters:` section to forward to your backend
(Langfuse, Tempo, Jaeger, Datadog, ...). LLM calls made via `openai_compat` produce a span with `gen_ai.*`
attributes (operation, system, model, token usage) and **no prompt/completion content**. In your own adapter use
`from aibase.observability import llm_span` as in `openai_compat.py`. The GenAI semantic conventions are
experimental and may change.

**Audit log:** JSON lines at `AIBASE_AUDIT__PATH`, one per `record_audit(...)` call:
`actor, tenant_id, action, resource, outcome, request_id, model, prompt_version, ts, prev_hash, hash`.
Each record hashes the previous one. To verify integrity:

```python
# PYTHONPATH=libs
from aibase.audit import FileAuditSink

print(
    FileAuditSink("./data/audit/audit.jsonl").verify()
)  # False if any line was edited or removed from the middle
```
This detects tampering; it does not prevent it. In production write to append-only/WORM storage or ship to your
SIEM by implementing `AuditSink.write`.

## 17. Docker, compose and Kubernetes

**Image** (one Dockerfile for every service, chosen by build arg): non-root user, slim base, healthcheck,
dependencies from `uv.lock`.

```bash
docker build -f deploy/docker/Dockerfile --build-arg SERVICE=rag -t my-registry/rag:1.0.0 .
docker build -f deploy/docker/Dockerfile --build-arg SERVICE=rag --build-arg EXTRAS="--extra presidio" -t my-registry/rag:1.0.0 .
docker run --rm -p 8000:8000 --read-only --tmpfs /tmp -e AIBASE_AUDIT__PATH=/tmp/audit.jsonl my-registry/rag:1.0.0
```
**(untested: Docker was not accessible when this was written.)** If the build fails, the likely causes are the `uv`
image tag in the first `FROM`/`COPY --from` line or a missing `uv.lock`; fix and tell your team.

**Compose** (dev only): `cp .env.example .env && docker compose up --build`. Services start on ports 8001-8005 with
read-only filesystems, dropped capabilities, an audit volume and an OTel collector. `docker compose --profile redis up`
adds Redis (then set `AIBASE_CACHE__PROVIDER=redis` and `AIBASE_CACHE__OPTIONS='{"url":"redis://redis:6379/0"}'`).

**Kubernetes:** `deploy/k8s/base/rag.yaml` is a complete example for one service: Deployment (non-root, read-only
root fs, probes, resource limits), Service, HPA, PodDisruptionBudget, default-deny NetworkPolicy. To use:
1. Copy for each service, replace `rag`.
2. Pin the image by digest; create the `<svc>-secrets` Secret from your secret manager (API keys, JWT public key, etc.).
3. Complete the NetworkPolicy egress `TODO` with your LLM / vector store endpoints, otherwise outbound calls are blocked.
4. `AIBASE_ENV=production` is already set, so the pod will not start without auth and PHI settings. Set
   `AIBASE_AUTH__ENABLED=true`, `AIBASE_AUTH__PUBLIC_KEY`, `AIBASE_AUTH__ISSUER`, `AIBASE_AUTH__AUDIENCE` in the secret.
5. Run more than one replica only after replacing the in-process pieces (queue, cache, rate limiter, vector store, audit file); see Known gaps.

## 18. CI

`.github/workflows/ci.yml` on every PR: lint, types, boundaries, tests+coverage, eval gate; then a **deletability** job
(deletes each service in turn and re-runs boundaries + tests) and a Docker build + Trivy scan per service.
`.github/workflows/security.yml`: pip-audit, bandit, gitleaks (also weekly). Dependabot is configured for uv, Actions, Docker.
Install local hooks once: `uv run pre-commit install`.
When you add or remove a service, update the `matrix.service` lists. The workflows were not run in the authoring environment.

## 19. Going to production checklist

Do these in order; the repo's `docs/hipaa-checklist.md` and `docs/threat-model.md` have the full lists.

1. Real adapters for: vector store, durable queue (workers in a separate deployment), encrypted object storage, diarization.
2. Replace `regex` redaction with an NER-grade redactor and measure recall on de-identified samples of your data.
3. BAAs with every vendor that can see PHI; configure zero-retention for LLM providers.
4. Set `AIBASE_ENV=production`, JWT verification, TLS at the ingress, secrets from a secret manager.
5. Send traces/metrics/logs to your platform; send the audit log to append-only storage.
6. Shared rate limiting (the built-in limiter is per process and per client IP).
7. Real eval datasets in CI; add faithfulness evals for summarization/RAG.
8. Clinical review of the emergency-escalation list, the system prompts and any generated clinical text; keep a human in the loop.
9. Load-test; set provider timeouts, token budgets and autoscaling targets.
10. Run the runbook drills in `docs/runbooks.md` (PHI leak, provider outage).

## 20. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ModuleNotFoundError: aibase` | `PYTHONPATH` missing. Use `PYTHONPATH=libs:services/<svc>/src`, or run through `uv run pytest`. |
| `TypeError: FakeLLM.__init__() got an unexpected keyword argument 'base_url'` | `AIBASE_LLM__OPTIONS` set while `AIBASE_LLM__PROVIDER=fake`. Options must match the selected adapter; unset them or switch provider. |
| `ConfigError: unknown llm provider 'x'; available: [...]` | Typo, or custom adapter not registered before `create_app`. |
| `ConfigError: ... provider '...' is not installed` | Missing extra: `uv sync --extra <name>` (and a spaCy model for Presidio). |
| App exits at start with `auth.enabled must be true in staging/production` | By design. Enable auth or use `AIBASE_ENV=local`. |
| 401 `missing bearer token` / `invalid or expired token` | Wrong key/issuer/audience, expired `exp`, or missing `sub`. |
| 403 `insufficient scope` | Token `scope` lacks the endpoint's scope (section 6). |
| 422 `guardrail_violation` | Input matched injection patterns or exceeded the length cap; `details.checks` says which. |
| 422 `validation_error` | Body does not match the schema; response lists field paths only (input values are deliberately not echoed). |
| 429 | Rate limit (per IP per minute). Raise `AIBASE_LIMITS__RATE_LIMIT_PER_MINUTE` or fix the client. |
| 500 `phi_redaction_failed` | Redactor raised; requests are blocked by design. Fix/rollback the redactor. |
| 502 / 503 `provider_*` | Vendor rejected or is unreachable; the circuit breaker opens after 5 consecutive failures for 30s. |
| Transcription job stays `queued` in tests | Use `with TestClient(app) as client:`. |
| Transcription job disappears after restart | In-memory queue; use a durable queue adapter. |
| RAG returns the refusal text | No chunk scored above 0.05, or all matches looked like injection. With the fake embeddings only word overlap matters. |
| `/docs` returns 404 | Expected when `AIBASE_ENV` is `staging`/`production`. |
| mypy/ruff complaints after your edits | `make format`, then fix remaining; mypy is strict on `libs/` only. |
| Boundaries failure: `layer 'x' must not import 'y'` | Move the shared code down a layer (see `docs/architecture.md`), do not add the import. |

## 21. Known gaps

Being explicit so nobody assumes otherwise:
- Docker image, compose stack, k8s manifest and GitHub workflows have not been executed by the author.
- Only these real adapters exist: `openai_compat` (LLM, embeddings), `faster_whisper`, `redis`, `presidio`. The Redis,
  faster-whisper and Presidio adapters have no automated tests. Vector store, queue, storage (encrypted), diarization
  are fake/in-memory/local only.
- Regex redaction misses free-text names/addresses.
- Guardrails are regex heuristics, not a classifier.
- Rate limiter, session cache, queue, vector store and audit file are per-process by default.
- `request_timeout_s` setting is not enforced.
- The eval dataset is a 4-document toy.
- Long-audio chunking for transcription is not implemented (the whole file is sent to the STT adapter at once).
- Compliance is your responsibility; this template supports it but does not make a deployment compliant.
