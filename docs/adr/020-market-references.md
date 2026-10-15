# ADR-020: Informational gross market references

Status: accepted, 2026-10-14. Extends ADR-019 reporting; no execution or mandate changes.

Daily/weekly Telegram reports can show BTC, ETH, nominal cash (zero interest) and a hypothetical
50/50 BTC/ETH buy-and-hold reference, all in the same venue and quote currency. Binance uses
USDT; legacy Kraken uses USD/XBT. These are gross price changes, excluding fees, slippage,
interest and FX. They are not the account's net investment return or an outperformance ranking.
The 50/50 reference never changes the operator's configurable allocation mandate.

Use exact closed hourly boundary prices. The reference end is the last closed UTC hour, and
start is the report period start. At UTC rollover, before a current-period hour has closed, use
the previous complete day/week and display its own dates. The reference window is printed
separately from account valuation dates. No interpolation, forward filling or USD/USDT merge.
Each reference is `(end / start - 1) * 100` in Decimal. The 50/50 result is the equally weighted
mean of both asset returns, with no rebalancing; cash is nominally zero in the same quote unit.

The public-data port is injected at the API composition root. Two bounded calls per reference
window, five-second timeout each, at most eight days/194 requested hourly rows. No private API,
credentials, order gateway or research execution capability is introduced. Missing endpoints,
duplicates, wrong venue/quote/source, excessive future receipt time and arithmetic overflow
withhold the asset's value. An unavailable component also withholds the passive mix. Other
valid references remain visible; a failed feed never becomes a zero asset return.

Account performance adjusted for external flows and exact account/reference alignment remains a
separate capability. No report claims that reference returns prove strategy profitability.
