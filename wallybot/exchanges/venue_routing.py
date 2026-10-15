"""Public market data routed to each instrument's own venue.

Position marks must come from the exchange that holds the position: a Binance BTC/USDT fill is
never valued with a Kraken XBT/USD quote. Unknown venues fail instead of borrowing another price.
"""

from datetime import datetime

from wallybot.domain.market import Candle, Instrument, MarketDataProvider, MarketSnapshot


class VenueRoutedMarketData:
    def __init__(self, providers: dict[str, MarketDataProvider]) -> None:
        self.providers = providers

    def _provider(self, instrument: Instrument) -> MarketDataProvider:
        try:
            return self.providers[instrument.venue]
        except KeyError:
            raise LookupError(f"No market data for venue {instrument.venue!r}") from None

    async def discover_instruments(self) -> list[Instrument]:
        instruments: list[Instrument] = []
        for provider in self.providers.values():
            instruments.extend(await provider.discover_instruments())
        return instruments

    async def fetch_candles(
        self, instrument: Instrument, timeframe: str, since: datetime, limit: int
    ) -> list[Candle]:
        return await self._provider(instrument).fetch_candles(instrument, timeframe, since, limit)

    async def fetch_snapshot(self, instrument: Instrument) -> MarketSnapshot:
        return await self._provider(instrument).fetch_snapshot(instrument)
