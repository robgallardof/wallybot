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
    // `environment` was previously never sent -- the backend requires `status` on every call
    // (it changes together, per wallybot.domain.control.Control.change) but treats a missing
    // `environment` as "leave unchanged", so this must always send the CURRENT environment
    // unless the caller explicitly wants to switch it.
    mutationFn: (body: { status: string; environment?: string }) =>
      api(
        "/control",
        z.object({ status: z.string(), environment: z.string() }),
        body,
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["dashboard"] });
      void client.invalidateQueries({ queryKey: ["events"] });
    },
  });
  // Refreshes the current session's MFA recency (apps/api/dependencies.py's admin() requires it
  // within the last 5 minutes for any Admin-gated action) without a new login -- see
  // wallybot.security.auth.AuthService.confirm_mfa. Does not retry whatever action originally
  // failed; the operator re-submits that themselves once this succeeds.
  const confirmMfa = useMutation({
    mutationFn: (body: { code: string }) =>
      api("/auth/confirm-mfa", z.object({ ok: z.boolean() }), body),
  });
  return { dashboard, system, events, change, confirmMfa };
}
