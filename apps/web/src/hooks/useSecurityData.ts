import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "../lib/validation";
import { api } from "../lib/api-client";
import { enrollmentSchema, sessionListSchema } from "../lib/dto";

const okSchema = z.object({ ok: z.boolean() });

export function useSecurityData(enabled: boolean) {
  const client = useQueryClient();
  const sessions = useQuery({
    queryKey: ["sessions"],
    enabled,
    queryFn: () => api("/auth/sessions", sessionListSchema),
  });
  const changePassword = useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) =>
      api("/auth/password", okSchema, body),
  });
  const startTotpReplace = useMutation({
    mutationFn: () => api("/auth/totp/replace/start", enrollmentSchema, {}),
  });
  const finishTotpReplace = useMutation({
    mutationFn: (body: { challenge: string; code: string }) =>
      api("/auth/totp/replace/finish", okSchema, body),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["sessions"] }),
  });
  const revokeSession = useMutation({
    mutationFn: (sessionId: string) =>
      api(`/auth/sessions/${sessionId}`, okSchema, {}, "DELETE"),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["sessions"] }),
  });
  return { sessions, changePassword, startTotpReplace, finishTotpReplace, revokeSession };
}
