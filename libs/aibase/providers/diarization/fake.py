from aibase.providers.diarization.port import SpeakerTurn


class FakeDiarizer:
    """Alternates SPEAKER_0/SPEAKER_1 every 2s line, matching FakeSTT's segment timing."""

    async def diarize(self, audio: bytes) -> list[SpeakerTurn]:
        lines = [
            line for line in audio.decode("utf-8", errors="ignore").splitlines() if line.strip()
        ]
        return [
            SpeakerTurn(start=i * 2.0, end=i * 2.0 + 2.0, speaker=f"SPEAKER_{i % 2}")
            for i in range(len(lines))
        ]
