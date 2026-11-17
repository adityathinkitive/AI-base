import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field

from aibase.core.errors import BadRequest
from aibase.phi import PHIGuard


@dataclass
class Document:
    text: str
    phi_entities: int = 0
    meta: dict[str, int] = field(default_factory=dict)


Step = Callable[[Document], Document]


def normalize_unicode(doc: Document) -> Document:
    return Document(unicodedata.normalize("NFKC", doc.text), doc.phi_entities, doc.meta)


def strip_control_chars(doc: Document) -> Document:
    cleaned = "".join(ch for ch in doc.text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    return Document(cleaned, doc.phi_entities, doc.meta)


def collapse_whitespace(doc: Document) -> Document:
    text = re.sub(r"[ \t]+", " ", doc.text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return Document(text, doc.phi_entities, doc.meta)


def make_deidentify(guard: PHIGuard) -> Step:
    def deidentify(doc: Document) -> Document:
        result = guard.redact(doc.text)
        return Document(result.text, doc.phi_entities + len(result.mapping), doc.meta)

    return deidentify


def build_steps(names: list[str], guard: PHIGuard) -> list[Step]:
    available: dict[str, Step] = {
        "normalize_unicode": normalize_unicode,
        "strip_control_chars": strip_control_chars,
        "collapse_whitespace": collapse_whitespace,
        "deidentify": make_deidentify(guard),
    }
    unknown = [n for n in names if n not in available]
    if unknown:
        raise BadRequest(f"unknown steps: {unknown}", details={"available": sorted(available)})
    return [available[n] for n in names]


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Fixed-size character windows that prefer to break on whitespace."""
    if overlap >= size:
        raise BadRequest("overlap must be smaller than chunk size")
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            space = text.rfind(" ", start + size // 2, end)
            end = space if space != -1 else end
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]
