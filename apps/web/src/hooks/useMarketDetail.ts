import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { marketDetailSchema } from "../lib/dto";

export function useMarketDetail(instrumentId: string | null) {
  return useQuery({
    queryKey: ["market-detail", instrumentId],
    queryFn: () => api(`/markets/${encodeURIComponent(instrumentId ?? "")}`, marketDetailSchema),
    enabled: instrumentId !== null,
    staleTime: 30_000,
  });
}
