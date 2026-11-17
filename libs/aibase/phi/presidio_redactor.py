from typing import Any

from aibase.core.errors import ConfigError
from aibase.phi.ports import Entity


class PresidioRedactor:
    """Requires `uv sync --extra presidio` and a spaCy model (e.g. en_core_web_lg)."""

    def __init__(self, language: str = "en", score_threshold: float = 0.4) -> None:
        try:
            from presidio_analyzer import AnalyzerEngine
        except ImportError as exc:
            raise ConfigError("presidio not installed; run `uv sync --extra presidio`") from exc
        self._analyzer: Any = AnalyzerEngine()
        self._language = language
        self._threshold = score_threshold

    def detect(self, text: str) -> list[Entity]:
        results = self._analyzer.analyze(
            text=text, language=self._language, score_threshold=self._threshold
        )
        return [Entity(r.entity_type, r.start, r.end) for r in results]
