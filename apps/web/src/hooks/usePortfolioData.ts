import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { portfolioSchema } from "../lib/dto";

export function usePortfolioData(enabled: boolean) {
  const client = useQueryClient();
  const portfolio = useQuery({
    queryKey: ["portfolio"],
    enabled,
    queryFn: () => api("/portfolio", portfolioSchema),
  });
  const fund = useMutation({
    mutationFn: (body: { amount: string }) => api("/portfolio/fund", portfolioSchema, body),
    onSuccess: (data) => client.setQueryData(["portfolio"], data),
  });
  return { portfolio, fund };
}
