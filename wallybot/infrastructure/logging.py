import json
import logging
from datetime import UTC, datetime


class SafeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Only structured event codes are emitted; raw exceptions and bodies are excluded.
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
