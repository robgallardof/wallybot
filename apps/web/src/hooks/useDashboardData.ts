import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "../lib/api-client";
import { dashboardSchema, eventsSchema, systemSchema } from "../lib/dto";

export function useDashboardData() {
  const client = useQueryClient();
  const dashboard = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api("/dashboard", dashboardSchema),
    refetchInterval: 10000,
  });
  const system = useQuery({
    queryKey: ["system"],
    queryFn: () => api("/system", systemSchema),
    refetchInterval: 10000,
  });
  const events = useQuery({
    queryKey: ["events"],
    queryFn: () => api("/events", eventsSchema),
    refetchInterval: 10000,
  });
  const change = useMutation({
    mutationFn: (status: string) =>
      api(
        "/control",
        z.object({ status: z.string(), environment: z.string() }),
        { status },
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["dashboard"] });
      void client.invalidateQueries({ queryKey: ["events"] });
    },
  });
  return { dashboard, system, events, change };
}
