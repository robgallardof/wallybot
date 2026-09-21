"""Pure dedup/rate-limit decision for outbound Telegram notifications (PENDING.md Fase 8:
"Integrar notificaciones por severidad, agrupación, deduplicación y límites para evitar spam.").

This is a decision only -- whether a (severity, title) pair has already fired recently, or
whether the rolling hourly cap is already spent -- with no I/O of its own, so it belongs in the
domain layer like `wallybot.domain.breaker`'s latch logic. `wallybot.application.
notification_dispatch` is the only caller: it consults `should_send` before actually calling the
Telegram transport, and calls `record` once it has (attempted to) send.

State is process-local memory, not persisted. That is a deliberate choice, not an oversight:
`dispatch_telegram_notification`'s own docstring already establishes Telegram as a convenience
channel that is "never a dependency of the action that triggered" it, and `apps/api` is the only
process that ever calls this -- a restart naturally resets the window, which is an acceptable
failure mode for a spam guard (worst case: one extra notification right after a restart).
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# 5 minutes: long enough to absorb a duplicate trigger from two near-simultaneous callers (e.g. a
# Telegram-confirmed pause landing moments after an operator also paused from the web), short
# enough that a genuinely new occurrence of the same severity+title (e.g. the bot pausing again
# after being resumed) is never silently swallowed for long.
DEFAULT_DEDUP_WINDOW = timedelta(minutes=5)

# 20/hour comfortably covers legitimate traffic today (pause/resume/confirmation notifications
# plus the daily/weekly report -- at most a handful of sends per hour in normal operation) while
# still bounding a runaway loop (e.g. a bug that fires a notification every tick) to a low,
# human-noticeable rate rather than unbounded spam.
DEFAULT_RATE_LIMIT = 20
DEFAULT_RATE_WINDOW = timedelta(hours=1)


@dataclass
class NotificationThrottle:
    """Tracks recent sends to decide whether a new notification should be suppressed.

    :ivar dedup_window: How long an identical (severity, title) pair is suppressed for.
    :ivar rate_limit: Max notifications allowed within `rate_window`.
    :ivar rate_window: Rolling window `rate_limit` is measured over.
    """

    dedup_window: timedelta = DEFAULT_DEDUP_WINDOW
    rate_limit: int = DEFAULT_RATE_LIMIT
    rate_window: timedelta = DEFAULT_RATE_WINDOW
    _last_sent: dict[tuple[str, str], datetime] = field(default_factory=dict, repr=False)
    _sent_at: deque[datetime] = field(default_factory=deque, repr=False)

    def should_send(self, severity: str, title: str, now: datetime) -> bool:
        """Decide whether a notification with this `severity`+`title` may be sent at `now`.

        Does not itself record anything -- callers must call `record` after acting on a ``True``
        result, so a suppressed call never displaces the timestamps this decision is based on.

        :param severity: The notification's severity, e.g. ``NotificationSeverity.value``.
        :param title: The notification's title; combined with `severity` as the dedup key.
        :param now: Current time; must be timezone-aware, like every other timestamp in this repo.
        :returns: ``False`` if the same (severity, title) fired within `dedup_window`, or if
            `rate_limit` sends already happened within `rate_window`; ``True`` otherwise.
        """
        last = self._last_sent.get((severity, title))
        if last is not None and now - last < self.dedup_window:
            return False
        self._evict_expired(now)
        return len(self._sent_at) < self.rate_limit

    def record(self, severity: str, title: str, now: datetime) -> None:
        """Record that a notification with this `severity`+`title` was (attempted to be) sent
        at `now`, so future `should_send` calls see it."""
        self._last_sent[(severity, title)] = now
        self._sent_at.append(now)

    def _evict_expired(self, now: datetime) -> None:
        while self._sent_at and now - self._sent_at[0] >= self.rate_window:
            self._sent_at.popleft()
