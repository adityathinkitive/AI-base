# rag

Ingest → de-identify → chunk → embed → upsert (tenant-scoped); query → embed → retrieve →
drop injection-looking chunks → grounded answer with citations. Refuses when nothing relevant is found.

- `POST /v1/documents` (`rag:write`), `POST /v1/query` (`rag:read`).
- Prompts: `src/rag_service/prompts/<name>/<version>.j2`; add `v2.j2` to roll forward; the prompt tag
  (`name@version#hash`) is stored in the audit log.
- Extend: hybrid search/reranking go in `engine.answer` behind new ports in `aibase.providers`.
- Vendor swap: set `AIBASE_EMBEDDINGS__PROVIDER`, `AIBASE_VECTORSTORE__PROVIDER`, `AIBASE_LLM__PROVIDER`.
