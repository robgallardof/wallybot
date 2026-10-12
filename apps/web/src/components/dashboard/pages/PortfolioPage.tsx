import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import { FaArrowRight, FaCircleDollarToSlot, FaRobot, FaWallet } from "react-icons/fa6";
import type { z } from "zod";
import i18n from "../../../lib/i18n";
import type { portfolioSchema } from "../../../lib/dto";
import { LivePortfolioPanel } from "./LiveTradingPanel";

function displayAmount(amount: string): string {
  const value = Number(amount);
  if (!Number.isFinite(value)) return amount;
  return new Intl.NumberFormat(i18n.resolvedLanguage, {
    maximumFractionDigits: 8,
  }).format(value);
}

function heldFor(seconds: number): string {
  if (seconds < 3600) return i18n.t("menos de una hora");
  if (seconds < 86400) return i18n.t("{{count}} h", { count: Math.floor(seconds / 3600) });
  return i18n.t("{{count}} d", { count: Math.floor(seconds / 86400) });
}

type Portfolio = z.infer<typeof portfolioSchema>;
type CancelOrder = UseMutationResult<{ client_order_id: string; status: string }, Error, string>;

/** The balances/performance/activity/orders panels shared by the deterministic PAPER account and
 * the AI-autonomous one -- same shape (`GET /api/portfolio` and `GET /api/portfolio/ai` both
 * return a `PortfolioView`), rendered twice with different framing/copy rather than duplicated,
 * since the two accounts are fully separate ledgers (.ai/DECISIONS.md, 2026-09-23). */
function PortfolioAccountPanels({
  data,
  cancelOrder,
}: {
  data: Portfolio;
  cancelOrder?: CancelOrder;
}) {
  const balances = data.balances;
  return (
    <>
      {balances.length > 0 && (
        <article className="panel wide-panel">
          <div className="panel-heading">
            <h2>{i18n.t("Saldos registrados")}</h2>
            <span className="subtle-pill">{i18n.t("SIMULACIÓN PAPER")}</span>
          </div>
          <div className="markets-table-wrap">
            <table className="markets-table">
              <thead>
                <tr>
                  <th>{i18n.t("Activo")}</th>
                  <th>{i18n.t("Tipo")}</th>
                  <th>{i18n.t("Cantidad")}</th>
                </tr>
              </thead>
              <tbody>
                {balances.map((balance) => (
                  <tr key={`${balance.purpose}-${balance.currency}`}>
                    <td>{balance.currency}</td>
                    <td>{balance.purpose === "CASH" ? i18n.t("Efectivo") : i18n.t("Posición")}</td>
                    <td>{displayAmount(balance.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      )}

      {data.performance.length > 0 && (
        <article className="panel wide-panel">
          <div className="panel-heading">
            <h2>{i18n.t("Resultados realizados")}</h2>
          </div>
          <p className="muted">
            {i18n.t(
              "El resultado realizado usa lotes FIFO. El valor no realizado solo aparece cuando exista una cotización verificable.",
            )}
          </p>
          <div className="portfolio-stats portfolio-performance">
            {data.performance.map((item) => (
              <div key={item.quote}>
                <small>{i18n.t("PnL realizado")} · {item.quote}</small>
                <strong>{displayAmount(item.realized_pnl)} {item.quote}</strong>
                <span>{i18n.t("Costo de posiciones abiertas")}: {displayAmount(item.open_cost_basis)} {item.quote}</span>
              </div>
            ))}
          </div>
        </article>
      )}

      {data.proposal_history.length > 0 && (
        <article className="panel wide-panel">
          <div className="panel-heading"><div><h2>{i18n.t("Seguimiento de propuestas IA")}</h2><p className="muted">{i18n.t("Entradas confirmadas y sus niveles registrados. El valor actual solo se muestra cuando exista una cotización verificable.")}</p></div></div>
          <ProposalMonitoringTable rows={data.proposal_history} />
        </article>
      )}

      {data.activity.length > 0 && (
        <article className="panel wide-panel">
          <div className="panel-heading">
            <h2>{i18n.t("Actividad reciente")}</h2>
          </div>
          <div className="markets-table-wrap">
            <table className="markets-table">
              <thead>
                <tr>
                  <th>{i18n.t("Fecha")}</th>
                  <th>{i18n.t("Mercado")}</th>
                  <th>{i18n.t("Lado")}</th>
                  <th>{i18n.t("Cantidad")}</th>
                  <th>{i18n.t("Precio")}</th>
                  <th>{i18n.t("Origen")}</th>
                </tr>
              </thead>
              <tbody>
                {data.activity.map((activity) => (
                  <tr key={activity.id}>
                    <td>{new Date(activity.occurred_at).toLocaleString(i18n.resolvedLanguage)}</td>
                    <td>{activity.base}/{activity.quote} · {activity.venue}</td>
                    <td>{activity.side}</td>
                    <td>{displayAmount(activity.quantity)}</td>
                    <td>{displayAmount(activity.price)} {activity.quote}</td>
                    <td>{activity.proposal_id ? `${i18n.t("Propuesta IA")} · ${activity.proposal_id}` : i18n.t("Estrategia del portafolio")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      )}

      {data.orders.length > 0 && (
        <article className="panel wide-panel">
          <div className="panel-heading"><h2>{i18n.t("Órdenes PAPER")}</h2><span className="subtle-pill">{data.orders.length}</span></div>
          <div className="markets-table-wrap"><table className="markets-table"><thead><tr><th>{i18n.t("Mercado")}</th><th>{i18n.t("Lado")}</th><th>{i18n.t("Cantidad")}</th><th>{i18n.t("Tipo")}</th><th>{i18n.t("Estado")}</th>{cancelOrder && <th>{i18n.t("Acción")}</th>}</tr></thead><tbody>{data.orders.map((order) => <tr key={order.client_order_id}><td>{order.base}/{order.quote} · {order.venue}</td><td>{order.side}</td><td>{displayAmount(order.quantity)}</td><td>{order.kind}</td><td><span className="quality-pill">{order.status}</span></td>{cancelOrder && <td>{!["FILLED", "CANCELLED", "REJECTED", "EXPIRED"].includes(order.status) && <button className="button button-outline" disabled={cancelOrder.isPending} onClick={() => cancelOrder.mutate(order.client_order_id)}>{i18n.t("Cancelar orden")}</button>}</td>}</tr>)}</tbody></table></div>
          {cancelOrder?.isError && <p className="error" role="alert">{i18n.t(cancelOrder.error.message)}</p>}
        </article>
      )}
    </>
  );
}

function ProposalMonitoringTable({ rows }: { rows: Portfolio["proposal_history"] }) {
  const labels: Record<string, string> = {
    CLOSED: "Posición cerrada", QUOTE_UNAVAILABLE: "Cotización no disponible",
    STOP_REACHED: "Stop alcanzado: revisar", TARGET_REACHED: "Objetivo alcanzado: revisar",
    MONITORING: "En seguimiento",
    REDUCTION_FILLED: "Reducción ejecutada",
  };
  return <div className="markets-table-wrap"><table className="markets-table">
    <thead><tr>{["Propuesta", "Entrada", "Tiempo", "Protección", "Precio actual", "Resultado", "Seguimiento"].map(label => <th key={label}>{i18n.t(label)}</th>)}</tr></thead>
    <tbody>{rows.map(item => <tr key={`${item.proposal_id}-${item.filled_at}`}>
      <td><code>{item.proposal_id}</code><br /><small>{item.direction} · {item.base}/{item.quote} · {displayAmount(item.filled_quantity)}</small></td>
      <td>{displayAmount(item.filled_price)} {item.quote}</td>
      <td>{item.direction === "BUY" ? heldFor(item.held_for_seconds) : "—"}</td>
      <td>{item.stop_price ? `${i18n.t("Stop")} ${displayAmount(item.stop_price)}` : "—"}{item.take_profit_price ? ` · ${i18n.t("Objetivo")} ${displayAmount(item.take_profit_price)}` : ""}</td>
      <td>{item.current_price === null ? i18n.t("Cotización no disponible") : <>{displayAmount(item.current_price)} {item.quote}<br /><small>{item.quote_source} · {item.quote_at && new Date(item.quote_at).toLocaleString(i18n.resolvedLanguage)}</small></>}</td>
      <td>{i18n.t("Realizado")}: {displayAmount(item.realized_pnl)} {item.quote}<br />{i18n.t("No realizado")}: {item.unrealized_pnl === null ? "—" : `${displayAmount(item.unrealized_pnl)} ${item.quote}`}</td>
      <td><span className="quality-pill">{i18n.t(labels[item.monitoring_status] ?? item.monitoring_status)}</span><br /><small>{i18n.t("Cantidad abierta")}: {displayAmount(item.remaining_quantity)} · {item.execution_status}</small></td>
    </tr>)}</tbody>
  </table><p className="muted">{i18n.t("Valor estimado al precio de venta disponible, sin comisión futura. Stop y objetivo son avisos de revisión; no ejecutan ventas. Los resultados de entrada y salida describen la misma operación y no se suman.")}</p></div>;
}

function AccountFundingForm({
  fund,
  buttonLabel,
}: {
  fund: UseMutationResult<Portfolio, Error, { amount: string }>;
  buttonLabel: string;
}) {
  const [amount, setAmount] = useState("10000");
  function submit(event: React.FormEvent) {
    event.preventDefault();
    fund.mutate({ amount });
  }
  return (
    <form className="settings-form" onSubmit={submit}>
      <label>
        {i18n.t("Efectivo inicial (USD)")}
        <input
          type="number"
          min="0.01"
          step="0.01"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          required
        />
      </label>
      <button className="button button-primary" disabled={fund.isPending}>
        {buttonLabel}
      </button>
      {fund.isError && (
        <p className="error" role="alert">
          {i18n.t(fund.error.message)}
        </p>
      )}
    </form>
  );
}

export function PortfolioPage({
  portfolio,
  fund,
  cancelOrder,
  navigate,
  aiPortfolio,
  fundAi,
}: {
  portfolio: UseQueryResult<Portfolio>;
  fund: UseMutationResult<Portfolio, Error, { amount: string }>;
  cancelOrder: CancelOrder;
  navigate: (page: string) => void;
  aiPortfolio: UseQueryResult<Portfolio>;
  fundAi: UseMutationResult<Portfolio, Error, { amount: string }>;
}) {
  useTranslation();
  const data = portfolio.data;
  const balances = data?.balances ?? [];
  const positions = balances.filter((balance) => balance.purpose === "POSITION");
  const aiData = aiPortfolio.data;

  return (
    <div className="portfolio-stack">
      <LivePortfolioPanel />
      <article className="panel wide-panel portfolio-hero">
        <div className="portfolio-hero-copy">
          <span className="section-kicker">
            <FaWallet size={15} /> {i18n.t("Instancia desplegada · Cuenta de simulación")}
          </span>
          <h2>{i18n.t("Tu portafolio")}</h2>
          <p className="muted">
            {i18n.t(
              "Esta aplicación está desplegada. PAPER identifica solo la cuenta de pruebas: permite validar saldos y operaciones simuladas sin tocar fondos externos.",
            )}
          </p>
        </div>
        <div className="portfolio-stats" aria-label={i18n.t("Resumen de portafolio")}>
          <div>
            <small>{i18n.t("Conexiones")}</small>
            <strong>{data?.connection_count ?? "—"}</strong>
          </div>
          <div>
            <small>{i18n.t("Posiciones")}</small>
            <strong>{data ? positions.length : "—"}</strong>
          </div>
          <div>
            <small>{i18n.t("Operaciones")}</small>
            <strong>{data?.activity.length ?? "—"}</strong>
          </div>
        </div>
      </article>

      {portfolio.isPending && <p className="muted">{i18n.t("Cargando portafolio…")}</p>}
      {portfolio.isError && (
        <p className="error" role="alert">
          {i18n.t("No se pudo cargar tu portafolio. Inténtalo de nuevo.")}
        </p>
      )}

      {data && balances.length === 0 && (
        <article className="panel portfolio-empty">
          <FaCircleDollarToSlot size={25} />
          <div>
            <h2>{i18n.t("Aún no hay saldos registrados")}</h2>
            <p className="muted">
              {i18n.t(
                "Conectar un proveedor conserva tus credenciales cifradas, pero no importa fondos automáticamente. Fondeá esta cuenta de pruebas para validar el flujo; los fondos reales nunca se mueven desde WallyBot.",
              )}
            </p>
            <AccountFundingForm fund={fund} buttonLabel={i18n.t("Crear saldo inicial de prueba")} />
            <button className="button button-secondary" onClick={() => navigate("connections")}>
              {i18n.t("Ver conexiones")} <FaArrowRight size={14} />
            </button>
          </div>
        </article>
      )}

      {data && <PortfolioAccountPanels data={data} cancelOrder={cancelOrder} />}

      <article className="panel wide-panel portfolio-hero">
        <div className="portfolio-hero-copy">
          <span className="section-kicker">
            <FaRobot size={15} /> {i18n.t("Cuenta separada · Operativa autónoma")}
          </span>
          <h2>{i18n.t("Cuenta PAPER de IA")}</h2>
          <p className="muted">
            {i18n.t(
              "Esta cuenta está separada de tu cuenta PAPER principal. La IA propone; vos aprobás con MFA y WallyBot valida datos y riesgo antes de simular una compra o venta.",
            )}
          </p>
        </div>
      </article>

      {aiPortfolio.isPending && <p className="muted">{i18n.t("Cargando cuenta de IA…")}</p>}
      {aiPortfolio.isError && (
        <p className="error" role="alert">
          {i18n.t("No se pudo cargar la cuenta de IA. Inténtalo de nuevo.")}
        </p>
      )}

      {aiData && aiData.balances.length === 0 && (
        <article className="panel portfolio-empty">
          <FaRobot size={25} />
          <div>
            <h2>{i18n.t("La cuenta de IA todavía no tiene saldo")}</h2>
            <p className="muted">
              {i18n.t(
                "Fondeá esta cuenta para simular las propuestas que apruebes. El saldo es simulado y no mueve dinero externo.",
              )}
            </p>
            <AccountFundingForm fund={fundAi} buttonLabel={i18n.t("Fondear cuenta de IA")} />
          </div>
        </article>
      )}

      {aiData && <PortfolioAccountPanels data={aiData} />}
    </div>
  );
}
