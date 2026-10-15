import { useTranslation } from "react-i18next";
import { useEffect, useRef, useState } from "react";
import {
  FaArrowTrendDown,
  FaArrowTrendUp,
  FaCheck,
  FaChevronDown,
  FaClock,
  FaFlask,
  FaLightbulb,
  FaShieldHalved,
  FaTriangleExclamation,
  FaXmark,
} from "react-icons/fa6";
import type { useProposalsData } from "../../../hooks/useProposalsData";
import { liveVenueLabel, useLiveTrading } from "../../../hooks/useLiveTrading";
import { formatDateTime, formatNumber, formatPercent, formatRelative } from "../../../lib/format";

type Proposal = NonNullable<ReturnType<typeof useProposalsData>["proposals"]["data"]>["rows"][number];
type Filter = "all" | "pending" | "decided";

/** Ticks every 30 s so countdowns and expiry states stay current without a refetch. */
function useNow(intervalMs = 30000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs]);
  return now;
}

function distance(from: string, to: string | null): number | null {
  if (to === null) return null;
  const base = Number(from);
  const target = Number(to);
  if (!Number.isFinite(base) || !Number.isFinite(target) || base === 0) return null;
  return (target - base) / base;
}

export function ProposalsSection({
  proposals,
  canSimulate,
  environment = "OBSERVE",
}: {
  proposals: ReturnType<typeof useProposalsData>;
  canSimulate: boolean;
  environment?: string;
}) {
  const { t } = useTranslation();
  const { proposals: query, decide } = proposals;
  const rows = query.data?.rows ?? [];
  const isLive = environment === "LIVE";
  const { live, configure } = useLiveTrading(isLive);
  const [confirmed, setConfirmed] = useState<string | null>(null);
  const [rearmConfirmed, setRearmConfirmed] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");
  const panel = useRef<HTMLElement>(null);
  // Open state is decided once per proposal (actionable ones start expanded); afterwards the
  // operator's own toggling wins and a decision never collapses the card showing its outcome.
  const initiallyOpen = useRef(new Map<string, boolean>());
  const now = useNow();
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const proposalId = params.get("proposal");
    if (!proposalId || !query.data) return;
    const details = Array.from(panel.current?.querySelectorAll("details") ?? []).find(
      (element) => element.dataset.proposal === proposalId,
    );
    if (details) {
      details.open = true;
      details.scrollIntoView({ block: "center" });
    }
  }, [query.data]);

  const isActionable = (row: Proposal) =>
    row.decision_status === "PENDING" && Date.parse(row.expires_at) > now;
  const pendingCount = rows.filter(isActionable).length;
  const visible = rows
    .filter((row) =>
      filter === "pending"
        ? row.decision_status === "PENDING"
        : filter === "decided"
          ? row.decision_status !== "PENDING"
          : true,
    )
    .sort((a, b) => Number(isActionable(b)) - Number(isActionable(a)));

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
  const liveReady = live.data?.state === "READY" && Boolean(live.data?.enabled);
  const currency = live.data?.cash_currency ?? "USD";

  // A blocked account is rearmed right here with the limits already saved; the API reconciles
  // the exchange account and asks for MFA again, so no safety check is skipped.
  function rearmLive() {
    const data = live.data;
    if (!data?.connection_id) return;
    configure.mutate(
      {
        connection_id: data.connection_id,
        enabled: true,
        confirmation: "LIVE",
        max_order_usd: data.max_order_usd ?? "",
        max_daily_loss_usd: data.max_daily_loss_usd ?? "",
        max_total_usd: data.max_total_usd ?? "",
        slippage_pct: data.slippage_pct ?? "",
      },
      { onSuccess: () => setRearmConfirmed(false) },
    );
  }

  function statusBadge(row: Proposal) {
    const expired = Date.parse(row.expires_at) <= now;
    if (row.decision_status === "PENDING" && expired)
      return <span className="badge">{t("Caducada")}</span>;
    const tone =
      row.decision_status === "APPROVED"
        ? "positive"
        : row.decision_status === "REJECTED"
          ? "danger"
          : row.decision_status === "PENDING"
            ? "accent live"
            : "warning";
    return <span className={`badge ${tone}`}>{statusLabel[row.decision_status]}</span>;
  }

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
        </div>
      </div>
      {isLive && (
        <div className="limits-strip">
          <span className={`badge ${liveReady ? "positive" : "warning"}`}>
            LIVE · {live.data?.state ?? "—"}
          </span>
          <span className="badge plain">
            {t("Máximo por operación")}: {live.data?.max_order_usd ?? "—"} {currency}
          </span>
          <span className="badge plain">
            {t("Exposición total máxima")}: {live.data?.max_total_usd ?? "—"} {currency}
          </span>
          <span className="badge plain">
            {t("Pérdida diaria máxima")}: {live.data?.max_daily_loss_usd ?? "—"} {currency}
          </span>
        </div>
      )}
      {rows.length > 0 && (
        <div className="proposal-toolbar">
          <div className="segmented" role="group" aria-label={t("Filtrar propuestas")}>
            {(
              [
                ["all", t("Todas"), rows.length],
                ["pending", t("Pendientes"), rows.filter((row) => row.decision_status === "PENDING").length],
                ["decided", t("Decididas"), rows.filter((row) => row.decision_status !== "PENDING").length],
              ] as const
            ).map(([key, label, count]) => (
              <button
                key={key}
                type="button"
                aria-pressed={filter === key}
                onClick={() => setFilter(key)}
              >
                {label} · {count}
              </button>
            ))}
          </div>
          {pendingCount > 0 && (
            <span className="badge accent live">
              {t("{{count}} esperando tu decisión", { count: pendingCount })}
            </span>
          )}
        </div>
      )}
      {query.isPending && <p className="muted">{t("Cargando…")}</p>}
      {query.isError && <p className="error">{t("No se pudieron cargar las propuestas.")}</p>}
      {!query.isPending && rows.length === 0 && (
        <div className="empty-state">
          <FaLightbulb size={26} />
          <strong>{t("Aún no hay propuestas")}</strong>
          <span>
            {t("Aún no hay propuestas. WallyBot seguirá analizando el contexto configurado.")}
          </span>
        </div>
      )}
      <div className="proposal-list">
        {visible.map((row) => {
          const expired = Date.parse(row.expires_at) <= now;
          const actionable = row.decision_status === "PENDING" && !expired;
          const isBuy = row.direction === "LONG";
          const stopMove = distance(row.entry_price, row.stop_price);
          const targetMove = distance(row.entry_price, row.take_profit_price);
          const stop = Number(row.stop_price);
          const target = Number(row.take_profit_price);
          const entry = Number(row.entry_price);
          const position =
            row.stop_price && row.take_profit_price && target !== stop
              ? Math.min(100, Math.max(0, ((entry - stop) / (target - stop)) * 100))
              : null;
          const confidence = Number(row.confidence);
          if (!initiallyOpen.current.has(row.proposal_id))
            initiallyOpen.current.set(row.proposal_id, actionable);
          return (
            <details
              className={`proposal-card${actionable ? " is-actionable" : ""}${
                row.decision_status !== "PENDING" || expired ? " is-muted" : ""
              }`}
              key={row.proposal_id}
              data-proposal={row.proposal_id}
              open={initiallyOpen.current.get(row.proposal_id) || undefined}
            >
              <summary>
                <span className="asset-icon" aria-hidden="true">
                  {row.base.slice(0, 4)}
                </span>
                <span className="proposal-title">
                  <strong>
                    <span className={`badge plain ${isBuy ? "positive" : "danger"}`}>
                      {isBuy ? <FaArrowTrendUp size={11} /> : <FaArrowTrendDown size={11} />}
                      {isBuy ? t("Comprar") : t("Vender")}
                    </span>
                    {row.base}/{row.quote}
                  </strong>
                  <small>
                    {t("Entrada")} {formatNumber(row.entry_price)} {row.quote} ·{" "}
                    {t("Confianza")} {formatPercent(confidence, 0)} ·{" "}
                    {formatRelative(row.as_of, now)}
                  </small>
                </span>
                <span className="proposal-side">
                  {statusBadge(row)}
                  {actionable && (
                    <small className="muted">
                      <FaClock size={11} /> {t("Caduca")} {formatRelative(row.expires_at, now)}
                    </small>
                  )}
                  <FaChevronDown className="proposal-chevron" size={13} aria-hidden="true" />
                </span>
              </summary>
              <div className="proposal-body">
                <div>
                  <div className="levels">
                    <div className="level stop">
                      <small>{t("Stop de protección")}</small>
                      <strong>{formatNumber(row.stop_price)}</strong>
                      {stopMove !== null && <em>{formatPercent(stopMove)}</em>}
                    </div>
                    <div className="level">
                      <small>{t("Entrada")}</small>
                      <strong>{formatNumber(row.entry_price)}</strong>
                      <em className="muted">{row.quote}</em>
                    </div>
                    <div className="level target">
                      <small>{t("Objetivo")}</small>
                      <strong>{formatNumber(row.take_profit_price)}</strong>
                      {targetMove !== null && <em>+{formatPercent(targetMove)}</em>}
                    </div>
                  </div>
                  {position !== null && (
                    <>
                      <div className="range-track" style={{ marginTop: 14 }} aria-hidden="true">
                        <i style={{ left: `${position}%` }} />
                      </div>
                      <div className="range-labels" aria-hidden="true">
                        <span>{t("Stop")}</span>
                        <span>{t("Objetivo")}</span>
                      </div>
                    </>
                  )}
                </div>
                <dl className="proposal-facts">
                  <div>
                    <dt>{t("Monto sugerido")}</dt>
                    <dd>{formatPercent(Number(row.suggested_allocation_pct))}</dd>
                  </div>
                  <div>
                    <dt>{t("Confianza")}</dt>
                    <dd>
                      {formatPercent(confidence, 0)}
                      <div className="meter">
                        <span style={{ width: `${Math.round(confidence * 100)}%` }} />
                      </div>
                    </dd>
                  </div>
                  <div>
                    <dt>{t("Válida hasta")}</dt>
                    <dd>
                      <time dateTime={row.expires_at}>{formatDateTime(row.expires_at)}</time>
                    </dd>
                  </div>
                  <div>
                    <dt>{t("Analistas")}</dt>
                    <dd>{row.model_id.replace("consensus:", "").replace("+", " + ")}</dd>
                  </div>
                </dl>
                <div className="proposal-notes">
                  <section className="why">
                    <h4>
                      <FaLightbulb size={12} /> {t("Motivos")}
                    </h4>
                    <ul>
                      {row.reasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  </section>
                  <section className="risk">
                    <h4>
                      <FaTriangleExclamation size={12} /> {t("Riesgos")}
                    </h4>
                    <ul>
                      {row.risks.length ? (
                        row.risks.map((risk) => <li key={risk}>{risk}</li>)
                      ) : (
                        <li>{t("No especificados")}</li>
                      )}
                    </ul>
                  </section>
                </div>
                {row.simulation && (
                  <div
                    className={`outcome ${row.simulation.risk_decision === "REJECTED" ? "bad" : "neutral"}`}
                  >
                    <FaFlask size={14} />
                    <span>
                      {t("Resultado de simulación")}:{" "}
                      {row.simulation.risk_decision ?? t("Sin aprobación de asignación")} ·{" "}
                      {row.simulation.reasons.join(" · ")}
                    </span>
                  </div>
                )}
                {row.execution && (
                  <div
                    className={`outcome ${row.execution.client_order_id ? "" : "bad"}`}
                    role="status"
                  >
                    {row.execution.client_order_id ? <FaCheck size={14} /> : <FaXmark size={14} />}
                    <span>
                      {t("Resultado de la aprobación")}:{" "}
                      {row.execution.environment === "LIVE"
                        ? `LIVE · ${row.execution.status}`
                        : (executionLabel[row.execution.status] ?? row.execution.status)}
                      {row.execution.reasons.length ? ` · ${row.execution.reasons.join(" · ")}` : ""}
                    </span>
                  </div>
                )}
                {row.decision_status === "PENDING" && expired && (
                  <div className="outcome neutral">
                    <FaClock size={14} />
                    <span>
                      {t(
                        "Esta propuesta caducó; ya no puede aprobarse ni simularse. Puedes rechazarla para archivarla.",
                      )}
                    </span>
                  </div>
                )}
                {row.decision_status === "PENDING" && (
                  <div className="proposal-decision">
                    {isLive && !expired && (
                      <label className="confirm-live">
                        <input
                          type="checkbox"
                          checked={confirmed === row.proposal_id}
                          onChange={(event) =>
                            setConfirmed(event.target.checked ? row.proposal_id : null)
                          }
                        />
                        {t("Confirmo esta operación con dinero real")}
                      </label>
                    )}
                    <div className="action-bar">
                      {!expired && (
                        <button
                          className="primary-button button-lg"
                          disabled={
                            decide.isPending ||
                            (isLive && (confirmed !== row.proposal_id || !liveReady))
                          }
                          onClick={() =>
                            decide.mutate(
                              {
                                proposalId: row.proposal_id,
                                decision: "approve",
                                environment: canSimulate ? "PAPER" : environment,
                                liveVersion: isLive ? (live.data?.version ?? undefined) : undefined,
                              },
                              { onSuccess: () => setConfirmed(null) },
                            )
                          }
                        >
                          <FaCheck size={14} />
                          {t(isLive ? "Aprobar operación real" : "Aprobar")}
                        </button>
                      )}
                      {canSimulate && !expired && (
                        <button
                          className="secondary-button button-lg"
                          disabled={decide.isPending}
                          onClick={() =>
                            decide.mutate({ proposalId: row.proposal_id, decision: "simulate" })
                          }
                        >
                          <FaFlask size={13} />
                          {t("Simular")}
                        </button>
                      )}
                      <button
                        className="secondary-button danger-outline button-lg"
                        disabled={decide.isPending}
                        onClick={() =>
                          decide.mutate({ proposalId: row.proposal_id, decision: "reject" })
                        }
                      >
                        <FaXmark size={14} />
                        {t("Rechazar")}
                      </button>
                    </div>
                    {isLive && !expired && !liveReady && (
                      <div className="outcome bad" role="status">
                        <FaTriangleExclamation size={14} />
                        <span>
                          {t("LIVE está en pausa ({{state}})", { state: live.data?.state ?? "—" })}
                          {live.data?.reason ? ` · ${t(live.data.reason)}` : ""}
                        </span>
                      </div>
                    )}
                    {isLive && !expired && !liveReady && live.data?.configured && (
                      <div className="action-bar">
                        <label className="confirm-live">
                          <input
                            type="checkbox"
                            checked={rearmConfirmed}
                            onChange={(event) => setRearmConfirmed(event.target.checked)}
                          />
                          {t("Rearmar LIVE con los límites actuales")}
                        </label>
                        <button
                          className="danger-button button-lg"
                          disabled={configure.isPending || !rearmConfirmed || !live.data?.capable}
                          onClick={rearmLive}
                        >
                          <FaShieldHalved size={13} />
                          {t(configure.isPending ? "Verificando cuenta…" : "Verificar y rearmar LIVE")}
                        </button>
                      </div>
                    )}
                    {isLive && configure.isError && (
                      <p className="error" role="alert">
                        {t(configure.error.message)}
                      </p>
                    )}
                    {!canSimulate && !isLive && !expired && (
                      <p className="muted">
                        {t(
                          "La simulación está desactivada. Podés habilitar PAPER de forma explícita en Configuración.",
                        )}
                      </p>
                    )}
                    <p className="muted" style={{ margin: 0, fontSize: 12 }}>
                      {t("La confirmación requiere MFA.")}
                    </p>
                  </div>
                )}
                {decide.isError && (
                  <p className="error">
                    {t("No se pudo registrar la decisión. Confirma tu identidad e inténtalo de nuevo.")}
                  </p>
                )}
                <div className="proposal-meta">
                  <span>
                    {t("Identificador")}: <code>{row.proposal_id}</code>
                  </span>
                  <span>{row.venue}</span>
                </div>
              </div>
            </details>
          );
        })}
      </div>
    </article>
  );
}
