import { useTranslation } from "react-i18next";
import { Pause, Play, ShieldCheck } from "lucide-react";
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
          <div>
            <span className="eyebrow">{i18n.t("CONTROL OPERATIVO")}</span>
            <h2>{i18n.t("Control de la instancia")}</h2>
          </div>
          <ShieldCheck size={20} />
        </div>
        <div className="risk-control-state">
          <span className={dashboard.data?.status === "PAUSED" ? "status-light pending" : "status-light"} />
          <div>
            <h3>
              {dashboard.data?.status === "PAUSED"
                ? i18n.t("Instancia pausada")
                : i18n.t("Instancia en preparación")}
            </h3>
            <p className="muted">
              {i18n.t(
                "Pausar detiene nuevas decisiones. La monitorización y el mantenimiento siguen activos.",
              )}
            </p>
          </div>
          <div className="risk-control-action">
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
                {dashboard.data?.status === "PAUSED" ? <Play size={16} /> : <Pause size={16} />}
                {dashboard.data?.status === "PAUSED"
                  ? i18n.t("Reanudar instancia")
                  : i18n.t("Pausar instancia")}
              </Button>
            ) : (
              <p className="settings-readonly">
                {i18n.t("Tu rol VIEWER permite consultar, pero no cambiar controles.")}
              </p>
            )}
            <small>{i18n.t("Requiere una sesión verificada con MFA en los últimos 5 minutos.")}</small>
          </div>
        </div>
      </article>

      <article className="panel wide-panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">{i18n.t("PROTECCIONES")}</span>
            <h2>{i18n.t("Circuit breakers")}</h2>
          </div>
          <span className={activeBreakers.length ? "quality-pill quality-warning" : "quality-pill quality-pass"}>
            {activeBreakers.length ? i18n.t("{{count}} activos", { count: activeBreakers.length }) : i18n.t("Sin alertas")}
          </span>
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
          <div className="breaker-empty">
            <ShieldCheck size={20} />
            <div>
              <strong>{i18n.t("Ningún breaker activo.")}</strong>
              <p>{i18n.t("Las protecciones están listas y no hay una condición pendiente de revisión.")}</p>
            </div>
          </div>
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
