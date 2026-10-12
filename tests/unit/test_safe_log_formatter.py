"""Structured logs expose allowlisted counters, never arbitrary extra values."""

import json
import logging

from wallybot.infrastructure.logging import SafeFormatter


def _record(**extra) -> logging.LogRecord:
    record = logging.LogRecord("wallybot", logging.INFO, __file__, 1, "EVENT", None, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_allowlisted_integer_counters_are_emitted() -> None:
    payload = json.loads(SafeFormatter().format(_record(instruments_evaluated=0)))
    assert payload["counts"] == {"instruments_evaluated": 0}


def test_unknown_or_non_integer_extras_are_dropped() -> None:
    payload = json.loads(
        SafeFormatter().format(_record(api_secret="s3cr3t", proposals_received="2"))
    )
    assert "counts" not in payload
    assert "s3cr3t" not in json.dumps(payload)
