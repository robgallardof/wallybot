import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import type {
  entityGraphSchema,
  priceConsensusSchema,
  providerReliabilitySchema,
  smartMoneySchema,
  tokenRiskSchema,
  walletActivitySchema,
  whaleFlowSchema,
} from "../../../lib/dto";
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
}: {
  smartMoney: UseQueryResult<z.infer<typeof smartMoneySchema>>;
  whaleFlow: UseQueryResult<z.infer<typeof whaleFlowSchema>>;
  tokenRisk: UseQueryResult<z.infer<typeof tokenRiskSchema>>;
  providerReliability: UseQueryResult<z.infer<typeof providerReliabilitySchema>>;
  priceConsensus: UseQueryResult<z.infer<typeof priceConsensusSchema>>;
  walletActivity: UseQueryResult<z.infer<typeof walletActivitySchema>>;
  entityGraph: UseQueryResult<z.infer<typeof entityGraphSchema>>;
}) {
  return (
    <div className="intelligence-stack">
      <SmartMoneyPage smartMoney={smartMoney} />
      <WhaleFlowSection whaleFlow={whaleFlow} />
      <TokenRiskSection tokenRisk={tokenRisk} />
      <ProviderReliabilitySection providerReliability={providerReliability} />
      <PriceConsensusSection priceConsensus={priceConsensus} />
      <WalletActivitySection walletActivity={walletActivity} />
      <EntityGraphSection entityGraph={entityGraph} />
    </div>
  );
}
