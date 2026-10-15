"""Shared base for sanitized private-exchange failures.

Venue adapters raise subclasses whose messages are safe to show the operator: they never contain
keys, secrets, signatures or raw provider payloads.
"""


class ExchangePrivateError(Exception):
    """Sanitized, operator-actionable failure from an authenticated exchange call."""
