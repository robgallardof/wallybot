import { z } from "zod";

export const meSchema = z.object({
  username: z.string(),
  role: z.enum(["ADMIN", "VIEWER"]),
  csrf: z.string(),
});
export const dashboardSchema = z.object({
  environment: z.literal("PAPER"),
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
export const eventsSchema = z.array(
  z.object({
    id: z.string(),
    timestamp: z.number(),
    event: z.string(),
    message: z.string(),
  }),
);
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
