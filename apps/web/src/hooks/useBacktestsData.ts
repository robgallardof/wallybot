import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { backtestHistorySchema, backtestRunSchema } from "../lib/dto";

export interface RunBacktestInput {
  instrument_base: string;
  instrument_quote: string;
  timeframe: string;
  window_start: string;
  window_end: string;
  feature_window: number;
  risk_off_threshold: string;
  starting_equity: string;
  allocation_pct: string;
  fee_rate: string;
  slippage_pct: string;
  bootstrap_seed: number | null;
}

export function useBacktestsData(enabled = true) {
  const client = useQueryClient();
  const history = useQuery({
    queryKey: ["backtests", "history"],
    queryFn: () => api("/backtests", backtestHistorySchema),
    enabled,
  });
  const run = useMutation({
    mutationFn: (input: RunBacktestInput) =>
      api("/backtests", backtestRunSchema, input),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["backtests", "history"] });
    },
  });
  return { history, run };
}
