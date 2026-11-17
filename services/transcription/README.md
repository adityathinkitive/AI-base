# transcription

One pipeline, two entry points:

- Batch: `POST /v1/transcriptions` (multipart, scope `transcribe:write`) → job id → `GET /v1/transcriptions/{id}`
  (`transcribe:read`). Raw audio is deleted after processing; stored transcripts are already PHI-redacted.
- Streaming: `WS /v1/stream` (scope `transcribe:stream`) for live dictation; produce the authoritative record via batch.

Stages (`pipeline.py`): ASR → diarization → merge (cross-talk ⇒ `UNKNOWN` speaker, low-confidence flagged) → redaction.

Vendor swap: `AIBASE_STT__PROVIDER` (`faster_whisper` built in, or register your own via `aibase.providers.registry.register`),
`AIBASE_DIARIZATION__PROVIDER`, `AIBASE_QUEUE__PROVIDER`, `AIBASE_STORAGE__PROVIDER`.

TODO before production: long-audio chunking with overlap in a real worker, a real diarization adapter,
an encrypted object-store adapter, a durable queue adapter.
