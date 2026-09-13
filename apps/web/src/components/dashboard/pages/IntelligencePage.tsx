import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import type {
  smartMoneySchema,
  tokenRiskSchema,
  whaleFlowSchema,
} from "../../../lib/dto";
import { SmartMoneyPage } from "./SmartMoneyPage";
import { WhaleFlowSection } from "./WhaleFlowSection";
import { TokenRiskSection } from "./TokenRiskSection";

export function IntelligencePage({
  smartMoney,
  whaleFlow,
  tokenRisk,
}: {
  smartMoney: UseQueryResult<z.infer<typeof smartMoneySchema>>;
  whaleFlow: UseQueryResult<z.infer<typeof whaleFlowSchema>>;
  tokenRisk: UseQueryResult<z.infer<typeof tokenRiskSchema>>;
}) {
  return (
    <div className="intelligence-stack">
      <SmartMoneyPage smartMoney={smartMoney} />
      <WhaleFlowSection whaleFlow={whaleFlow} />
      <TokenRiskSection tokenRisk={tokenRisk} />
    </div>
  );
}
