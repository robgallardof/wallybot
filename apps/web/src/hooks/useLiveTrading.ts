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
