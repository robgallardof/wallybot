import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { z } from "../lib/validation";
import { api } from "../lib/api-client";
import { dashboardSchema, eventPageSchema, systemSchema } from "../lib/dto";

// Latest events fetched per request. The API allows up to 200 (see apps/api/system_routes.py);
// this keeps the "overview" snapshot and each page of the /events feed reasonably sized.
const EVENTS_PAGE_SIZE = 100;

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
  // The "recent activity" snapshot used by the overview widget and the global error banner --
  // a single page, not the full history. The dedicated /events page uses useEventsFeed below to
  // reach older events too.
  const events = useQuery({
    queryKey: ["events"],
    queryFn: () =>
      api(`/events?limit=${EVENTS_PAGE_SIZE}`, eventPageSchema).then(
        (page) => page.rows,
      ),
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

// Cursor-paginated event history for the /events page (apps/api/system_routes.py's GET /api/events
// -- `before`/`limit`, ordered newest first). Separate from `events` above because the full
// history can grow far past one page; "load more" calls fetchNextPage to walk it backwards in
// time. Each page's rows are flattened by the caller (EventsPage) for its existing client-side
// search/filter/sort, which still operates on whatever has been loaded so far.
export function useEventsFeed(enabled: boolean) {
  return useInfiniteQuery({
    queryKey: ["events-feed"],
    queryFn: ({ pageParam }: { pageParam?: string }) =>
      api(
        `/events?limit=${EVENTS_PAGE_SIZE}${
          pageParam ? `&before=${encodeURIComponent(pageParam)}` : ""
        }`,
        eventPageSchema,
      ),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_before ?? undefined,
    enabled,
    refetchInterval: 10000,
  });
}
