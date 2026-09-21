import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { telegramConfirmationListSchema, telegramConfirmationSchema } from "../lib/dto";

export function useTelegramConfirmationsData(enabled: boolean) {
  const client = useQueryClient();
  const confirmations = useQuery({
    queryKey: ["telegram", "confirmations"],
    enabled,
    refetchInterval: 10000,
    queryFn: () => api("/telegram/confirmations", telegramConfirmationListSchema),
  });
  const confirm = useMutation({
    mutationFn: (confirmationId: string) =>
      api(`/telegram/confirmations/${confirmationId}/confirm`, telegramConfirmationSchema, {}),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["telegram", "confirmations"] }),
  });
  return { confirmations, confirm };
}
