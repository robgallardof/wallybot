import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  type LivePosition,
  type PriceHistory,
  useLivePositions,
  useLivePriceHistory,
} from "../../../hooks/useLiveTrading";
import { formatDateTime, formatMoney, formatNumber, formatPercent } from "../../../lib/format";

function heldFor(iso: string): string {
  const days = (Date.now() - Date.parse(iso)) / 86_400_000;
  if (days < 1 / 24) return "< 1 h";
  if (days < 1) return `${Math.floor(days * 24)} h`;
  return `${Math.floor(days)} d`;
}

function tone(value: string | null): string {
  if (value === null) return "";
  return Number(value) >= 0 ? "positive" : "danger";
}

/** Closing-price line since the purchase, with the average entry as a dashed reference. */
function PriceChart({ history, large }: { history: PriceHistory; large: boolean }) {
  const { t } = useTranslation();
  const points = history.points.map((point) => ({ t: Date.parse(point.t), v: Number(point.close) }));
  if (points.length < 2) return <p className="muted">{t("Sin historial de precios suficiente.")}</p>;
  const entry = history.average_price ? Number(history.average_price) : null;
  const since = history.held_since ? Date.parse(history.held_since) : null;
  const values = points.map((point) => point.v).concat(entry === null ? [] : [entry]);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const range = high - low || high || 1;
  const width = 720;
  const height = large ? 240 : 96;
  const pad = 6;
  const first = points[0].t;
  const span = points[points.length - 1].t - first || 1;
  const x = (time: number) => ((time - first) / span) * width;
  const y = (value: number) => pad + (1 - (value - low) / range) * (height - pad * 2);
  const line = points.map((point, index) => `${index ? "L" : "M"}${x(point.t).toFixed(1)},${y(point.v).toFixed(1)}`).join("");
  const last = points[points.length - 1].v;
  const rising = entry === null ? last >= points[0].v : last >= entry;
  return (
    <svg
      className={`position-chart ${rising ? "rising" : "falling"}`}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={t("Precio de {{asset}} desde la compra", { asset: history.asset })}
    >
      <path className="position-chart-area" d={`${line}L${width},${height}L0,${height}Z`} />
      <path className="position-chart-line" d={line} vectorEffect="non-scaling-stroke" />
      {entry !== null && (
        <line className="position-chart-entry" x1="0" x2={width} y1={y(entry)} y2={y(entry)} vectorEffect="non-scaling-stroke" />
      )}
      {since !== null && since >= first && (
        <line className="position-chart-since" x1={x(since)} x2={x(since)} y1="0" y2={height} vectorEffect="non-scaling-stroke" />
      )}
    </svg>
  );
}

function PositionHistory({ asset, large }: { asset: string; large: boolean }) {
  const { t } = useTranslation();
  const history = useLivePriceHistory(asset);
  if (history.isPending) return <div className={`position-chart-placeholder ${large ? "large" : ""}`} />;
  if (history.isError || !history.data) return <p className="muted">{t("No se pudo cargar el historial de precios.")}</p>;
  return <PriceChart history={history.data} large={large} />;
}

function PositionCard({ position, cash }: { position: LivePosition; cash: string }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <article className={`position-card ${open ? "open" : ""}`}>
      <button type="button" className="position-card-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="asset-cell">
          <span className="asset-icon">{position.asset.slice(0, 4)}</span>
          <span>
            <strong>{position.asset}</strong>
            <small className="muted">{formatNumber(position.quantity)}</small>
          </span>
        </span>
        <span className="position-card-value">
          <strong>{formatMoney(position.value, cash)}</strong>
          {position.pnl_pct !== null ? (
            <small className={tone(position.pnl_pct)}>
              {Number(position.pnl_pct) >= 0 ? "+" : ""}
              {formatPercent(Number(position.pnl_pct) / 100, 2)} · {formatMoney(position.pnl, cash)}
            </small>
          ) : (
            <small className="muted">{t("Precio de compra desconocido")}</small>
          )}
        </span>
      </button>
      <PositionHistory asset={position.asset} large={open} />
      <dl className="position-card-facts">
        <div>
          <dt>{t("Precio de compra")}</dt>
          <dd>{position.average_price ? formatNumber(position.average_price) : "—"}</dd>
        </div>
        <div>
          <dt>{t("Precio actual")}</dt>
          <dd>{formatNumber(position.price)}</dd>
        </div>
        <div>
          <dt>{t("En cartera")}</dt>
          <dd title={formatDateTime(position.held_since)}>{position.held_since ? heldFor(position.held_since) : "—"}</dd>
        </div>
      </dl>
      {open && position.held_since && (
        <p className="muted position-card-note">
          {t("Comprado desde {{date}}. La línea punteada es tu precio medio de compra.", {
            date: formatDateTime(position.held_since),
          })}
        </p>
      )}
    </article>
  );
}

/** One card per coin held in the real account: entry, current value, result and price chart. */
export function LivePositionsSection() {
  const { t } = useTranslation();
  const positions = useLivePositions();
  if (positions.isPending || positions.isError || !positions.data?.positions.length) return null;
  const cash = positions.data.cash_currency ?? "USDT";
  const known = positions.data.positions.filter((row) => row.pnl !== null);
  const invested = known.reduce((sum, row) => sum + Number(row.average_price) * Number(row.quantity), 0);
  const result = known.reduce((sum, row) => sum + Number(row.pnl), 0);
  return (
    <section className="live-positions">
      <div className="panel-heading">
        <h3>{t("Tus monedas")}</h3>
        {known.length > 0 && (
          <span className={`badge plain ${result >= 0 ? "positive" : "danger"}`}>
            {result >= 0 ? "+" : ""}
            {formatMoney(result, cash)} ({formatPercent(invested ? result / invested : 0, 2)})
          </span>
        )}
      </div>
      <div className="position-grid">
        {positions.data.positions.map((position) => (
          <PositionCard key={position.asset} position={position} cash={cash} />
        ))}
      </div>
    </section>
  );
}
