import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { tokenRiskSchema } from "../lib/dto";

export function useTokenRiskData(enabled = true) {
  return useQuery({
    queryKey: ["intelligence", "token-risk"],
    queryFn: () => api("/intelligence/token-risk", tokenRiskSchema),
    enabled,
    refetchInterval: 30000,
  });
}
