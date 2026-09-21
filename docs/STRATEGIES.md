# Strategies and regime classification

Status: exactly one strategy is implemented — `wallybot/strategies/trend_following.py`'s
`TrendFollowingStrategy`. Regime classification (`wallybot/domain/regime.py`) is momentum-only.
Every other strategy family the original specification named (breakout, pullback, reversal,
rotation, volume/volatility variants) does not exist in this codebase.

## The `Strategy` contract

`wallybot/domain/strategy.py` defines the port every strategy implements:

```python
class Strategy(Protocol):
    def evaluate(self, context: StrategyContext) -> StrategySignal: ...
```

`StrategyContext` carries `instrument`, `features` (a `FeatureVector`), `regime`
(`RegimeClassification`) and `as_of`. `StrategySignal` carries `action` (`BUY`/`SELL`/`HOLD`),
`confidence` (bounded `[0, 1]`), `strategy_id`, `version` and `reason`. Per the module's own
docstring and ARCHITECTURE.md's Contracts table: "A `Strategy` never touches I/O, never holds
credentials ... there is nothing here for a strategy to misuse even if it wanted to" — this is a
pure, synchronous recommendation function with no execution capability of any kind.

## `TrendFollowingStrategy`: the only real strategy

`wallybot/strategies/trend_following.py` maps regime directly to action:

| Regime | Action |
| --- | --- |
| `TRENDING_UP` | BUY |
| `TRENDING_DOWN` | SELL |
| `RANGING` | HOLD |
| `RISK_OFF` | HOLD |

Confidence is `min(abs(momentum), 1)` from the feature vector's `momentum_<window>` value. There is
no parameter fitting, no multi-timeframe confirmation, and no volume/volatility input — the entire
decision is one momentum number and the regime it was already used to classify. It carries
`STRATEGY_ID = "trend_following"`, `STRATEGY_VERSION = 1`, and is explicitly DRAFT status per
RISK.md's promotion ladder (DRAFT → BACKTESTED → VALIDATED → PAPER → CANDIDATE → LIVE → RETIRED) —
nothing in this codebase promotes it further than DRAFT. It is the strategy `DecisionPipeline` runs
in the live PAPER loop (see [TRADING.md](TRADING.md)) and the strategy `BacktestEngine`/
`BacktestOrchestrator` run in every backtest (see [BACKTESTING.md](BACKTESTING.md)) — there is only
one strategy, so both paths use it by construction, not by configuration choice.

## Regime classification: momentum only

`wallybot/domain/regime.py`'s `classify_regime` is deliberately short — the whole function is
about 25 lines. It reads a single `momentum_<window>` feature value and buckets it into one of four
regimes:

- `momentum <= -risk_off_threshold` → `RISK_OFF`
- `momentum > 0` → `TRENDING_UP`
- `momentum < 0` (but above the risk-off threshold) → `TRENDING_DOWN`
- `momentum == 0` → `RANGING`

The module's own docstring is explicit about scope: "Only the classification rule lives here;
nothing yet consumes a regime to actually change a risk ceiling — that arrives with RiskEngine, a
deliberately separate, later piece of work." `docs/PENDING.md`'s Fase 3 says the same thing from
the product side: "el clasificador inicial de momentum no cubre toda la taxonomía original" — this
document states it again plainly rather than letting the gap go unmentioned. Other module
docstrings in this codebase (`wallybot/domain/regime.py` itself, `wallybot/application/
decision_loop.py`) already admit this; there is no volatility, breadth, or "abnormal condition"
signal feeding regime classification today, only momentum.

## What is not built

- **Breakout, pullback, reversal, rotation strategies.** None of these exist. `docs/PENDING.md`
  Fase 3 lists them as unchecked: "Incorporar las demás estrategias solicitadas cuando exista
  hipótesis y datos: breakout, pullback, reversión, rotación y variantes de volumen/volatilidad."
- **A strategy registry.** `wallybot/application/backtest_orchestrator.py`'s own docstring notes
  only `TrendFollowingStrategy`/`SimpleFeatureEngine` are wired because "this codebase has exactly
  one strategy and one feature engine so far" — a registry over more than one strategy is
  `docs/PHASE_5.md`'s remaining "strategy registry lifecycle" item, not built.
  `DeterministicRiskEngine`, `SimplePortfolioAllocator` and `WeightedSignalAggregator` all take a
  single injected strategy today; nothing selects among several at runtime.
  - `wallybot/signals/weighted_aggregator.py`'s `WeightedSignalAggregator` is real and does support
    multiple weighted strategies in principle, but the live loop (`decision_loop.py`) configures it
    with `weights={"trend_following": Decimal("1")}` and a single injected strategy — there is only
    ever one signal to aggregate in production today.
- **A richer regime taxonomy.** Volatility-based, breadth-based or "abnormal condition" regimes are
  not classified; `RISK.md`'s "Neutral and risk-off regimes may reduce ceilings" has nothing beyond
  momentum-derived `RISK_OFF` to act on.
- **The equities/VIX DCA idea.** `docs/PENDING.md` Fase 3 records a user-proposed strategy
  (regime-conditioned DCA on SMH/NVDA using VIX/Fear & Greed, plus a crypto branch) as an explicit
  unchecked item, not implemented. It is blocked on two real prerequisites that do not exist in
  this codebase: an equities market/venue (`wallybot.domain.market.MarketType` only has `SPOT`
  crypto via Kraken today) and a VIX/Fear & Greed data source. It would be modeled as a new
  `Strategy` implementation, not a change to the risk engine or breakers, per the same
  `docs/PENDING.md` entry.

See [ARCHITECTURE.md](../ARCHITECTURE.md)'s Contracts table for the target `Strategy`/
`SignalAggregator` shape, and [RISK.md](../RISK.md) for the promotion ladder a strategy must climb
before any capital increase beyond PAPER.
