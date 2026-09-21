import { z } from "zod";

export const meSchema = z.object({
  username: z.string(),
  role: z.enum(["ADMIN", "VIEWER"]),
  csrf: z.string(),
});
export const dashboardSchema = z.object({
  environment: z.enum(["OBSERVE", "PAPER"]),
  status: z.enum(["RUNNING", "PAUSED"]),
  trading_available: z.literal(false),
  equity: z.null(),
  exchange: z.string(),
  positions: z.array(z.unknown()),
  phase: z.number(),
});
export const systemSchema = z.object({
  api: z.string(),
  database: z.string(),
  redis: z.string(),
  services: z.record(
    z.object({ status: z.string(), age_seconds: z.number().nullable() }),
  ),
  exchange: z.string(),
  ai: z.string(),
  telegram: z.string(),
  live_available: z.literal(false),
});
export const eventSchema = z.object({
  id: z.string(),
  timestamp: z.number(),
  event: z.string(),
  message: z.string(),
});
export const eventsSchema = z.array(eventSchema);
export const eventPageSchema = z.object({
  rows: eventsSchema,
  next_before: z.string().nullable(),
});
export const marketRowSchema = z.object({
  id: z.string(),
  venue: z.string(),
  base: z.string(),
  quote: z.string(),
  bid: z.string(),
  ask: z.string(),
  spread_ratio: z.string(),
  quality_status: z.enum(["PASS", "WARNING", "FAILURE"]),
  quality_reasons: z.array(z.string()),
  eligible: z.boolean(),
  rejection_reasons: z.array(z.string()),
  score: z.string().nullable(),
  rank: z.number().nullable(),
});
export const marketsSchema = z.object({
  as_of: z.string(),
  rows: z.array(marketRowSchema),
});
export const smartMoneyRowSchema = z.object({
  wallet_id: z.string(),
  status: z.enum(["SCORED", "INSUFFICIENT_DATA"]),
  score: z.string().nullable(),
  trade_count: z.number(),
  win_rate: z.string().nullable(),
  realized_pnl_usd: z.string().nullable(),
  computed_at: z.string(),
  reasons: z.array(z.string()),
});
export const smartMoneySchema = z.object({
  rows: z.array(smartMoneyRowSchema),
});
export const whaleTransferRowSchema = z.object({
  wallet_id: z.string(),
  chain: z.string(),
  token: z.string(),
  action: z.string(),
  amount: z.string(),
  value_usd: z.string(),
  threshold_usd: z.string(),
  occurred_at: z.string(),
  reasons: z.array(z.string()),
});
export const whaleFlowSchema = z.object({
  rows: z.array(whaleTransferRowSchema),
});
export const walletActivityRowSchema = z.object({
  wallet_id: z.string(),
  chain: z.string(),
  token: z.string(),
  action: z.string(),
  amount: z.string(),
  value_usd: z.string().nullable(),
  price: z.string().nullable(),
  occurred_at: z.string(),
  attribution_source: z.string(),
  attribution_confidence: z.string(),
});
export const walletActivitySchema = z.object({
  rows: z.array(walletActivityRowSchema),
});
export const relationshipRowSchema = z.object({
  id: z.string(),
  source_type: z.string(),
  source_id: z.string(),
  relationship_type: z.string(),
  target_type: z.string(),
  target_id: z.string(),
  attribution_source: z.string(),
  attribution_confidence: z.string(),
  created_at: z.string(),
});
export const entityGraphSchema = z.object({
  rows: z.array(relationshipRowSchema),
});
export const tokenRiskRowSchema = z.object({
  token_id: z.string(),
  chain: z.string(),
  status: z.enum(["SCORED", "INSUFFICIENT_DATA"]),
  risk_score: z.string().nullable(),
  computed_at: z.string(),
  reasons: z.array(z.string()),
});
export const tokenRiskSchema = z.object({
  rows: z.array(tokenRiskRowSchema),
});
export const providerReliabilityRowSchema = z.object({
  provider: z.string(),
  status: z.enum(["HEALTHY", "DEGRADED", "UNRELIABLE", "INSUFFICIENT_DATA"]),
  call_count: z.number(),
  error_rate: z.string().nullable(),
  average_latency_ms: z.string().nullable(),
  seconds_since_last_success: z.string().nullable(),
  computed_at: z.string(),
  reasons: z.array(z.string()),
});
export const providerReliabilitySchema = z.object({
  rows: z.array(providerReliabilityRowSchema),
});
export const priceConsensusRowSchema = z.object({
  instrument_id: z.string(),
  status: z.enum(["CONSENSUS", "INSUFFICIENT_DATA"]),
  consensus_price: z.string().nullable(),
  included_sources: z.array(z.string()),
  excluded_sources: z.array(z.string()),
  computed_at: z.string(),
  reasons: z.array(z.string()),
});
export const priceConsensusSchema = z.object({
  rows: z.array(priceConsensusRowSchema),
});
export const backtestBootstrapSchema = z.object({
  sample_count: z.number(),
  trades_per_sample: z.number(),
  mean_total_pnl: z.string(),
  median_total_pnl: z.string(),
  p05_total_pnl: z.string(),
  p95_total_pnl: z.string(),
  probability_of_loss: z.string(),
});
export const backtestWalkForwardWindowSchema = z.object({
  index: z.number(),
  trade_count: z.number(),
  final_equity: z.string(),
  total_return_pct: z.string(),
  max_drawdown_pct: z.string(),
  win_rate: z.string().nullable(),
});
export const backtestRunSchema = z.object({
  experiment_id: z.string(),
  instrument_venue: z.string(),
  instrument_base: z.string(),
  instrument_quote: z.string(),
  timeframe: z.string(),
  trade_count: z.number(),
  starting_equity: z.string(),
  final_equity: z.string(),
  total_return_pct: z.string(),
  max_drawdown_pct: z.string(),
  win_rate: z.string().nullable(),
  created_at: z.string(),
  bootstrap: backtestBootstrapSchema.nullable(),
  walk_forward: z.array(backtestWalkForwardWindowSchema).nullable(),
});
export const backtestHistoryRowSchema = z.object({
  experiment_id: z.string(),
  strategy_id: z.string(),
  instrument_venue: z.string(),
  instrument_base: z.string(),
  instrument_quote: z.string(),
  timeframe: z.string(),
  window_start: z.string(),
  window_end: z.string(),
  trade_count: z.number(),
  starting_equity: z.string(),
  final_equity: z.string(),
  total_return_pct: z.string(),
  max_drawdown_pct: z.string(),
  win_rate: z.string().nullable(),
  created_at: z.string(),
});
export const backtestHistorySchema = z.object({
  rows: z.array(backtestHistoryRowSchema),
});

export const researchJobSchema = z.object({
  id: z.string(),
  experiment_id: z.string(),
  purpose: z.string(),
  status: z.enum(["PENDING", "RUNNING", "CANCELLED", "COMPLETED", "FAILED"]),
  attempts: z.number(),
  cancel_requested: z.boolean(),
  artifact_uri: z.string().nullable(),
  error: z.string().nullable(),
  created_at: z.number(),
  claimed_at: z.number().nullable(),
  completed_at: z.number().nullable(),
});
export const researchJobListSchema = z.object({
  rows: z.array(researchJobSchema),
});

export const providerConnectionSchema = z.object({
  id: z.string(), provider: z.string(), label: z.string(), mode: z.string(),
  status: z.string(), has_credentials: z.boolean(), created_at: z.number(),
});
export const providerConnectionListSchema = z.object({ rows: z.array(providerConnectionSchema) });

export const portfolioBalanceSchema = z.object({
  currency: z.string(),
  purpose: z.enum(["CASH", "POSITION"]),
  amount: z.string(),
});
export const portfolioActivitySchema = z.object({
  id: z.string(),
  venue: z.string(),
  base: z.string(),
  quote: z.string(),
  side: z.enum(["BUY", "SELL"]),
  quantity: z.string(),
  price: z.string(),
  fee: z.string(),
  fee_currency: z.string(),
  occurred_at: z.string(),
});
export const portfolioPerformanceSchema = z.object({
  quote: z.string(),
  realized_pnl: z.string(),
  open_cost_basis: z.string(),
});
export const portfolioSchema = z.object({
  environment: z.literal("PAPER"),
  connection_count: z.number(),
  balances: z.array(portfolioBalanceSchema),
  activity: z.array(portfolioActivitySchema),
  performance: z.array(portfolioPerformanceSchema),
});

export const telegramConfigSchema = z.object({
  has_bot_token: z.boolean(),
  chat_id: z.number().nullable(),
  enabled: z.boolean(),
  pairing_status: z.enum(["NEEDS_TOKEN", "WAITING_FOR_START", "LINKED"]),
  pairing_code: z.string().nullable(),
});

export const telegramConfirmationSchema = z.object({
  confirmation_id: z.string(),
  action: z.enum(["PAUSE", "RESUME"]),
  requested_at: z.string(),
  expires_at: z.string(),
  confirmed_at: z.string().nullable(),
  confirmed_by: z.string().nullable(),
});
export const telegramConfirmationListSchema = z.object({
  rows: z.array(telegramConfirmationSchema),
});

export const breakerSchema = z.object({
  breaker_type: z.enum(["DAILY_LOSS", "WEEKLY_LOSS", "DRAWDOWN", "RECONCILIATION"]),
  reason: z.string(),
  tripped_at: z.string(),
  cleared_at: z.string().nullable(),
  cleared_by: z.string().nullable(),
});
export const breakerListSchema = z.object({ rows: z.array(breakerSchema) });
