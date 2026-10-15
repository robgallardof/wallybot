import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { aiAutonomyControlSchema } from "../lib/dto";

export function useAiAutonomyData(enabled: boolean) {
  const client = useQueryClient();
  const control = useQuery({
    queryKey: ["ai-autonomy-control"],
    enabled,
    queryFn: () => api("/ai-autonomy/control", aiAutonomyControlSchema),
    refetchInterval: 30_000,
  });
  const change = useMutation({
    mutationFn: (body: {
      status: "DISABLED" | "ENABLED";
      target_core_pct?: string;
      target_growth_pct?: string;
      target_speculative_pct?: string;
      digest_interval_hours?: number;
      codex_enabled?: boolean;
      claude_enabled?: boolean;
      require_consensus?: boolean;
    }) => api("/ai-autonomy/control", aiAutonomyControlSchema, body),
    onSuccess: (data) => client.setQueryData(["ai-autonomy-control"], data),
  });
  const checkAnalysts = useMutation({
    mutationFn: () => api("/ai-autonomy/check-analysts", aiAutonomyControlSchema, {}),
    onSuccess: (data) => client.setQueryData(["ai-autonomy-control"], data),
  });
  const startAnalyst = useMutation({
    mutationFn: (analyst: "codex" | "claude") =>
      api(`/ai-autonomy/analysts/${analyst}/start`, aiAutonomyControlSchema, {}),
    onSuccess: (data) => client.setQueryData(["ai-autonomy-control"], data),
  });
  return { control, change, checkAnalysts, startAnalyst };
}
