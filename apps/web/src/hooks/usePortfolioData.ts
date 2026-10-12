import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { portfolioSchema } from "../lib/dto";
import { z } from "zod";

export function usePortfolioData(enabled: boolean) {
  const client = useQueryClient();
  const portfolio = useQuery({
    queryKey: ["portfolio"],
    enabled,
    refetchInterval: 30000,
    queryFn: () => api("/portfolio", portfolioSchema),
  });
  const fund = useMutation({
    mutationFn: (body: { amount: string }) => api("/portfolio/fund", portfolioSchema, body),
    onSuccess: (data) => client.setQueryData(["portfolio"], data),
  });
  const cancelOrder = useMutation({
    mutationFn: (clientOrderId: string) =>
      api(`/portfolio/orders/${encodeURIComponent(clientOrderId)}/cancel`, z.object({ client_order_id: z.string(), status: z.string() }), {}),
    onSuccess: () => client.invalidateQueries({ queryKey: ["portfolio"] }),
  });
  return { portfolio, fund, cancelOrder };
}
