from fastapi.testclient import TestClient

from aibase.testing import SYNTHETIC_PHI, assert_no_phi, make_settings
from preprocessing_service.main import create_service_app
from preprocessing_service.pipeline import chunk_text


def client() -> TestClient:
    return TestClient(create_service_app(make_settings()))


def test_pipeline_deidentifies_and_chunks():
    text = f"Patient   record\x00 {SYNTHETIC_PHI['ssn']} {SYNTHETIC_PHI['email']}. " + "word " * 100
    response = client().post(
        "/v1/preprocess", json={"text": text, "chunk_size": 100, "chunk_overlap": 10}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["phi_entities_removed"] == 2
    assert len(body["chunks"]) > 1
    assert_no_phi(response.text)
    assert "\x00" not in response.text


def test_unknown_step_rejected():
    response = client().post("/v1/preprocess", json={"text": "x", "steps": ["nope"]})
    assert response.status_code == 400


def test_chunk_overlap_must_be_smaller():
    response = client().post(
        "/v1/preprocess", json={"text": "x" * 500, "chunk_size": 100, "chunk_overlap": 100}
    )
    assert response.status_code == 400


def test_chunking_covers_all_text():
    text = " ".join(f"w{i}" for i in range(200))
    chunks = chunk_text(text, 80, 10)
    assert all(len(c) <= 80 for c in chunks)
    assert chunks[0].startswith("w0") and chunks[-1].endswith("w199")
