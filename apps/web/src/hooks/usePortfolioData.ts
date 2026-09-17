import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { portfolioSchema } from "../lib/dto";

export function usePortfolioData(enabled: boolean) {
  return useQuery({
    queryKey: ["portfolio"],
    enabled,
    queryFn: () => api("/portfolio", portfolioSchema),
  });
}
