import json
import logging
from datetime import UTC, datetime

# Allowlisted integer counters only: they make silent no-op cycles visible without logging text.
_COUNT_FIELDS = ("instruments_evaluated", "proposals_received", "proposals_persisted")


class SafeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Only structured event codes are emitted; raw exceptions and bodies are excluded.
        counts = {
            name: value
            for name in _COUNT_FIELDS
            if type(value := getattr(record, name, None)) is int
        }
        return json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": record.levelname,
                "service": getattr(record, "service", "api"),
                "correlation_id": getattr(record, "correlation_id", None),
                "decision_id": None,
                "exchange": None,
                "symbol": None,
                "event": record.getMessage(),
                "message": record.getMessage(),
                **({"counts": counts} if counts else {}),
            }
        )


class ContextAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        kwargs["extra"] = {**(self.extra or {}), **kwargs.get("extra", {})}
        return msg, kwargs


def configure_logging(service: str) -> logging.LoggerAdapter:
    logger = logging.getLogger("wallybot")
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(SafeFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return ContextAdapter(logger, {"service": service})
