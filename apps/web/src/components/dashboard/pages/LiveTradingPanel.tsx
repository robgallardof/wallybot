import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { liveVenueLabel, useLiveTrading } from "../../../hooks/useLiveTrading";
import { useConnectionsData } from "../../../hooks/useConnectionsData";

export function LiveTradingPanel({ role }: { role: string }) {
  const { t } = useTranslation();
  const { live, configure } = useLiveTrading();
  const { connections } = useConnectionsData(true);
  const [connectionId, setConnectionId] = useState("");
  const [orderLimit, setOrderLimit] = useState("");
  const [dailyLoss, setDailyLoss] = useState("");
  const [totalLimit, setTotalLimit] = useState("");
  const [slippage, setSlippage] = useState("");
  const [confirmation, setConfirmation] = useState("");
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
      { onSuccess: () => setConfirmation("") },
    );
  }
  return (
    <article className="panel wide-panel settings-panel">
      <h2>{t("Operaciones con dinero real")}</h2>
      <p>
        {t(
          "Conecta tu cuenta en Conexiones y define tus límites. Cada propuesta sigue necesitando tu aprobación con MFA. La IA no recibe tus claves.",
        )}
      </p>
      <p>
        <strong>{live.data?.state ?? t("Cargando…")}</strong>{" "}
        {t(live.data?.reason ?? "")}
      </p>
      <p className="muted">
        {t(
          "Binance spot: USDT, BTC y ETH; límites en USDT. Sin deuda ni apalancamiento. Las órdenes usan precio límite y cancelan la cantidad que no se llena inmediatamente. Los stops y objetivos son avisos de revisión.",
        )}
      </p>
      <p className="muted">
        {t(
          "También se bloquean nuevas operaciones al perder 2% diario, 5% semanal o alcanzar 10% de caída desde el máximo. Siempre aplica el límite más estricto. Una diferencia con los saldos del exchange requiere revisión; no se reinician las pérdidas.",
        )}
      </p>
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
          <label>
            {t("Escribe LIVE para activar dinero real")}
            <input
              autoComplete="off"
              required
              pattern="LIVE"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
            />
          </label>
          <button
            className="danger-button"
            disabled={
              configure.isPending ||
              confirmation !== "LIVE" ||
              !live.data?.capable
            }
          >
            {t(
              live.data?.enabled
                ? "Verificar límites y rearmar LIVE"
                : "Verificar cuenta y activar LIVE",
            )}
          </button>
          {live.data?.configured && (
            <button
              type="button"
              className="secondary-button"
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
  const { t, i18n } = useTranslation();
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
  return (
    <article className="panel wide-panel">
      <h2>
        {t("Cuenta real {{venue}}", { venue: liveVenueLabel(live.data.venue) })}
      </h2>
      <p>
        <strong>LIVE · {live.data.state}</strong> {t(live.data.reason)}
      </p>
      <p>
        {t("Valor verificado")}: {live.data.equity_usd ?? "—"}{" "}
        {live.data.cash_currency ?? "USD"} ·{" "}
        {live.data.as_of
          ? new Date(live.data.as_of).toLocaleString(i18n.language)
          : "—"}
      </p>
      <p className="muted">
        {t(
          "Los saldos iniciales vienen del exchange. Su coste de compra histórico no se conoce; no se inventan ganancias sobre esas posiciones.",
        )}
      </p>
      <div className="markets-table-wrap">
        <table className="markets-table">
          <thead>
            <tr>
              <th>{t("Activo")}</th>
              <th>{t("Cantidad")}</th>
            </tr>
          </thead>
          <tbody>
            {live.data.balances.map((row) => (
              <tr key={row.asset}>
                <td>{row.asset}</td>
                <td>{row.amount}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3>{t("Órdenes reales")}</h3>
      <div className="markets-table-wrap">
        <table className="markets-table">
          <thead>
            <tr>
              <th>{t("Activo")}</th>
              <th>{t("Acción")}</th>
              <th>{t("Cantidad")}</th>
              <th>{t("Precio límite")}</th>
              <th>{t("Llenado confirmado")}</th>
              <th>{t("Estado")}</th>
            </tr>
          </thead>
          <tbody>
            {live.data.orders.map((row) => (
              <tr key={row.id}>
                <td>{row.pair}</td>
                <td>{row.side}</td>
                <td>{row.quantity}</td>
                <td>{row.limit_price}</td>
                <td>{row.filled_quantity}</td>
                <td>{row.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
}
