"""Stages: ASR -> diarization -> merge -> PHI redaction -> structured transcript.

Each stage is a plain function so it can be unit-tested and swapped independently.
"""

from pydantic import BaseModel

from aibase.phi import PHIGuard
from aibase.providers.diarization import DiarizerPort, SpeakerTurn
from aibase.providers.stt import STTPort, TranscriptSegment

LOW_CONFIDENCE = 0.5
UNKNOWN = "UNKNOWN"


class TranscriptLine(BaseModel):
    start: float
    end: float
    speaker: str
    text: str
    confidence: float
    low_confidence: bool = False


class Transcript(BaseModel):
    lines: list[TranscriptLine]
    redacted_entities: int
    duration_s: float


def _overlap(seg: TranscriptSegment, turn: SpeakerTurn) -> float:
    return max(0.0, min(seg.end, turn.end) - max(seg.start, turn.start))


def merge(segments: list[TranscriptSegment], turns: list[SpeakerTurn]) -> list[TranscriptLine]:
    lines: list[TranscriptLine] = []
    for seg in segments:
        best = max(turns, key=lambda t: _overlap(seg, t), default=None)
        has_speaker = best is not None and _overlap(seg, best) > 0
        # Cross-talk: refuse to guess a speaker rather than mislabel clinical statements.
        speaker = best.speaker if has_speaker and best and not best.overlap else UNKNOWN
        lines.append(
            TranscriptLine(
                start=seg.start,
                end=seg.end,
                speaker=speaker,
                text=seg.text,
                confidence=seg.confidence,
                low_confidence=seg.confidence < LOW_CONFIDENCE,
            )
        )
    return lines


def redact(lines: list[TranscriptLine], guard: PHIGuard) -> tuple[list[TranscriptLine], int]:
    count = 0
    out: list[TranscriptLine] = []
    for line in lines:
        result = guard.redact(line.text)
        count += len(result.mapping)
        out.append(line.model_copy(update={"text": result.text}))
    return out, count


async def run(
    audio: bytes,
    stt: STTPort,
    diarizer: DiarizerPort,
    guard: PHIGuard,
    language: str | None = None,
) -> Transcript:
    segments = await stt.transcribe(audio, language=language)
    turns = await diarizer.diarize(audio)
    lines, count = redact(merge(segments, turns), guard)
    return Transcript(
        lines=lines, redacted_entities=count, duration_s=max((s.end for s in segments), default=0.0)
    )
