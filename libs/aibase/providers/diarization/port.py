from typing import Protocol

from pydantic import BaseModel


class SpeakerTurn(BaseModel):
    start: float
    end: float
    speaker: str
    overlap: bool = False


class DiarizerPort(Protocol):
    async def diarize(self, audio: bytes) -> list[SpeakerTurn]: ...
