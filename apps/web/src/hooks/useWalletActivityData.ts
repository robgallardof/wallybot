import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { walletActivitySchema } from "../lib/dto";

export function useWalletActivityData(enabled = true) {
  return useQuery({
    queryKey: ["intelligence", "wallet-activity"],
    queryFn: () => api("/intelligence/wallet-activity", walletActivitySchema),
    enabled,
    refetchInterval: 30000,
  });
}
