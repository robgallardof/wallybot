import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { providerReliabilitySchema } from "../lib/dto";

export function useProviderReliabilityData(enabled = true) {
  return useQuery({
    queryKey: ["intelligence", "provider-reliability"],
    queryFn: () => api("/intelligence/provider-reliability", providerReliabilitySchema),
    enabled,
    refetchInterval: 30000,
  });
}
