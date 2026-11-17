import re

from aibase.phi.ports import Entity

# Regex catches structured identifiers only. Free-text names need an NER adapter (e.g. presidio).
PATTERNS: dict[str, re.Pattern[str]] = {
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "EMAIL": re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),
    "PHONE": re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"),
    "MRN": re.compile(r"\b(?:MRN|Medical Record(?: Number)?)\s*[:#]?\s*[A-Z0-9-]{5,}\b", re.I),
    "DATE": re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),
    "IP": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "NAME": re.compile(r"\b(?:Dr|Mr|Mrs|Ms|Miss|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b"),
}


class RegexRedactor:
    def __init__(self, extra_patterns: dict[str, re.Pattern[str]] | None = None) -> None:
        self._patterns = {**PATTERNS, **(extra_patterns or {})}

    def detect(self, text: str) -> list[Entity]:
        return [
            Entity(label, match.start(), match.end())
            for label, pattern in self._patterns.items()
            for match in pattern.finditer(text)
        ]
