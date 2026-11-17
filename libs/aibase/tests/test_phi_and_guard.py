import json
import logging

import pytest

from aibase.core.errors import PHIRedactionError
from aibase.core.logging import JsonFormatter
from aibase.phi import PHIGuard, make_log_scrubber
from aibase.phi.ports import Entity
from aibase.phi.regex_redactor import RegexRedactor
from aibase.providers.guarded import GuardedLLM
from aibase.providers.llm.fake import FakeLLM
from aibase.providers.llm.port import LLMMessage
from aibase.testing import SYNTHETIC_PHI, assert_no_phi

PHI_TEXT = " | ".join(SYNTHETIC_PHI.values())


class BrokenRedactor:
    def detect(self, text: str) -> list[Entity]:
        raise RuntimeError(f"boom {text}")


def test_regex_redacts_all_synthetic_phi():
    result = PHIGuard(RegexRedactor()).redact(PHI_TEXT)
    assert_no_phi(result.text)
    assert result.restore(result.text) == PHI_TEXT


def test_fail_closed_raises_without_leaking_input():
    with pytest.raises(PHIRedactionError) as info:
        PHIGuard(BrokenRedactor()).redact(PHI_TEXT)
    assert_no_phi(str(info.value))
    assert info.value.__cause__ is None


def test_fail_open_passes_text_through():
    assert PHIGuard(BrokenRedactor(), fail_closed=False).redact("hello").text == "hello"


async def test_guarded_llm_never_sends_phi_upstream():
    inner = FakeLLM()
    llm = GuardedLLM(inner, PHIGuard(RegexRedactor()))
    response = await llm.generate([LLMMessage(role="user", content=PHI_TEXT)])
    sent = " ".join(m.content for call in inner.calls for m in call)
    assert_no_phi(sent)
    assert_no_phi(response.text)


async def test_guarded_llm_blocks_when_redactor_fails():
    inner = FakeLLM()
    llm = GuardedLLM(inner, PHIGuard(BrokenRedactor()))
    with pytest.raises(PHIRedactionError):
        await llm.generate([LLMMessage(role="user", content=PHI_TEXT)])
    assert inner.calls == []


def test_logs_are_scrubbed_including_tracebacks():
    formatter = JsonFormatter(make_log_scrubber(PHIGuard(RegexRedactor())))
    try:
        raise ValueError(f"bad record {SYNTHETIC_PHI['ssn']}")
    except ValueError:
        record = logging.LogRecord(
            "t",
            logging.ERROR,
            __file__,
            1,
            "patient %s",
            (SYNTHETIC_PHI["email"],),
            logging.sys.exc_info(),
        )
    record.note = SYNTHETIC_PHI["phone"]
    output = formatter.format(record)
    assert_no_phi(output)
    assert json.loads(output)["level"] == "ERROR"
