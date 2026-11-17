import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from aibase.core.errors import PHIRedactionError
from aibase.phi.ports import Entity, Redactor

logger = logging.getLogger(__name__)


@dataclass
class RedactionResult:
    text: str
    # placeholder -> original value; keep in memory only, never persist or log.
    mapping: dict[str, str] = field(default_factory=dict, repr=False)

    def restore(self, text: str) -> str:
        for placeholder, original in self.mapping.items():
            text = text.replace(placeholder, original)
        return text


def _merge(entities: list[Entity]) -> list[Entity]:
    merged: list[Entity] = []
    for ent in sorted(entities, key=lambda e: (e.start, -e.end)):
        if merged and ent.start < merged[-1].end:
            continue  # overlapping span already covered
        merged.append(ent)
    return merged


class PHIGuard:
    def __init__(self, redactor: Redactor, *, fail_closed: bool = True) -> None:
        self._redactor = redactor
        self._fail_closed = fail_closed

    def redact(self, text: str) -> RedactionResult:
        try:
            entities = _merge(self._redactor.detect(text))
        except Exception as exc:
            if self._fail_closed:
                # Deliberately drop the original exception text: it may quote the input.
                raise PHIRedactionError("PHI redaction failed; request blocked") from None
            logger.error(
                "phi redaction failed; continuing fail-open", extra={"error": type(exc).__name__}
            )
            return RedactionResult(text)

        mapping: dict[str, str] = {}
        counters: dict[str, int] = {}
        pieces: list[str] = []
        cursor = 0
        for ent in entities:
            counters[ent.label] = counters.get(ent.label, 0) + 1
            placeholder = f"[{ent.label}_{counters[ent.label]}]"
            mapping[placeholder] = text[ent.start : ent.end]
            pieces += [text[cursor : ent.start], placeholder]
            cursor = ent.end
        pieces.append(text[cursor:])
        return RedactionResult("".join(pieces), mapping)

    def contains_phi(self, text: str) -> bool:
        return bool(self.redact(text).mapping)


def make_log_scrubber(guard: PHIGuard) -> Callable[[str], str]:
    def scrub(text: str) -> str:
        try:
            return guard.redact(text).text
        except PHIRedactionError:
            return "[REDACTION_FAILED]"

    return scrub
