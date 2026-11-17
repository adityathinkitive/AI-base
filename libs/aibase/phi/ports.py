from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Entity:
    label: str
    start: int
    end: int


class Redactor(Protocol):
    """Detects PHI spans. Adapters: regex (built in), presidio, or any cloud de-id service."""

    def detect(self, text: str) -> list[Entity]: ...
