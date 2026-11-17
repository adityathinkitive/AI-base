import hashlib
from dataclasses import dataclass
from pathlib import Path

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from aibase.core.errors import NotFound


@dataclass(frozen=True)
class RenderedPrompt:
    name: str
    version: str
    content_hash: str
    text: str

    @property
    def tag(self) -> str:
        """Record this in traces/audit events so every output is traceable to a prompt."""
        return f"{self.name}@{self.version}#{self.content_hash[:8]}"


class PromptRegistry:
    """Prompts live in files: <root>/<name>/<version>.j2, e.g. summarize/v1.j2.
    Latest = highest lexical version. Changing a file's content changes its hash."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._env = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)

    def versions(self, name: str) -> list[str]:
        return sorted(p.stem for p in (self._root / name).glob("*.j2"))

    def render(
        self, name: str, version: str | None = None, /, **variables: object
    ) -> RenderedPrompt:
        versions = self.versions(name)
        if not versions:
            raise NotFound(f"prompt '{name}' not found")
        version = version or versions[-1]
        path = self._root / name / f"{version}.j2"
        if not path.exists():
            raise NotFound(f"prompt '{name}' version '{version}' not found")
        source = path.read_text()
        text = self._env.from_string(source).render(**variables)
        return RenderedPrompt(name, version, hashlib.sha256(source.encode()).hexdigest(), text)
