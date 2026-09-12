import { useTranslation } from "react-i18next";
import { Pause, Play, ShieldCheck } from "lucide-react";
import i18n from "../../../lib/i18n";
import type { dashboardSchema } from "../../../lib/dto";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import { Button } from "../../ui/button";

export function RiskPage({
  dashboard,
  change,
  role,
}: {
  dashboard: UseQueryResult<z.infer<typeof dashboardSchema>>;
  change: UseMutationResult<unknown, Error, string>;
  role: string;
}) {
  useTranslation();
  return (
    <article className="panel wide-panel">
      <div className="panel-heading">
        <h2>{i18n.t("Control de la instancia")}</h2>
        <ShieldCheck size={20} />
      </div>
      <h3>
        {dashboard.data?.status === "PAUSED"
          ? i18n.t("Instancia pausada")
          : i18n.t("Instancia en preparación")}
      </h3>
      <p className="muted">
        {i18n.t(
          "Pausar registra el estado de control. La monitorización y el mantenimiento siguen activos. Esta fase aún no genera operaciones.",
        )}
      </p>
      {role === "ADMIN" ? (
        <Button
          disabled={!dashboard.data || change.isPending}
          onClick={() =>
            change.mutate(
              dashboard.data?.status === "PAUSED" ? "RUNNING" : "PAUSED",
            )
          }
        >
          {dashboard.data?.status === "PAUSED" ? (
            <Play size={16} />
          ) : (
            <Pause size={16} />
          )}
          {dashboard.data?.status === "PAUSED"
            ? i18n.t("Reanudar instancia PAPER")
            : i18n.t("Pausar instancia")}
        </Button>
      ) : (
        <p>
          {i18n.t("Tu rol VIEWER permite consultar, pero no cambiar controles.")}
        </p>
      )}
      <p className="footnote">
        {i18n.t(
          "Requiere una sesión verificada con MFA en los últimos 5 minutos. Los límites de cartera y RiskEngine se implementan en la fase 3.",
        )}
      </p>
    </article>
  );
}
