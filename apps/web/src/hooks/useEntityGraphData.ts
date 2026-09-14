import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { entityGraphSchema } from "../lib/dto";

export function useEntityGraphData(enabled = true) {
  return useQuery({
    queryKey: ["intelligence", "entity-graph"],
    queryFn: () => api("/intelligence/entity-graph", entityGraphSchema),
    enabled,
    refetchInterval: 30000,
  });
}
