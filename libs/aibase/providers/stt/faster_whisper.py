import asyncio
import io
import math
from typing import Any

from aibase.core.errors import ConfigError
from aibase.providers.stt.port import TranscriptSegment


class FasterWhisperSTT:
    """Self-hosted ASR. Requires `uv sync --extra faster-whisper`."""

    def __init__(
        self, model_size: str = "small", device: str = "auto", compute_type: str = "int8"
    ) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ConfigError(
                "faster-whisper not installed; run `uv sync --extra faster-whisper`"
            ) from exc
        self._model: Any = WhisperModel(model_size, device=device, compute_type=compute_type)

    async def transcribe(
        self, audio: bytes, *, language: str | None = None
    ) -> list[TranscriptSegment]:
        return await asyncio.to_thread(self._run, audio, language)

    def _run(self, audio: bytes, language: str | None) -> list[TranscriptSegment]:
        segments, _ = self._model.transcribe(io.BytesIO(audio), language=language, vad_filter=True)
        return [
            TranscriptSegment(
                start=s.start, end=s.end, text=s.text.strip(), confidence=math.exp(s.avg_logprob)
            )
            for s in segments
        ]
