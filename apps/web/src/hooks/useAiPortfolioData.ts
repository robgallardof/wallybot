import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { portfolioSchema } from "../lib/dto";

/** Same shape as usePortfolioData, against the fully separate AI-autonomous account
 * (/api/portfolio/ai) -- see .ai/DECISIONS.md (2026-09-23). */
export function useAiPortfolioData(enabled: boolean) {
  const client = useQueryClient();
  const portfolio = useQuery({
    queryKey: ["ai-portfolio"],
    enabled,
    refetchInterval: 30000,
    queryFn: () => api("/portfolio/ai", portfolioSchema),
  });
  const fund = useMutation({
    mutationFn: (body: { amount: string }) => api("/portfolio/ai/fund", portfolioSchema, body),
    onSuccess: (data) => client.setQueryData(["ai-portfolio"], data),
  });
  return { portfolio, fund };
}
