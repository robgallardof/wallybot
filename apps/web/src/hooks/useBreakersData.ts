import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { breakerListSchema, breakerSchema } from "../lib/dto";

export function useBreakersData(enabled: boolean) {
  const client = useQueryClient();
  const breakers = useQuery({
    queryKey: ["breakers"],
    enabled,
    queryFn: () => api("/risk/breakers", breakerListSchema),
  });
  const clear = useMutation({
    mutationFn: (breakerType: string) =>
      api(`/risk/breakers/${breakerType}/clear`, breakerSchema, {}),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["breakers"] }),
  });
  return { breakers, clear };
}
