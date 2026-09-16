import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { providerConnectionListSchema, providerConnectionSchema } from "../lib/dto";

export function useConnectionsData(enabled: boolean) {
  const client = useQueryClient();
  const connections = useQuery({ queryKey: ["connections"], enabled, queryFn: () => api("/connections", providerConnectionListSchema) });
  const add = useMutation({
    mutationFn: (body: { provider: string; label: string; mode: string }) => api("/connections", providerConnectionSchema, body),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["connections"] }),
  });
  return { connections, add };
}
