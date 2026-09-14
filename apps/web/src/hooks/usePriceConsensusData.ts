import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { priceConsensusSchema } from "../lib/dto";

export function usePriceConsensusData(enabled = true) {
  return useQuery({
    queryKey: ["intelligence", "price-consensus"],
    queryFn: () => api("/intelligence/price-consensus", priceConsensusSchema),
    enabled,
    refetchInterval: 30000,
  });
}
