import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { telegramConfigSchema } from "../lib/dto";

export function useTelegramData(enabled: boolean) {
  const client = useQueryClient();
  const telegram = useQuery({
    queryKey: ["telegram"],
    enabled,
    queryFn: () => api("/telegram", telegramConfigSchema),
  });
  const save = useMutation({
    mutationFn: (body: {
      bot_token?: string;
      chat_id?: number | null;
      enabled: boolean;
      start_pairing?: boolean;
    }) =>
      api("/telegram", telegramConfigSchema, body),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["telegram"] }),
  });
  return { telegram, save };
}
