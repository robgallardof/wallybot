import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import type {
  priceConsensusSchema,
  providerReliabilitySchema,
  smartMoneySchema,
  tokenRiskSchema,
  whaleFlowSchema,
} from "../../../lib/dto";
import { SmartMoneyPage } from "./SmartMoneyPage";
import { WhaleFlowSection } from "./WhaleFlowSection";
import { TokenRiskSection } from "./TokenRiskSection";
import { ProviderReliabilitySection } from "./ProviderReliabilitySection";
import { PriceConsensusSection } from "./PriceConsensusSection";

export function IntelligencePage({
  smartMoney,
  whaleFlow,
  tokenRisk,
  providerReliability,
  priceConsensus,
}: {
  smartMoney: UseQueryResult<z.infer<typeof smartMoneySchema>>;
  whaleFlow: UseQueryResult<z.infer<typeof whaleFlowSchema>>;
  tokenRisk: UseQueryResult<z.infer<typeof tokenRiskSchema>>;
  providerReliability: UseQueryResult<z.infer<typeof providerReliabilitySchema>>;
  priceConsensus: UseQueryResult<z.infer<typeof priceConsensusSchema>>;
}) {
  return (
    <div className="intelligence-stack">
      <SmartMoneyPage smartMoney={smartMoney} />
      <WhaleFlowSection whaleFlow={whaleFlow} />
      <TokenRiskSection tokenRisk={tokenRisk} />
      <ProviderReliabilitySection providerReliability={providerReliability} />
      <PriceConsensusSection priceConsensus={priceConsensus} />
    </div>
  );
}
