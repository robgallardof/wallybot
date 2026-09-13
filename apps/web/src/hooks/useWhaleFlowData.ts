import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { whaleFlowSchema } from "../lib/dto";

export function useWhaleFlowData(enabled = true) {
  return useQuery({
    queryKey: ["intelligence", "whale-flow"],
    queryFn: () => api("/intelligence/whale-flow", whaleFlowSchema),
    enabled,
    refetchInterval: 30000,
  });
}
