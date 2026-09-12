# ADR-004: Constrained exchange adapters

Status: accepted boundary; streaming implementation pending Phase 2 benchmark, 2026-09-09.

Context: venue APIs differ in precision, order IDs, types and reconnect behavior.

Decision: use CCXT behind a narrow ExchangeGateway for REST/execution, starting with Fake then Kraken. Expose no withdrawal function. Evaluate native Kraken WebSocket versus CCXT Pro using sequence-gap/reconnect/freshness tests and maintenance/licensing evidence.

Alternatives: direct CCXT calls in strategies couple research to network behavior; a native-only implementation duplicates broad REST support.

Consequences: venue capabilities are explicit and contract-tested. A venue cannot qualify for LIVE without reliable ambiguous-order resolution. Binance/Coinbase follow later.
