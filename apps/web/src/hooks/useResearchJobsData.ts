import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api-client";
import { researchJobListSchema, researchJobSchema } from "../lib/dto";

export interface CreateResearchJobInput {
  experiment_id: string;
  purpose: string;
}

export function useResearchJobsData(enabled: boolean) {
  const client = useQueryClient();
  const jobs = useQuery({
    queryKey: ["research", "jobs"],
    enabled,
    refetchInterval: 10000,
    queryFn: () => api("/research/jobs", researchJobListSchema),
  });
  const create = useMutation({
    mutationFn: (input: CreateResearchJobInput) =>
      api("/research/jobs", researchJobSchema, input),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["research", "jobs"] }),
  });
  const cancel = useMutation({
    mutationFn: (jobId: string) =>
      api(`/research/jobs/${jobId}`, researchJobSchema, {}, "DELETE"),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["research", "jobs"] }),
  });
  return { jobs, create, cancel };
}
