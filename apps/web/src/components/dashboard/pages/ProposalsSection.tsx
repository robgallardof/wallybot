import { useTranslation } from "react-i18next";
import { useEffect, useRef, useState } from "react";
import type { useProposalsData } from "../../../hooks/useProposalsData";
import { liveVenueLabel, useLiveTrading } from "../../../hooks/useLiveTrading";

export function ProposalsSection({
  proposals,
  canSimulate,
  environment = "OBSERVE",
}: {
  proposals: ReturnType<typeof useProposalsData>;
  canSimulate: boolean;
  environment?: string;
}) {
  const { t, i18n } = useTranslation();
  const { proposals: query, decide } = proposals;
  const rows = query.data?.rows ?? [];
  const isLive = environment === "LIVE";
  const { live } = useLiveTrading(isLive);
  const [confirmed, setConfirmed] = useState<string | null>(null);
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const proposalId = params.get("proposal");
    if (!proposalId || !query.data) return;
    const details = Array.from(
      panel.current?.querySelectorAll("details") ?? [],
    ).find((element) => element.dataset.proposal === proposalId);
    if (details) {
      details.open = true;
      details.scrollIntoView({ block: "center" });
    }
  }, [query.data]);
  const now = Date.now();
  const statusLabel: Record<string, string> = {
    PENDING: t("Pendiente"),
    SIMULATED: t("Simulación solicitada"),
    APPROVED: t("Aprobada"),
    REJECTED: t("Rechazada"),
  };
  const executionLabel: Record<string, string> = {
    OBSERVE_ONLY: t("Sin orden: PAPER está desactivado"),
    EXPIRED: t("Sin orden: la propuesta caducó"),
    BLOCKED: t("Sin orden: bloqueada por los controles de riesgo"),
    FAILED: t("Sin orden: la revalidación falló"),
    FILLED: t("Orden PAPER ejecutada"),
    REJECTED: t("Orden PAPER rechazada por el simulador"),
  };
  return (
    <article ref={panel} className="panel wide-panel">
      <div className="panel-heading">
        <div>
          <h2>{t("Propuestas de WallyBot")}</h2>
          <p>
            {isLive
              ? t(
                  "LIVE: al aprobar, se podrá enviar una orden con dinero real a tu cuenta {{venue}}, después de verificar saldos, precios, límites y riesgo.",
                  { venue: liveVenueLabel(live.data?.venue) },
                )
              : t(
                  "La IA explica una idea; no compra por sí sola. Al aprobarla con PAPER activo, WallyBot revalida datos y riesgo antes de crear una orden simulada. En OBSERVE solo se registra tu decisión.",
                )}
          </p>
          {isLive && (
            <p>
              <strong>
                {t("Máximo por operación")}: {live.data?.max_order_usd ?? "—"}{" "}
                {live.data?.cash_currency ?? "USD"} · {t("Pérdida diaria máxima")}:{" "}
                {live.data?.max_daily_loss_usd ?? "—"} {live.data?.cash_currency ?? "USD"}
              </strong>
            </p>
          )}
          <p className="muted">
            {t(
              "Un enlace de Telegram solo abre la propuesta. Revisá sus datos y elegí una acción; la confirmación requiere MFA.",
            )}
          </p>
        </div>
      </div>
      {query.isPending && <p className="muted">{t("Cargando…")}</p>}
      {query.isError && (
        <p className="error">{t("No se pudieron cargar las propuestas.")}</p>
      )}
      {!query.isPending && rows.length === 0 && (
        <p className="muted">
          {t(
            "Aún no hay propuestas. WallyBot seguirá analizando el contexto configurado.",
          )}
        </p>
      )}
      {rows.map((row) => {
        const expired = Date.parse(row.expires_at) <= now;
        return (
          <details
            className="experiment-details"
            key={row.proposal_id}
            data-proposal={row.proposal_id}
          >
            <summary>
              <strong>
                {row.direction === "LONG" ? t("Comprar") : t("Vender")}:{" "}
                {row.base}/{row.quote}
              </strong>{" "}
              · {row.entry_price} {row.quote} ·{" "}
              {row.decision_status === "PENDING" && expired
                ? t("Caducada")
                : statusLabel[row.decision_status]}
            </summary>
            <dl>
              <dt>{t("Monto sugerido")}</dt>
              <dd>
                {(Number(row.suggested_allocation_pct) * 100).toFixed(1)}%
              </dd>
              <dt>{t("Confianza")}</dt>
              <dd>{(Number(row.confidence) * 100).toFixed(0)}%</dd>
              <dt>{t("Motivos")}</dt>
              <dd>{row.reasons.join(" · ")}</dd>
              <dt>{t("Riesgos")}</dt>
              <dd>
                {row.risks.length
                  ? row.risks.join(" · ")
                  : t("No especificados")}
              </dd>
              <dt>{t("Válida hasta")}</dt>
              <dd>
                <time dateTime={row.expires_at}>
                  {new Date(row.expires_at).toLocaleString(i18n.language)}
                </time>
              </dd>
              <dt>{t("Identificador")}</dt>
              <dd>
                <code>{row.proposal_id}</code>
              </dd>
            </dl>
            {row.simulation && (
              <p
                className={
                  row.simulation.risk_decision === "REJECTED"
                    ? "error"
                    : "muted"
                }
              >
                {t("Resultado de simulación")}:{" "}
                {row.simulation.risk_decision ??
                  t("Sin aprobación de asignación")}{" "}
                · {row.simulation.reasons.join(" · ")}
              </p>
            )}
            {row.execution && (
              <p
                className={row.execution.client_order_id ? "muted" : "error"}
                role="status"
              >
                {t("Resultado de la aprobación")}:{" "}
                {row.execution.environment === "LIVE"
                  ? `LIVE · ${row.execution.status}`
                  : (executionLabel[row.execution.status] ??
                    row.execution.status)}
                {row.execution.reasons.length
                  ? ` · ${row.execution.reasons.join(" · ")}`
                  : ""}
              </p>
            )}
            {row.decision_status === "PENDING" && expired && (
              <p className="muted">
                {t(
                  "Esta propuesta caducó; ya no puede aprobarse ni simularse. Puedes rechazarla para archivarla.",
                )}
              </p>
            )}
            {row.decision_status === "PENDING" && (
              <>
                {isLive && !expired && (
                  <label>
                    <input
                      type="checkbox"
                      checked={confirmed === row.proposal_id}
                      onChange={(event) =>
                        setConfirmed(
                          event.target.checked ? row.proposal_id : null,
                        )
                      }
                    />
                    {t("Confirmo esta operación con dinero real")}
                  </label>
                )}
                <div className="button-row">
                  {canSimulate && !expired && (
                    <button
                      className="secondary-button"
                      disabled={decide.isPending}
                      onClick={() =>
                        decide.mutate({
                          proposalId: row.proposal_id,
                          decision: "simulate",
                        })
                      }
                    >
                      {t("Simular")}
                    </button>
                  )}
                  {!expired && (
                    <button
                      className="primary-button"
                      disabled={
                        decide.isPending ||
                        (isLive &&
                          (confirmed !== row.proposal_id ||
                            live.data?.state !== "READY" ||
                            !live.data?.enabled))
                      }
                      onClick={() =>
                        decide.mutate(
                          {
                            proposalId: row.proposal_id,
                            decision: "approve",
                            environment: canSimulate ? "PAPER" : environment,
                            liveVersion: isLive
                              ? (live.data?.version ?? undefined)
                              : undefined,
                          },
                          { onSuccess: () => setConfirmed(null) },
                        )
                      }
                    >
                      {t(isLive ? "Aprobar operación real" : "Aprobar")}
                    </button>
                  )}
                  <button
                    className="danger-button"
                    disabled={decide.isPending}
                    onClick={() =>
                      decide.mutate({
                        proposalId: row.proposal_id,
                        decision: "reject",
                      })
                    }
                  >
                    {t("Rechazar")}
                  </button>
                </div>
                {!canSimulate && !isLive && !expired && (
                  <p className="muted">
                    {t(
                      "La simulación está desactivada. Podés habilitar PAPER de forma explícita en Configuración.",
                    )}
                  </p>
                )}
              </>
            )}
            {decide.isError && (
              <p className="error">
                {t(
                  "No se pudo registrar la decisión. Confirma tu identidad e inténtalo de nuevo.",
                )}
              </p>
            )}
          </details>
        );
      })}
    </article>
  );
}
