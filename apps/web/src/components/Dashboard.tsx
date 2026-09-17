import { useTranslation } from "react-i18next";
import { usePathname, useRouter } from "next/navigation";
import type { z } from "zod";
import type { meSchema } from "../lib/dto";
import { useBacktestsData } from "../hooks/useBacktestsData";
import { useDashboardData } from "../hooks/useDashboardData";
import { useMarketsData } from "../hooks/useMarketsData";
import { useSmartMoneyData } from "../hooks/useSmartMoneyData";
import { useWhaleFlowData } from "../hooks/useWhaleFlowData";
import { useTokenRiskData } from "../hooks/useTokenRiskData";
import { useProviderReliabilityData } from "../hooks/useProviderReliabilityData";
import { usePriceConsensusData } from "../hooks/usePriceConsensusData";
import { useWalletActivityData } from "../hooks/useWalletActivityData";
import { useEntityGraphData } from "../hooks/useEntityGraphData";
import { DashboardShell } from "./dashboard/DashboardShell";
import { Overview } from "./dashboard/pages/Overview";
import { SystemPage } from "./dashboard/pages/SystemPage";
import { EventsPage } from "./dashboard/pages/EventsPage";
import { RiskPage } from "./dashboard/pages/RiskPage";
import { MarketsPage } from "./dashboard/pages/MarketsPage";
import { IntelligencePage } from "./dashboard/pages/IntelligencePage";
import { BacktestsPage } from "./dashboard/pages/BacktestsPage";
import { ConnectionsPage } from "./dashboard/pages/ConnectionsPage";
import { useConnectionsData } from "../hooks/useConnectionsData";
import { useTelegramData } from "../hooks/useTelegramData";
import { SettingsPage } from "./dashboard/pages/SettingsPage";
import { DocsPage } from "./dashboard/pages/DocsPage";
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
    "connections",
    "settings",
    "docs",
  ].includes(initial)
    ? initial
    : "dashboard";
  const { dashboard, system, events, change, confirmMfa } = useDashboardData();
  const markets = useMarketsData(page === "markets");
  const smartMoney = useSmartMoneyData(page === "intelligence");
  const whaleFlow = useWhaleFlowData(page === "intelligence");
  const tokenRisk = useTokenRiskData(page === "intelligence");
  const providerReliability = useProviderReliabilityData(
    page === "intelligence",
  );
  const priceConsensus = usePriceConsensusData(page === "intelligence");
  const walletActivity = useWalletActivityData(page === "intelligence");
  const entityGraph = useEntityGraphData(page === "intelligence");
  const { history: backtestHistory, run: runBacktest } = useBacktestsData(
    page === "research",
  );
  const { connections, add: addConnection } = useConnectionsData(
    page === "connections",
  );
  const { telegram, save: saveTelegram } = useTelegramData(page === "settings");
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
      environment={dashboard.data?.environment}
    >
      {page === "dashboard" && (
        <Overview system={system} events={events} navigate={navigate} />
      )}
      {page === "system" && <SystemPage system={system} />}
      {page === "events" && <EventsPage events={events} />}
      {page === "markets" && <MarketsPage markets={markets} />}
      {page === "intelligence" && (
        <IntelligencePage
          smartMoney={smartMoney}
          whaleFlow={whaleFlow}
          tokenRisk={tokenRisk}
          providerReliability={providerReliability}
          priceConsensus={priceConsensus}
          walletActivity={walletActivity}
          entityGraph={entityGraph}
        />
      )}
      {page === "risk" && (
        <RiskPage dashboard={dashboard} change={change} role={user.role} />
      )}
      {page === "research" && (
        <BacktestsPage history={backtestHistory} run={runBacktest} />
      )}
      {page === "portfolio" && <Unavailable />}
      {page === "connections" && (
        <ConnectionsPage connections={connections} add={addConnection} />
      )}
      {page === "settings" && (
        <SettingsPage
          dashboard={dashboard}
          change={change}
          role={user.role}
          telegram={telegram}
          saveTelegram={saveTelegram}
          confirmMfa={confirmMfa}
        />
      )}
      {page === "docs" && <DocsPage />}
    </DashboardShell>
  );
}
