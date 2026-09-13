import { useTranslation } from "react-i18next";
import { usePathname, useRouter } from "next/navigation";
import type { z } from "zod";
import type { meSchema } from "../lib/dto";
import { useDashboardData } from "../hooks/useDashboardData";
import { useMarketsData } from "../hooks/useMarketsData";
import { useSmartMoneyData } from "../hooks/useSmartMoneyData";
import { DashboardShell } from "./dashboard/DashboardShell";
import { Overview } from "./dashboard/pages/Overview";
import { SystemPage } from "./dashboard/pages/SystemPage";
import { EventsPage } from "./dashboard/pages/EventsPage";
import { RiskPage } from "./dashboard/pages/RiskPage";
import { MarketsPage } from "./dashboard/pages/MarketsPage";
import { SmartMoneyPage } from "./dashboard/pages/SmartMoneyPage";
import { Unavailable } from "./dashboard/pages/Unavailable";

export function Dashboard({
  user,
  logout,
}: {
  user: z.infer<typeof meSchema>;
  logout: () => void;
}) {
  useTranslation();
  const router = useRouter();
  const initial = usePathname().slice(1);
  const page = [
    "system",
    "events",
    "research",
    "portfolio",
    "markets",
    "intelligence",
    "risk",
  ].includes(initial)
    ? initial
    : "dashboard";
  const { dashboard, system, events, change } = useDashboardData();
  const markets = useMarketsData(page === "markets");
  const smartMoney = useSmartMoneyData(page === "intelligence");
  function navigate(next: string) {
    router.push(`/${next}`);
  }

  return (
    <DashboardShell
      user={user}
      logout={logout}
      page={page}
      navigate={navigate}
      hasError={Boolean(dashboard.error || system.error || events.error)}
      mutationError={change.error?.message}
    >
      {page === "dashboard" && (
        <Overview system={system} events={events} navigate={navigate} />
      )}
      {page === "system" && <SystemPage system={system} />}
      {page === "events" && <EventsPage events={events} />}
      {page === "markets" && <MarketsPage markets={markets} />}
      {page === "intelligence" && (
        <SmartMoneyPage smartMoney={smartMoney} />
      )}
      {page === "risk" && (
        <RiskPage dashboard={dashboard} change={change} role={user.role} />
      )}
      {(page === "portfolio" || page === "research") && (
        <Unavailable page={page} />
      )}
    </DashboardShell>
  );
}
