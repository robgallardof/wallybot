import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "../lib/api-client";
import { tradeProposalListSchema } from "../lib/dto";

export function useProposalsData(enabled = true) {
  const client = useQueryClient();
  const proposals = useQuery({
    queryKey: ["proposals"],
    enabled,
    queryFn: () => api("/proposals", tradeProposalListSchema),
  });
  const decide = useMutation({
    mutationFn: ({
      proposalId,
      decision,
      environment,
      liveVersion,
    }: {
      proposalId: string;
      decision: "simulate" | "approve" | "reject";
      environment?: string;
      liveVersion?: number;
    }) =>
      api(
        `/proposals/${encodeURIComponent(proposalId)}/${decision}`,
        z.object({
          proposal_id: z.string(),
          status: z.string(),
          execution_status: z.string().nullable(),
        }),
        { environment, live_version: liveVersion },
      ),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["proposals"] });
      client.invalidateQueries({ queryKey: ["ai-portfolio"] });
      client.invalidateQueries({ queryKey: ["live-trading"] });
    },
  });
  return { proposals, decide };
}
