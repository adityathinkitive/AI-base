import re
from collections.abc import Callable
from dataclasses import dataclass

from aibase.core.errors import GuardrailViolation
from aibase.phi.guard import PHIGuard


@dataclass(frozen=True)
class Verdict:
    passed: bool
    check: str
    reason: str = ""


Check = Callable[[str], Verdict]

# Heuristics are a cheap first layer only. Pair with a model-based classifier for high risk
# flows; guardrails are enforcement, system prompts are not.
_INJECTION = re.compile(
    r"ignore (all |any )?(previous|prior|above) (instructions|prompts)"
    r"|disregard (the )?(system|previous) (prompt|instructions)"
    r"|reveal (your )?(system )?prompt"
    r"|you are now (dan|in developer mode)",
    re.I,
)


def injection_check(text: str) -> Verdict:
    if _INJECTION.search(text):
        return Verdict(False, "prompt_injection", "possible prompt injection pattern")
    return Verdict(True, "prompt_injection")


def injection_free(text: str) -> bool:
    return injection_check(text).passed


def max_length_check(limit: int) -> Check:
    def check(text: str) -> Verdict:
        if len(text) > limit:
            return Verdict(False, "max_length", f"input exceeds {limit} characters")
        return Verdict(True, "max_length")

    return check


def no_phi_check(guard: PHIGuard) -> Check:
    def check(text: str) -> Verdict:
        if guard.contains_phi(text):
            return Verdict(False, "phi_in_output", "output contains PHI")
        return Verdict(True, "phi_in_output")

    return check


class GuardrailPipeline:
    def __init__(self, checks: list[Check]) -> None:
        self._checks = checks

    def evaluate(self, text: str) -> list[Verdict]:
        return [check(text) for check in self._checks]

    def enforce(self, text: str) -> None:
        failures = [v for v in self.evaluate(text) if not v.passed]
        if failures:
            raise GuardrailViolation(
                "request blocked by guardrails",
                details={"checks": [v.check for v in failures]},
            )


def default_input_pipeline(max_chars: int = 20_000) -> GuardrailPipeline:
    return GuardrailPipeline([max_length_check(max_chars), injection_check])


def default_output_pipeline(guard: PHIGuard) -> GuardrailPipeline:
    return GuardrailPipeline([no_phi_check(guard)])
