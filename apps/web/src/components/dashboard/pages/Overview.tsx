import { useTranslation } from "react-i18next";
import {
  FaArrowRight,
  FaArrowTrendUp,
  FaBolt,
  FaBrain,
  FaChartLine,
  FaCoins,
  FaGauge,
  FaGear,
  FaListCheck,
  FaRadio,
  FaShieldHalved,
  FaWallet,
} from "react-icons/fa6";
import i18n from "../../../lib/i18n";
import type { eventsSchema, marketsSchema, portfolioSchema, systemSchema } from "../../../lib/dto";
import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import { EventList } from "../EventList";
import { liveVenueLabel, useLiveTrading } from "../../../hooks/useLiveTrading";
import type { useProposalsData } from "../../../hooks/useProposalsData";
import { formatMoney, formatNumber, formatPercent, formatRelative } from "../../../lib/format";

const STABLE = new Set(["USDT", "USDC", "USD", "FDUSD", "BUSD", "DAI"]);
const PALETTE = ["#0a84ff", "#30b0c7", "#34c759", "#ff9f0a", "#bf5af2", "#ff375f", "#64d2ff", "#ac8e68"];

type Holding = { asset: string; amount: number; value: number | null; price: number | null };

export function Overview({
  system,
  events,
  portfolio,
  markets,
  proposals,
  environment,
  navigate,
}: {
  system: UseQueryResult<z.infer<typeof systemSchema>>;
  events: UseQueryResult<z.infer<typeof eventsSchema>>;
  portfolio: UseQueryResult<z.infer<typeof portfolioSchema>>;
  markets: UseQueryResult<z.infer<typeof marketsSchema>>;
  proposals: ReturnType<typeof useProposalsData>;
  environment?: "OBSERVE" | "PAPER" | "LIVE";
  navigate: (next: string) => void;
}) {
  useTranslation();
  const isLive = environment === "LIVE";
  const { live } = useLiveTrading(isLive);
  const services = system.data
    ? [
        ["API", system.data.api],
        ["PostgreSQL", system.data.database],
        ["Redis", system.data.redis],
        ...Object.entries(system.data.services).map(([name, value]) => [name, value.status]),
      ]
    : [];
  const unhealthy = services.filter(([, status]) => status !== "HEALTHY");
  const operational = system.data && unhealthy.length === 0;
  const balances = portfolio.data?.balances ?? [];
  const positions = balances.filter((balance) => balance.purpose === "POSITION");
  const cashBalances = balances.filter((balance) => balance.purpose === "CASH");
  const performance = portfolio.data?.performance ?? [];
  const cashCurrency = live.data?.cash_currency ?? "USDT";
  const now = Date.now();
  const pending = (proposals.proposals.data?.rows ?? []).filter(
    (row) => row.decision_status === "PENDING" && Date.parse(row.expires_at) > now,
  );

  // Value each holding with the public bid of its USDT pair, when the market list carries one.
  const prices = new Map<string, number>();
  for (const row of markets.data?.rows ?? []) {
    if (row.quote === "USDT" || row.quote === "USD") prices.set(row.base, Number(row.bid));
  }
  const rawHoldings = isLive
    ? (live.data?.balances ?? []).map((row) => ({ asset: row.asset, amount: Number(row.amount) }))
    : balances.map((row) => ({ asset: row.currency, amount: Number(row.amount) }));
  const holdings: Holding[] = rawHoldings
    .filter((row) => row.amount > 0)
    .map((row) => {
      const price = STABLE.has(row.asset) ? 1 : (prices.get(row.asset) ?? null);
      return { ...row, price, value: price === null ? null : price * row.amount };
    })
    .sort((a, b) => (b.value ?? -1) - (a.value ?? -1));
  const valued = holdings.reduce((sum, row) => sum + (row.value ?? 0), 0);

  const metrics: [string, string, string, typeof FaWallet][] = [
    [
      i18n.t(isLive ? "Efectivo real" : "Efectivo PAPER"),
      isLive
        ? `${live.data?.balances.find((row) => row.asset === cashCurrency)?.amount ?? "—"} ${cashCurrency}`
        : portfolio.data
          ? cashBalances.length
            ? cashBalances.map((balance) => formatMoney(balance.amount, balance.currency)).join(" · ")
            : "—"
          : "—",
      isLive
        ? i18n.t("Saldo reconciliado con {{venue}}", { venue: liveVenueLabel(live.data?.venue) })
        : portfolio.data
          ? i18n.t("Saldo de simulación disponible")
          : i18n.t("Cargando saldo de simulación"),
      FaCoins,
    ],
    [
      i18n.t(isLive ? "Valor de la cuenta real" : "Resultado realizado"),
      isLive
        ? `${live.data?.equity_usd ?? "—"} ${cashCurrency}`
        : performance.length
          ? performance.map((item) => formatMoney(item.realized_pnl, item.quote)).join(" · ")
          : "—",
      isLive
        ? live.data?.as_of
          ? i18n.t("Verificado {{when}}", { when: formatRelative(live.data.as_of) })
          : i18n.t("Sin valoración verificada")
        : performance.length
          ? i18n.t("Calculado con lotes FIFO")
          : i18n.t("Sin cierres registrados"),
      FaWallet,
    ],
    [
      i18n.t("Posiciones abiertas"),
      isLive
        ? String(
            live.data?.balances.filter((row) => row.asset !== cashCurrency && Number(row.amount) > 0)
              .length ?? 0,
          )
        : portfolio.data
          ? String(positions.length)
          : "—",
      isLive
        ? i18n.t("Posiciones reales reconciliadas")
        : portfolio.data
          ? i18n.t("Posiciones registradas en PAPER")
          : i18n.t("Cargando actividad"),
      FaChartLine,
    ],
    [
      i18n.t("Propuestas pendientes"),
      proposals.proposals.data ? String(pending.length) : "—",
      pending.length
        ? i18n.t("Esperan tu aprobación")
        : i18n.t("Los analistas siguen vigilando"),
      FaListCheck,
    ],
  ];

  return (
    <>
      <section className="metrics-grid">
        {metrics.map(([label, value, note, Icon]) => (
          <article className="metric" key={label}>
            <div>
              {label}
              <Icon size={14} aria-hidden="true" />
            </div>
            <strong>{value}</strong>
            <small>{note}</small>
          </article>
        ))}
      </section>

      <section className="dash-grid">
        <div style={{ display: "grid", gap: 24, alignContent: "start" }}>
          <article className="panel">
            <div className="panel-heading">
              <div>
                <h2>{i18n.t("Propuestas pendientes")}</h2>
                <p>{i18n.t("Ideas de los analistas que esperan tu decisión antes de caducar.")}</p>
              </div>
              <button className="text-button" onClick={() => navigate("intelligence#proposals")}>
                {i18n.t("Ver todas")} <FaArrowRight size={12} />
              </button>
            </div>
            {pending.length === 0 ? (
              <div className="empty-state">
                <FaBrain size={24} />
                <strong>{i18n.t("Nada pendiente ahora mismo")}</strong>
                <span>
                  {i18n.t(
                    "Cuando Codex y Claude coincidan en una idea aparecerá aquí y te avisaremos por Telegram.",
                  )}
                </span>
              </div>
            ) : (
              <div className="pending-list">
                {pending.slice(0, 4).map((row) => (
                  <div className="pending-item" key={row.proposal_id}>
                    <span className="asset-icon" aria-hidden="true">
                      {row.base.slice(0, 4)}
                    </span>
                    <div>
                      <strong>
                        {row.direction === "LONG" ? i18n.t("Comprar") : i18n.t("Vender")} {row.base}/
                        {row.quote}
                      </strong>
                      <small>
                        {i18n.t("Entrada")} {formatNumber(row.entry_price)} · {i18n.t("Confianza")}{" "}
                        {formatPercent(Number(row.confidence), 0)} · {i18n.t("Caduca")}{" "}
                        {formatRelative(row.expires_at, now)}
                      </small>
                    </div>
                    <div>
                      <button
                        className="primary-button"
                        onClick={() =>
                          navigate(
                            `intelligence?proposal=${encodeURIComponent(row.proposal_id)}#proposals`,
                          )
                        }
                      >
                        {i18n.t("Revisar")} <FaArrowRight size={12} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </article>

          <article className="panel">
            <div className="panel-heading">
              <div>
                <h2>{i18n.t("Distribución de la cuenta")}</h2>
                <p>
                  {isLive
                    ? i18n.t("Saldos reales valorados con el precio de compra público de cada par.")
                    : i18n.t("Saldos de la cuenta de simulación.")}
                </p>
              </div>
              <button className="text-button" onClick={() => navigate("portfolio")}>
                {i18n.t("Ver portafolio")} <FaArrowRight size={12} />
              </button>
            </div>
            {holdings.length === 0 ? (
              <div className="empty-state">
                <FaWallet size={24} />
                <strong>{i18n.t("Todavía no hay saldos")}</strong>
                <span>{i18n.t("Sin resultados ficticios. Sin rentabilidad supuesta.")}</span>
              </div>
            ) : (
              <>
                {valued > 0 && (
                  <>
                    <div className="allocation-bar" aria-hidden="true">
                      {holdings.map((row, index) =>
                        row.value ? (
                          <span
                            key={row.asset}
                            style={{
                              width: `${(row.value / valued) * 100}%`,
                              background: PALETTE[index % PALETTE.length],
                            }}
                          />
                        ) : null,
                      )}
                    </div>
                    <div className="allocation-legend">
                      {holdings.map((row, index) =>
                        row.value ? (
                          <span key={row.asset}>
                            <i style={{ background: PALETTE[index % PALETTE.length] }} />
                            {row.asset} {formatPercent(row.value / valued)}
                          </span>
                        ) : null,
                      )}
                    </div>
                  </>
                )}
                <div className="markets-table-wrap" style={{ marginTop: 16 }}>
                  <table className="markets-table">
                    <thead>
                      <tr>
                        <th>{i18n.t("Activo")}</th>
                        <th className="num">{i18n.t("Cantidad")}</th>
                        <th className="num hide-sm">{i18n.t("Precio")}</th>
                        <th className="num">{i18n.t("Valor")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {holdings.map((row) => (
                        <tr key={row.asset}>
                          <td>
                            <span className="asset-cell">
                              <span className="asset-icon">{row.asset.slice(0, 4)}</span>
                              {row.asset}
                            </span>
                          </td>
                          <td className="num">{formatNumber(row.amount)}</td>
                          <td className="num hide-sm">{row.price === null ? "—" : formatNumber(row.price)}</td>
                          <td className="num">
                            {row.value === null ? "—" : formatMoney(row.value, isLive ? cashCurrency : null)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </article>
        </div>

        <div style={{ display: "grid", gap: 24, alignContent: "start" }}>
          <article className="panel">
            <div className="panel-heading">
              <h2>{i18n.t("Acciones rápidas")}</h2>
              <FaBolt size={15} aria-hidden="true" />
            </div>
            <div className="quick-actions">
              {(
                [
                  ["intelligence#proposals", FaListCheck, "Revisar propuestas", "Aprueba o rechaza ideas de los analistas"],
                  ["markets", FaArrowTrendUp, "Explorar mercados", "Precios, spread y calidad de datos"],
                  ["risk", FaShieldHalved, "Controles de riesgo", "Pérdidas, drawdown y breakers"],
                  ["settings", FaGear, "Límites y analistas", "Cuenta real, IA y Telegram"],
                ] as const
              ).map(([target, Icon, title, hint]) => (
                <button key={target} className="quick-action" onClick={() => navigate(target)}>
                  <Icon size={18} />
                  <strong>{i18n.t(title)}</strong>
                  <small>{i18n.t(hint)}</small>
                </button>
              ))}
            </div>
          </article>

          {isLive && live.data && (
            <article className="panel">
              <div className="panel-heading">
                <h2>{i18n.t("Límites LIVE")}</h2>
                <span className={`badge ${live.data.state === "READY" ? "positive" : "warning"}`}>
                  {live.data.state}
                </span>
              </div>
              <div className="kpi-row compact" style={{ marginBottom: 0 }}>
                <div className="kpi">
                  <small>{i18n.t("Máximo por operación")}</small>
                  <strong>{formatMoney(live.data.max_order_usd, cashCurrency)}</strong>
                </div>
                <div className="kpi">
                  <small>{i18n.t("Exposición total máxima")}</small>
                  <strong>{formatMoney(live.data.max_total_usd, cashCurrency)}</strong>
                </div>
                <div className="kpi">
                  <small>{i18n.t("Pérdida diaria máxima")}</small>
                  <strong>{formatMoney(live.data.max_daily_loss_usd, cashCurrency)}</strong>
                </div>
              </div>
            </article>
          )}

          <article className="panel system-summary">
            <div className="panel-heading">
              <h2>{i18n.t("Estado del sistema")}</h2>
              <FaRadio size={15} aria-hidden="true" />
            </div>
            <div className="system-state">
              <span className={operational ? "status-light" : "status-light pending"} />
              <div>
                <strong>
                  {system.isPending
                    ? i18n.t("Comprobando servicios")
                    : operational
                      ? i18n.t("Base operativa disponible")
                      : i18n.t("Requiere atención")}
                </strong>
                <small>
                  {system.data
                    ? i18n.t("{{ok}} de {{total}} servicios disponibles", {
                        ok: services.length - unhealthy.length,
                        total: services.length,
                      })
                    : i18n.t("Estado observado de los servicios")}
                </small>
              </div>
            </div>
            {unhealthy.length > 0 && (
              <div className="service-mini" style={{ marginBottom: 12 }}>
                {unhealthy.map(([name]) => (
                  <span key={name} className="badge warning">
                    {name}
                  </span>
                ))}
              </div>
            )}
            <button className="text-button" onClick={() => navigate("system")}>
              <FaGauge size={13} /> {i18n.t("Ver todos los servicios")}
            </button>
          </article>
        </div>
      </section>

      <section>
        <article className="panel">
          <div className="panel-heading">
            <h2>{i18n.t("Actividad reciente")}</h2>
            <button className="text-button" onClick={() => navigate("events")}>
              {i18n.t("Ver todo")} <FaArrowRight size={12} />
            </button>
          </div>
          <EventList events={events.data?.slice(0, 5)} />
        </article>
      </section>
    </>
  );
}
