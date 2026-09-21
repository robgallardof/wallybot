import { useTranslation } from "react-i18next";
import { AlertTriangle, Pause, Play, ShieldCheck } from "lucide-react";
import i18n from "../../../lib/i18n";
import type { breakerListSchema, dashboardSchema } from "../../../lib/dto";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import { Button } from "../../ui/button";

const BREAKER_LABELS: Record<string, string> = {
  DAILY_LOSS: "Pérdida diaria",
  WEEKLY_LOSS: "Pérdida semanal",
  DRAWDOWN: "Drawdown",
  RECONCILIATION: "Conciliación",
};

export function RiskPage({
  dashboard,
  change,
  breakers,
  clearBreaker,
  role,
}: {
  dashboard: UseQueryResult<z.infer<typeof dashboardSchema>>;
  change: UseMutationResult<unknown, Error, { status: string; environment?: string }>;
  breakers: UseQueryResult<z.infer<typeof breakerListSchema>>;
  clearBreaker: UseMutationResult<unknown, Error, string>;
  role: string;
}) {
  useTranslation();
  const activeBreakers = (breakers.data?.rows ?? []).filter((row) => row.cleared_at === null);

  return (
    <div className="portfolio-stack">
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
            "Pausar registra el estado de control. La monitorización y el mantenimiento siguen activos.",
          )}
        </p>
        {role === "ADMIN" ? (
          <Button
            disabled={!dashboard.data || change.isPending}
            onClick={() =>
              change.mutate({
                status: dashboard.data?.status === "PAUSED" ? "RUNNING" : "PAUSED",
                environment: dashboard.data?.environment,
              })
            }
          >
            {dashboard.data?.status === "PAUSED" ? (
              <Play size={16} />
            ) : (
              <Pause size={16} />
            )}
            {dashboard.data?.status === "PAUSED"
              ? i18n.t("Reanudar instancia")
              : i18n.t("Pausar instancia")}
          </Button>
        ) : (
          <p>
            {i18n.t("Tu rol VIEWER permite consultar, pero no cambiar controles.")}
          </p>
        )}
        <p className="footnote">
          {i18n.t("Requiere una sesión verificada con MFA en los últimos 5 minutos.")}
        </p>
      </article>

      <article className="panel wide-panel">
        <div className="panel-heading">
          <h2>{i18n.t("Circuit breakers")}</h2>
          <AlertTriangle size={20} />
        </div>
        <p className="muted">
          {i18n.t(
            "Pérdida diaria/semanal, drawdown y conciliación se evalúan en cada ciclo de decisión. Un breaker activado bloquea nuevas operaciones hasta que un administrador lo confirme.",
          )}
        </p>
        {breakers.isPending && <p className="muted">{i18n.t("Cargando…")}</p>}
        {breakers.isError && (
          <p className="error" role="alert">
            {i18n.t("No se pudieron cargar los breakers.")}
          </p>
        )}
        {breakers.data && activeBreakers.length === 0 && (
          <p className="muted">{i18n.t("Ningún breaker activo.")}</p>
        )}
        {activeBreakers.length > 0 && (
          <div className="markets-table-wrap">
            <table className="markets-table">
              <thead>
                <tr>
                  <th>{i18n.t("Tipo")}</th>
                  <th>{i18n.t("Motivo")}</th>
                  <th>{i18n.t("Desde")}</th>
                  {role === "ADMIN" && <th>{i18n.t("Acción")}</th>}
                </tr>
              </thead>
              <tbody>
                {activeBreakers.map((row) => (
                  <tr key={row.breaker_type}>
                    <td>{i18n.t(BREAKER_LABELS[row.breaker_type] ?? row.breaker_type)}</td>
                    <td>{row.reason}</td>
                    <td>{new Date(row.tripped_at).toLocaleString(i18n.resolvedLanguage)}</td>
                    {role === "ADMIN" && (
                      <td>
                        <Button
                          disabled={clearBreaker.isPending}
                          onClick={() => clearBreaker.mutate(row.breaker_type)}
                        >
                          {i18n.t("Confirmar y despejar")}
                        </Button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {clearBreaker.isError && (
          <p className="error" role="alert">
            {i18n.t(clearBreaker.error.message)}
          </p>
        )}
      </article>
    </div>
  );
}
