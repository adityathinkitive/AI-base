from aibase.providers.stt.port import TranscriptSegment


class FakeSTT:
    """Treats the audio bytes as UTF-8 text, one segment per line (2s each). Test-only."""

    async def transcribe(
        self, audio: bytes, *, language: str | None = None
    ) -> list[TranscriptSegment]:
        lines = [
            line for line in audio.decode("utf-8", errors="ignore").splitlines() if line.strip()
        ]
        return [
            TranscriptSegment(start=i * 2.0, end=i * 2.0 + 2.0, text=line.strip())
            for i, line in enumerate(lines)
        ]
