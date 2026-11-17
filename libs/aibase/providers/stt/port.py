from typing import Protocol

from pydantic import BaseModel


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    confidence: float = 1.0
    speaker: str | None = None


class STTPort(Protocol):
    async def transcribe(
        self, audio: bytes, *, language: str | None = None
    ) -> list[TranscriptSegment]: ...
