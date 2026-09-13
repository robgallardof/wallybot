from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from tests.contract.exchange_gateway_suite import (
    assert_accept_then_timeout_resolves_via_lookup,
    assert_cancel_loses_race_to_a_completed_fill,
    assert_cancel_wins_when_no_fill_posted,
    assert_submit_then_lookup_round_trips,
    intent_factory,
)
from wallybot.domain.execution import SubmissionOutcome
from wallybot.exchanges.fake import FakeExchange

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FixedClock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


def make_gateway(**scripts: Any) -> FakeExchange:
    return FakeExchange(
        clock=FixedClock(NOW),
        seed=1,
        balances={"USD": Decimal("1000000"), "BTC": Decimal("10")},
        **scripts,
    )


async def test_submit_then_lookup_round_trips() -> None:
    gateway = make_gateway()
    instrument = (await gateway.discover_instruments())[0]
    await assert_submit_then_lookup_round_trips(gateway, intent_factory(instrument, NOW))


async def test_accept_then_timeout_resolves_via_lookup() -> None:
    gateway = make_gateway(submission_script={"order-timeout": SubmissionOutcome.UNKNOWN})
    instrument = (await gateway.discover_instruments())[0]
    await assert_accept_then_timeout_resolves_via_lookup(gateway, intent_factory(instrument, NOW))


async def test_cancel_wins_when_no_fill_posted() -> None:
    gateway = make_gateway()
    instrument = (await gateway.discover_instruments())[0]
    await assert_cancel_wins_when_no_fill_posted(gateway, intent_factory(instrument, NOW))


async def test_cancel_loses_race_to_a_completed_fill() -> None:
    gateway = make_gateway()
    instrument = (await gateway.discover_instruments())[0]
    await assert_cancel_loses_race_to_a_completed_fill(gateway, intent_factory(instrument, NOW))
