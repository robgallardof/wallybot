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
