import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { marketsSchema } from "../lib/dto";

export function useMarketsData() {
  return useQuery({
    queryKey: ["markets"],
    queryFn: () => api("/markets", marketsSchema),
    refetchInterval: 30000,
  });
}
