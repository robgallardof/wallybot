import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { marketsSchema } from "../lib/dto";

export function useMarketsData(enabled = true) {
  return useQuery({
    queryKey: ["markets"],
    queryFn: () => api("/markets", marketsSchema),
    enabled,
    refetchInterval: 30000,
  });
}
