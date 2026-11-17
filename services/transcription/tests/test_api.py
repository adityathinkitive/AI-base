import time

import pytest
from fastapi.testclient import TestClient

from aibase.phi import PHIGuard
from aibase.phi.regex_redactor import RegexRedactor
from aibase.providers.diarization import SpeakerTurn
from aibase.providers.stt import TranscriptSegment
from aibase.testing import SYNTHETIC_PHI, assert_no_phi, make_settings
from transcription_service import pipeline
from transcription_service.main import create_service_app

AUDIO = (
    f"Hello doctor, my SSN is {SYNTHETIC_PHI['ssn']}\nI have had chest pain for two days".encode()
)


@pytest.fixture
def client(tmp_path):
    settings = make_settings(storage={"provider": "local", "options": {"root": str(tmp_path)}})
    # Context manager keeps one event loop alive so queued background jobs can finish.
    with TestClient(create_service_app(settings)) as c:
        yield c


def poll(c: TestClient, job_id: str) -> dict:
    for _ in range(50):
        body = c.get(f"/v1/transcriptions/{job_id}").json()
        if body["state"] in ("succeeded", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_batch_flow_redacts_and_deletes_audio(client, tmp_path):
    c = client
    response = c.post("/v1/transcriptions", files={"file": ("a.txt", AUDIO, "text/plain")})
    assert response.status_code == 202
    body = poll(c, response.json()["job_id"])
    assert body["state"] == "succeeded"
    assert [line["speaker"] for line in body["transcript"]["lines"]] == ["SPEAKER_0", "SPEAKER_1"]
    assert body["transcript"]["redacted_entities"] == 1
    assert_no_phi(str(body))
    assert not list((tmp_path / "dev-tenant" / "audio").glob("*")), "raw audio must not be retained"


def test_rejects_bad_media_type_and_empty(client, tmp_path):
    c = client
    assert (
        c.post(
            "/v1/transcriptions", files={"file": ("a.exe", b"x", "application/x-msdownload")}
        ).status_code
        == 400
    )
    assert (
        c.post("/v1/transcriptions", files={"file": ("a.txt", b"", "text/plain")}).status_code
        == 400
    )


def test_unknown_job_404(client):
    assert client.get("/v1/transcriptions/nope").status_code == 404


def test_websocket_stream_redacts(client, tmp_path):
    c = client
    with c.websocket_connect("/v1/stream") as ws:
        ws.send_bytes(AUDIO)
        message = ws.receive_json()
    assert message["chunk"] == 0 and len(message["lines"]) == 2
    assert_no_phi(str(message))


def test_merge_suppresses_crosstalk_and_flags_low_confidence():
    segments = [
        TranscriptSegment(start=0, end=2, text="a", confidence=0.9),
        TranscriptSegment(start=2, end=4, text="b", confidence=0.2),
        TranscriptSegment(start=10, end=12, text="c", confidence=0.9),
    ]
    turns = [
        SpeakerTurn(start=0, end=2, speaker="S0"),
        SpeakerTurn(start=2, end=4, speaker="S1", overlap=True),
    ]
    lines = pipeline.merge(segments, turns)
    assert [x.speaker for x in lines] == ["S0", "UNKNOWN", "UNKNOWN"]
    assert lines[1].low_confidence and not lines[0].low_confidence
    redacted, count = pipeline.redact(lines, PHIGuard(RegexRedactor()))
    assert count == 0 and len(redacted) == 3
