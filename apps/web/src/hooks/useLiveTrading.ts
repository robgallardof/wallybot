import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "../lib/api-client";

const liveSchema = z.object({
  capable: z.boolean().default(false),
  configured: z.boolean(),
  enabled: z.boolean(),
  state: z.string(),
  reason: z.string(),
  version: z.number().nullable(),
  connection_id: z.string().nullable(),
  venue: z.string().nullable().default(null),
  cash_currency: z.string().nullable().default(null),
  max_order_usd: z.string().nullable(),
  max_daily_loss_usd: z.string().nullable(),
  max_total_usd: z.string().nullable(),
  slippage_pct: z.string().nullable(),
  equity_usd: z.string().nullable(),
  as_of: z.string().nullable(),
  balances: z.array(z.object({ asset: z.string(), amount: z.string() })),
  orders: z.array(
    z.object({
      id: z.string(),
      pair: z.string(),
      side: z.string(),
      quantity: z.string(),
      filled_quantity: z.string().default("0"),
      limit_price: z.string(),
      status: z.string(),
      created_at: z.string(),
    }),
  ),
});

/** Display name and cash currency of the configured real-account exchange. */
export function liveVenueLabel(venue: string | null | undefined) {
  return venue === "kraken" ? "Kraken" : "Binance";
}

export function useLiveTrading(enabled = true) {
  const client = useQueryClient();
  const live = useQuery({
    queryKey: ["live-trading"],
    enabled,
    queryFn: () => api("/live", liveSchema),
    refetchInterval: 30000,
  });
  const configure = useMutation({
    mutationFn: (body: {
      connection_id: string;
      enabled: boolean;
      confirmation?: "LIVE";
      max_order_usd: string;
      max_daily_loss_usd: string;
      max_total_usd: string;
      slippage_pct: string;
    }) => api("/live/control", liveSchema, body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["live-trading"] });
      client.invalidateQueries({ queryKey: ["dashboard"] });
      client.invalidateQueries({ queryKey: ["system"] });
    },
  });
  return { live, configure };
}

const livePositionsSchema = z.object({
  cash_currency: z.string().nullable(),
  as_of: z.string().nullable(),
  positions: z.array(
    z.object({
      asset: z.string(),
      quantity: z.string(),
      price: z.string().nullable(),
      value: z.string().nullable(),
      average_price: z.string().nullable(),
      held_since: z.string().nullable(),
      pnl: z.string().nullable(),
      pnl_pct: z.string().nullable(),
      source: z.string().nullable(),
    }),
  ),
});

const priceHistorySchema = z.object({
  asset: z.string(),
  timeframe: z.string(),
  average_price: z.string().nullable(),
  held_since: z.string().nullable(),
  points: z.array(z.object({ t: z.string(), close: z.string() })),
});

export type LivePosition = z.infer<typeof livePositionsSchema>["positions"][number];
export type PriceHistory = z.infer<typeof priceHistorySchema>;

/** Per-coin entry, value and result of the real account (refreshed with each verified sync). */
export function useLivePositions(enabled = true) {
  return useQuery({
    queryKey: ["live-positions"],
    enabled,
    queryFn: () => api("/live/positions", livePositionsSchema),
    refetchInterval: 30000,
  });
}

/** Closing prices of one held coin since it was bought. */
export function useLivePriceHistory(asset: string) {
  return useQuery({
    queryKey: ["live-price-history", asset],
    queryFn: () => api(`/live/positions/${encodeURIComponent(asset)}/history`, priceHistorySchema),
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000,
  });
}
