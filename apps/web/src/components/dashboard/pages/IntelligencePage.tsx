import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import { useTranslation } from "react-i18next";
import type {
  entityGraphSchema,
  priceConsensusSchema,
  providerReliabilitySchema,
  smartMoneySchema,
  tokenRiskSchema,
  walletActivitySchema,
  whaleFlowSchema,
} from "../../../lib/dto";
import type { useProposalsData } from "../../../hooks/useProposalsData";
import { ProposalsSection } from "./ProposalsSection";
import { SmartMoneyPage } from "./SmartMoneyPage";
import { WhaleFlowSection } from "./WhaleFlowSection";
import { TokenRiskSection } from "./TokenRiskSection";
import { ProviderReliabilitySection } from "./ProviderReliabilitySection";
import { PriceConsensusSection } from "./PriceConsensusSection";
import { WalletActivitySection } from "./WalletActivitySection";
import { EntityGraphSection } from "./EntityGraphSection";

export function IntelligencePage({
  smartMoney,
  whaleFlow,
  tokenRisk,
  providerReliability,
  priceConsensus,
  walletActivity,
  entityGraph,
  proposals,
  canSimulate,
  environment,
}: {
  smartMoney: UseQueryResult<z.infer<typeof smartMoneySchema>>;
  whaleFlow: UseQueryResult<z.infer<typeof whaleFlowSchema>>;
  tokenRisk: UseQueryResult<z.infer<typeof tokenRiskSchema>>;
  providerReliability: UseQueryResult<
    z.infer<typeof providerReliabilitySchema>
  >;
  priceConsensus: UseQueryResult<z.infer<typeof priceConsensusSchema>>;
  walletActivity: UseQueryResult<z.infer<typeof walletActivitySchema>>;
  entityGraph: UseQueryResult<z.infer<typeof entityGraphSchema>>;
  proposals: ReturnType<typeof useProposalsData>;
  canSimulate: boolean;
  environment?: string;
}) {
  const { t } = useTranslation();
  const sections = [
    { id: "proposals", label: "Propuestas de WallyBot", query: proposals.proposals, content: <ProposalsSection proposals={proposals} canSimulate={canSimulate} environment={environment} /> },
    {
      id: "smart-money",
      label: "Wallets Smart Money",
      query: smartMoney,
      content: <SmartMoneyPage smartMoney={smartMoney} />,
    },
    {
      id: "whale-flow",
      label: "Transferencias de ballenas",
      query: whaleFlow,
      content: <WhaleFlowSection whaleFlow={whaleFlow} />,
    },
    {
      id: "token-risk",
      label: "Riesgo de tokens",
      query: tokenRisk,
      content: <TokenRiskSection tokenRisk={tokenRisk} />,
    },
    {
      id: "providers",
      label: "Confiabilidad de proveedores",
      query: providerReliability,
      content: (
        <ProviderReliabilitySection providerReliability={providerReliability} />
      ),
    },
    {
      id: "prices",
      label: "Consenso de precios",
      query: priceConsensus,
      content: <PriceConsensusSection priceConsensus={priceConsensus} />,
    },
    {
      id: "wallet-activity",
      label: "Actividad de wallets",
      query: walletActivity,
      content: <WalletActivitySection walletActivity={walletActivity} />,
    },
    {
      id: "entities",
      label: "Grafo de correlación de entidades",
      query: entityGraph,
      content: <EntityGraphSection entityGraph={entityGraph} />,
    },
  ];
  return (
    <div className="intelligence-stack">
      <nav
        className="panel intelligence-index"
        aria-label={t("Explorar inteligencia")}
        id="intelligence-index"
        tabIndex={-1}
      >
        <h2>{t("Explorar señales")}</h2>
        <p className="muted">
          {t(
            "Accede a cada fuente de observación y comprueba si hay registros disponibles.",
          )}
        </p>
        <ul>
          {sections.map(({ id, label, query }) => (
            <li key={id}>
              <a href={`#signal-${id}`}>
                <span>{t(label)}</span>
                <small>
                  {query.isPending
                    ? t("Cargando…")
                    : query.isError
                      ? t("Consulta con error")
                      : t("{{count}} registros", {
                          count: query.data?.rows.length ?? 0,
                        })}
                </small>
              </a>
            </li>
          ))}
        </ul>
      </nav>
      {sections.map(({ id, content }) => (
        <div
          key={id}
          id={`signal-${id}`}
          className="intelligence-section"
          tabIndex={-1}
        >
          {content}
          <a className="intelligence-return" href="#intelligence-index">
            {t("Volver a las señales")}
          </a>
        </div>
      ))}
    </div>
  );
}
