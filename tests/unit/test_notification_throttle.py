from datetime import UTC, datetime, timedelta

from wallybot.domain.notification_throttle import NotificationThrottle

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_a_fresh_severity_title_pair_may_be_sent() -> None:
    throttle = NotificationThrottle()

    assert throttle.should_send("WARNING", "Bot paused", NOW) is True


def test_an_identical_pair_is_suppressed_within_the_dedup_window() -> None:
    throttle = NotificationThrottle(dedup_window=timedelta(minutes=5))
    throttle.record("WARNING", "Bot paused", NOW)

    assert throttle.should_send("WARNING", "Bot paused", NOW + timedelta(minutes=4)) is False


def test_an_identical_pair_may_be_sent_again_once_the_dedup_window_elapses() -> None:
    throttle = NotificationThrottle(dedup_window=timedelta(minutes=5))
    throttle.record("WARNING", "Bot paused", NOW)

    assert throttle.should_send("WARNING", "Bot paused", NOW + timedelta(minutes=5)) is True


def test_a_different_severity_or_title_is_not_deduplicated() -> None:
    throttle = NotificationThrottle(dedup_window=timedelta(minutes=5))
    throttle.record("WARNING", "Bot paused", NOW)

    assert throttle.should_send("INFO", "Bot paused", NOW) is True
    assert throttle.should_send("WARNING", "Bot resumed", NOW) is True


def test_the_rate_limit_caps_sends_within_the_rolling_window() -> None:
    throttle = NotificationThrottle(rate_limit=2, rate_window=timedelta(hours=1))
    throttle.record("INFO", "one", NOW)
    throttle.record("INFO", "two", NOW + timedelta(minutes=1))

    assert throttle.should_send("INFO", "three", NOW + timedelta(minutes=2)) is False


def test_the_rate_limit_window_rolls_forward() -> None:
    throttle = NotificationThrottle(rate_limit=1, rate_window=timedelta(hours=1))
    throttle.record("INFO", "one", NOW)

    assert throttle.should_send("INFO", "two", NOW + timedelta(hours=1, minutes=1)) is True


def test_should_send_does_not_itself_record() -> None:
    throttle = NotificationThrottle(rate_limit=1, rate_window=timedelta(hours=1))

    assert throttle.should_send("INFO", "one", NOW) is True
    assert throttle.should_send("INFO", "one", NOW) is True  # never recorded, so still allowed
