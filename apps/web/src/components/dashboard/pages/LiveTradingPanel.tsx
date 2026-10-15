import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { liveVenueLabel, useLiveTrading } from "../../../hooks/useLiveTrading";
import { useConnectionsData } from "../../../hooks/useConnectionsData";
import { FaCircleCheck, FaShieldHalved } from "react-icons/fa6";
import { formatDateTime, formatMoney, formatNumber, formatRelative } from "../../../lib/format";

const cents = (value: number) => (Math.floor(value * 100) / 100).toFixed(2);

/**
 * Suggested limits to put the whole verified account to work: ~3% is kept free for fees and
 * price moves, each order is a third of that so the money spreads over a few positions (and
 * stays above Binance's ~5 USDT minimum), and the daily loss matches the built-in 2% breaker.
 */
export function recommendedLimits(equity: number) {
  const total = Math.floor(equity * 0.97 * 100) / 100;
  return {
    total: cents(total),
    order: cents(Math.max(total / 3, Math.min(6, total))),
    dailyLoss: cents(Math.max(1, equity * 0.02)),
  };
}

export function LiveTradingPanel({ role }: { role: string }) {
  const { t } = useTranslation();
  const { live, configure } = useLiveTrading();
  const { connections } = useConnectionsData(true);
  const [connectionId, setConnectionId] = useState("");
  const [orderLimit, setOrderLimit] = useState("");
  const [dailyLoss, setDailyLoss] = useState("");
  const [totalLimit, setTotalLimit] = useState("");
  const [slippage, setSlippage] = useState("");
  const [formError, setFormError] = useState("");
  useEffect(() => {
    if (!live.data?.configured) return;
    setConnectionId(live.data.connection_id ?? "");
    setOrderLimit(live.data.max_order_usd ?? "");
    setDailyLoss(live.data.max_daily_loss_usd ?? "");
    setTotalLimit(live.data.max_total_usd ?? "");
    setSlippage(
      live.data.slippage_pct
        ? String(Number(live.data.slippage_pct) * 100)
        : "",
    );
  }, [
    live.data?.configured,
    live.data?.connection_id,
    live.data?.max_order_usd,
    live.data?.max_daily_loss_usd,
    live.data?.max_total_usd,
    live.data?.slippage_pct,
  ]);
  const candidates =
    connections.data?.rows.filter(
      (row) =>
        (row.provider === "KRAKEN" || row.provider === "BINANCE") &&
        row.mode === "TRADE_ONLY",
    ) ?? [];
  const selectedProvider = candidates.find((row) => row.id === connectionId)?.provider;
  const currency = selectedProvider === "KRAKEN" ? "USD" : "USDT";
  const equity = Number(live.data?.equity_usd ?? 0);
  function applyRecommendation() {
    const suggestion = recommendedLimits(equity);
    setTotalLimit(suggestion.total);
    setOrderLimit(suggestion.order);
    setDailyLoss(suggestion.dailyLoss);
    if (!slippage) setSlippage("0.5");
    setFormError("");
  }
  function limitsError() {
    // Mirrors the API's bounds so the operator sees which value to fix, not a generic 422.
    if (Number(orderLimit) > Number(totalLimit))
      return "El máximo por operación no puede superar la exposición total máxima.";
    if (Number(slippage) <= 0 || Number(slippage) > 2)
      return "El cambio de precio máximo debe estar entre 0,01% y 2%.";
    return "";
  }
  function submit(event: React.FormEvent) {
    event.preventDefault();
    const problem = limitsError();
    setFormError(problem);
    if (problem) return;
    // Adjusting limits of an already armed account needs no extra step; switching real money
    // on from OFF still asks once, with a click instead of typing LIVE.
    if (
      !live.data?.enabled &&
      !window.confirm(t("¿Activar operaciones con dinero real en tu cuenta?"))
    )
      return;
    configure.mutate(
      {
        connection_id: connectionId,
        enabled: true,
        confirmation: "LIVE",
        max_order_usd: orderLimit,
        max_daily_loss_usd: dailyLoss,
        max_total_usd: totalLimit,
        slippage_pct: String(Number(slippage) / 100),
      },
    );
  }
  return (
    <article className="panel wide-panel settings-panel">
      <div className="live-account-head">
        <div>
          <h2>{t("Operaciones con dinero real")}</h2>
          <p className="muted" style={{ margin: 0 }}>
            {t(
              "Conecta tu cuenta en Conexiones y define tus límites. Cada propuesta sigue necesitando tu aprobación con MFA. La IA no recibe tus claves.",
            )}
          </p>
        </div>
        <span
          className={`badge ${
            live.data?.state === "READY" && live.data.enabled
              ? "positive live"
              : live.data?.configured
                ? "warning"
                : ""
          }`}
        >
          {live.data?.state ?? t("Cargando…")}
        </span>
      </div>
      {live.data?.reason && (
        <p className="muted">
          <strong>{t("Último estado")}:</strong> {t(live.data.reason)}
        </p>
      )}
      <ul className="info-list">
        <li>
          <FaCircleCheck size={13} />
          {t(
            "Binance spot: USDT, BTC y ETH; límites en USDT. Sin deuda ni apalancamiento. Las órdenes usan precio límite y cancelan la cantidad que no se llena inmediatamente. Los stops y objetivos son avisos de revisión.",
          )}
        </li>
        <li>
          <FaShieldHalved size={13} />
          {t(
            "También se bloquean nuevas operaciones al perder 2% diario, 5% semanal o alcanzar 10% de caída desde el máximo. Siempre aplica el límite más estricto. Una diferencia con los saldos del exchange requiere revisión; no se reinician las pérdidas.",
          )}
        </li>
      </ul>
      {role === "ADMIN" && (
        <form className="connection-form" onSubmit={submit}>
          <label>
            {t("Cuenta real")}
            <select
              aria-label={t("Cuenta real")}
              required
              value={connectionId}
              onChange={(event) => setConnectionId(event.target.value)}
            >
              <option value="">
                {t("Selecciona una conexión de trading")}
              </option>
              {candidates.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.label} · {liveVenueLabel(row.provider.toLowerCase())}
                </option>
              ))}
            </select>
          </label>
          {equity > 0 && (
            <div className="limits-suggestion">
              <p className="muted" style={{ margin: 0 }}>
                {t(
                  "Valor de tu cuenta: {{equity}}. La recomendación usa casi todo el saldo (deja 3% para comisiones), reparte cada compra en un tercio y corta el día al perder 2%.",
                  { equity: formatMoney(String(equity), currency) },
                )}
              </p>
              <button
                type="button"
                className="secondary-button"
                onClick={applyRecommendation}
              >
                {t("Usar recomendación según mi saldo")}
              </button>
            </div>
          )}
          <label>
            {t("Máximo por operación ({{currency}})", { currency })}
            <input
              type="number"
              min="0.01"
              max="100000"
              step="0.01"
              required
              value={orderLimit}
              onChange={(event) => setOrderLimit(event.target.value)}
            />
          </label>
          <label>
            {t("Pérdida diaria máxima ({{currency}})", { currency })}
            <input
              type="number"
              min="0.01"
              max="100000"
              step="0.01"
              required
              value={dailyLoss}
              onChange={(event) => setDailyLoss(event.target.value)}
            />
          </label>
          <label>
            {t("Exposición total máxima ({{currency}})", { currency })}
            <input
              type="number"
              min="0.01"
              max="1000000"
              step="0.01"
              required
              value={totalLimit}
              onChange={(event) => setTotalLimit(event.target.value)}
            />
          </label>
          <label>
            {t("Cambio de precio máximo (%)")}
            <input
              type="number"
              min="0.01"
              max="2"
              step="0.01"
              required
              value={slippage}
              onChange={(event) => setSlippage(event.target.value)}
            />
          </label>
          <div className="form-actions">
          <button
            className="danger-button button-lg"
            disabled={
              configure.isPending || !live.data?.capable
            }
          >
            {t(
              live.data?.enabled
                ? "Guardar límites"
                : "Verificar cuenta y activar LIVE",
            )}
          </button>
          {live.data?.configured && (
            <button
              type="button"
              className="secondary-button danger-outline button-lg"
              disabled={configure.isPending}
              onClick={() =>
                configure.mutate({
                  connection_id: connectionId,
                  enabled: false,
                  max_order_usd: orderLimit,
                  max_daily_loss_usd: dailyLoss,
                  max_total_usd: totalLimit,
                  slippage_pct: String(Number(slippage) / 100),
                })
              }
            >
              {t("Desactivar operaciones reales")}
            </button>
          )}
          </div>
        </form>
      )}
      {candidates.length === 0 && (
        <p>
          {t(
            "Primero agrega en Conexiones una clave API de Binance con permisos de consulta y trading spot. Nunca habilites retiros ni transferencias.",
          )}
        </p>
      )}
      {formError && (
        <p className="error" role="alert">
          {t(formError)}
        </p>
      )}
      {configure.isError && (
        <p className="error" role="alert">
          {t(configure.error.message)}
        </p>
      )}
      {live.isError && (
        <p className="error" role="alert">
          {t("No se pudo consultar el estado de la cuenta real.")}
        </p>
      )}
    </article>
  );
}

export function LivePortfolioPanel() {
  const { t } = useTranslation();
  const { live } = useLiveTrading();
  if (live.isPending)
    return (
      <article className="panel">
        <p>{t("Cargando cuenta real…")}</p>
      </article>
    );
  if (live.isError)
    return (
      <article className="panel">
        <p className="error">{t("No se pudo consultar la cuenta real.")}</p>
      </article>
    );
  if (!live.data?.configured)
    return (
      <article className="panel">
        <h2>{t("Cuenta real")}</h2>
        <p>
          {t(
            "Conecta tu exchange y configura los límites LIVE en Configuración.",
          )}
        </p>
      </article>
    );
  const cash = live.data.cash_currency ?? "USD";
  const held = live.data.balances.filter((row) => row.asset !== cash && Number(row.amount) > 0);
  const cashRow = live.data.balances.find((row) => row.asset === cash);
  return (
    <article className="panel wide-panel">
      <div className="live-account-head">
        <div>
          <h2>{t("Cuenta real {{venue}}", { venue: liveVenueLabel(live.data.venue) })}</h2>
          <p className="muted" style={{ margin: 0 }}>
            {t(
              "Los saldos iniciales vienen del exchange. Su coste de compra histórico no se conoce; no se inventan ganancias sobre esas posiciones.",
            )}
          </p>
        </div>
        <span className={`badge ${live.data.state === "READY" ? "positive live" : "warning"}`}>
          LIVE · {live.data.state}
        </span>
      </div>
      <div className="kpi-row">
        <div className="kpi">
          <small>{t("Valor verificado")}</small>
          <strong>
            {live.data.equity_usd ?? "—"} {cash}
          </strong>
        </div>
        <div className="kpi">
          <small>{t("Efectivo disponible")}</small>
          <strong>{formatMoney(cashRow?.amount, cash)}</strong>
        </div>
        <div className="kpi">
          <small>{t("Posiciones abiertas")}</small>
          <strong>{held.length}</strong>
        </div>
        <div className="kpi">
          <small>{t("Última verificación")}</small>
          <strong style={{ fontSize: 15 }}>
            {live.data.as_of ? formatRelative(live.data.as_of) : "—"}
          </strong>
        </div>
      </div>
      {live.data.reason && <p className="muted">{t(live.data.reason)}</p>}
      <h3>{t("Saldos")}</h3>
      <div className="markets-table-wrap">
        <table className="markets-table">
          <thead>
            <tr>
              <th>{t("Activo")}</th>
              <th className="num">{t("Cantidad")}</th>
            </tr>
          </thead>
          <tbody>
            {live.data.balances.map((row) => (
              <tr key={row.asset}>
                <td>
                  <span className="asset-cell">
                    <span className="asset-icon">{row.asset.slice(0, 4)}</span>
                    {row.asset}
                  </span>
                </td>
                <td className="num">{formatNumber(row.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3>{t("Órdenes reales")}</h3>
      {live.data.orders.length === 0 ? (
        <p className="muted">{t("Todavía no hay órdenes reales.")}</p>
      ) : (
        <div className="markets-table-wrap">
          <table className="markets-table">
            <thead>
              <tr>
                <th>{t("Activo")}</th>
                <th>{t("Acción")}</th>
                <th className="num">{t("Cantidad")}</th>
                <th className="num">{t("Precio límite")}</th>
                <th className="num">{t("Llenado confirmado")}</th>
                <th>{t("Estado")}</th>
                <th>{t("Fecha")}</th>
              </tr>
            </thead>
            <tbody>
              {live.data.orders.map((row) => (
                <tr key={row.id}>
                  <td>{row.pair}</td>
                  <td>
                    <span className={`badge plain ${row.side === "BUY" ? "positive" : "danger"}`}>
                      {row.side === "BUY" ? t("Compra") : t("Venta")}
                    </span>
                  </td>
                  <td className="num">{formatNumber(row.quantity)}</td>
                  <td className="num">{formatNumber(row.limit_price)}</td>
                  <td className="num">{formatNumber(row.filled_quantity)}</td>
                  <td>
                    <span
                      className={`badge ${
                        row.status === "FILLED"
                          ? "positive"
                          : ["REJECTED", "CANCELED", "CANCELLED", "EXPIRED"].includes(row.status)
                            ? "danger"
                            : "warning"
                      }`}
                    >
                      {row.status}
                    </span>
                  </td>
                  <td>{formatDateTime(row.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}
