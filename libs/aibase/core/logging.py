import json
import logging
import sys
from collections.abc import Callable

from aibase.core.context import request_id_var, tenant_id_var

Scrubber = Callable[[str], str]

_RESERVED = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def __init__(self, scrub: Scrubber | None = None) -> None:
        super().__init__()
        self._scrub = scrub or (lambda s: s)

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": self._scrub(record.getMessage()),
            "request_id": request_id_var.get(),
            "tenant_id": tenant_id_var.get(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED:
                payload[key] = self._scrub(value) if isinstance(value, str) else value
        if record.exc_info:
            # Tracebacks can embed PHI via exception messages, so they are scrubbed too.
            payload["exc"] = self._scrub(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", scrub: Scrubber | None = None) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(scrub))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    for noisy in ("httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)  # URLs/payloads can carry PHI
