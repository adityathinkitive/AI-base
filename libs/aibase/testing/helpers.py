from typing import Any

from aibase.core.settings import Settings

# Fabricated identifiers only. Never put real patient data in tests or fixtures.
SYNTHETIC_PHI = {
    "ssn": "123-45-6789",
    "email": "jane.doe@example.com",
    "phone": "415-555-0132",
    "mrn": "MRN: A1234567",
    "dob": "04/12/1961",
    "name": "Dr. Alice Smith",
}


def assert_no_phi(blob: str) -> None:
    leaked = [kind for kind, value in SYNTHETIC_PHI.items() if value in blob]
    assert not leaked, f"PHI leaked into output: {leaked}"


def make_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {"env": "test", "service_name": "test"}
    return Settings(_env_file=None, **{**base, **overrides})
