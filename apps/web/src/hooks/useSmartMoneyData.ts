import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { smartMoneySchema } from "../lib/dto";

export function useSmartMoneyData(enabled = true) {
  return useQuery({
    queryKey: ["intelligence", "smart-money"],
    queryFn: () => api("/intelligence/smart-money", smartMoneySchema),
    enabled,
    refetchInterval: 30000,
  });
}
