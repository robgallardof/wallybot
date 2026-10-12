import { useTranslation } from "react-i18next";
import { useState } from "react";
import { FaTriangleExclamation, FaArrowTrendUp } from "react-icons/fa6";
import i18n from "../../../lib/i18n";
import type { marketsSchema } from "../../../lib/dto";
import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import { PageSkeleton } from "../PageSkeleton";
import { useMarketDetail } from "../../../hooks/useMarketDetail";

function CandleChart({ candles }: { candles: Array<{ open: string; high: string; low: string; close: string }> }) {
  const visible = candles.slice(-48);
  const values = visible.flatMap((candle) => [Number(candle.low), Number(candle.high)]);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const range = high - low || 1;
  const y = (value: string) => 176 - ((Number(value) - low) / range) * 160;
  const width = 680 / Math.max(visible.length, 1);
  return (
    <svg className="candle-chart" viewBox="0 0 720 200" role="img" aria-label={i18n.t("Velas recientes") }>
      {visible.map((candle, index) => {
        const x = 20 + index * width + width / 2;
        const rising = Number(candle.close) >= Number(candle.open);
        const top = Math.min(y(candle.open), y(candle.close));
        const body = Math.max(Math.abs(y(candle.open) - y(candle.close)), 2);
        return <g className={rising ? "candle-up" : "candle-down"} key={index}><line x1={x} x2={x} y1={y(candle.high)} y2={y(candle.low)} /><rect x={x - Math.max(width * .27, 1)} y={top} width={Math.max(width * .54, 2)} height={body} rx="1" /></g>;
      })}
    </svg>
  );
}

export function MarketsPage({
  markets,
}: {
  markets: UseQueryResult<z.infer<typeof marketsSchema>>;
}) {
  useTranslation();
  const [search, setSearch] = useState("");
  const [eligibility, setEligibility] = useState("all");
  const [quality, setQuality] = useState("all");
  const [selectedInstrument, setSelectedInstrument] = useState<string | null>(null);
  const detail = useMarketDetail(selectedInstrument);

  if (markets.isPending) {
    return <PageSkeleton rows={4} label={i18n.t("Cargando mercados…")} />;
  }
  if (markets.isError && !markets.data) {
    return (
      <div>
        <p role="alert" className="error">
          {i18n.t(
            "No se pudieron cargar los mercados. El proveedor de datos puede no estar disponible.",
          )}
        </p>
        <button
          className="button button-outline"
          onClick={() => void markets.refetch()}
          disabled={markets.isFetching}
        >
          {i18n.t("Reintentar")}
        </button>
      </div>
    );
  }

  const rows = markets.data?.rows ?? [];
  const query = search.trim().toLowerCase();
  const sorted = rows
    .filter(
      (row) =>
        `${row.base}/${row.quote} ${row.id} ${row.venue}`
          .toLowerCase()
          .includes(query) &&
        (eligibility === "all" ||
          row.eligible === (eligibility === "eligible")) &&
        (quality === "all" || row.quality_status === quality),
    )
    .sort((a, b) => {
      if (a.rank !== null && b.rank !== null) return a.rank - b.rank;
      if (a.rank !== null) return -1;
      if (b.rank !== null) return 1;
      return a.id.localeCompare(b.id);
    });

  return (
    <article className="panel wide-panel">
      <div className="panel-heading">
        <h2>{i18n.t("Mercados descubiertos")}</h2>
        <button
          className="button button-outline"
          onClick={() => void markets.refetch()}
          disabled={markets.isFetching}
        >
          {i18n.t(markets.isFetching ? "Actualizando…" : "Actualizar")}
        </button>
      </div>
      <p className="muted">
        {i18n.t(
          "Datos públicos de Kraken. Sin claves de trading. Los fallos del proveedor se muestran como fallo, nunca como cotización válida.",
        )}
      </p>
      <p className="footnote">
        {i18n.t(
          "Elegible para análisis no significa una recomendación ni una orden de compra.",
        )}
      </p>
      {markets.isError && (
        <p role="alert" className="error">
          {i18n.t(
            "No se pudo actualizar. Se muestran los últimos datos recibidos; pueden estar desactualizados.",
          )}
        </p>
      )}
      <div className="market-filters">
        <label>
          {i18n.t("Buscar mercado")}
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={i18n.t("Par o proveedor")}
          />
        </label>
        <label>
          {i18n.t("Elegibilidad")}
          <select
            aria-label={i18n.t("Elegibilidad")}
            value={eligibility}
            onChange={(event) => setEligibility(event.target.value)}
          >
            <option value="all">{i18n.t("Todos")}</option>
            <option value="eligible">{i18n.t("Elegible")}</option>
            <option value="excluded">{i18n.t("Excluido")}</option>
          </select>
        </label>
        <label>
          {i18n.t("Calidad")}
          <select
            aria-label={i18n.t("Calidad")}
            value={quality}
            onChange={(event) => setQuality(event.target.value)}
          >
            <option value="all">{i18n.t("Todas")}</option>
            <option value="PASS">{i18n.t("OK")}</option>
            <option value="WARNING">{i18n.t("AVISO")}</option>
            <option value="FAILURE">{i18n.t("FALLO")}</option>
          </select>
        </label>
        <button
          className="button button-outline"
          onClick={() => {
            setSearch("");
            setEligibility("all");
            setQuality("all");
          }}
        >
          {i18n.t("Limpiar filtros")}
        </button>
      </div>
      <p className="muted" role="status">
        {i18n.t("Mostrando {{visible}} de {{total}} mercados", {
          visible: sorted.length,
          total: rows.length,
        })}
      </p>
      {rows.length === 0 ? (
        <p className="muted">{i18n.t("No se descubrió ningún instrumento.")}</p>
      ) : sorted.length === 0 ? (
        <p className="muted">
          {i18n.t("Ningún mercado coincide con los filtros.")}
        </p>
      ) : (
        <div
          className="markets-table-wrap"
          role="region"
          aria-label={i18n.t("Mercados descubiertos")}
          tabIndex={0}
        >
          <table className="markets-table">
            <thead>
              <tr>
                <th scope="col">{i18n.t("Rango")}</th>
                <th scope="col">{i18n.t("Instrumento")}</th>
                <th scope="col">{i18n.t("Compra")} (bid)</th>
                <th scope="col">{i18n.t("Venta")} (ask)</th>
                <th scope="col">Spread</th>
                <th scope="col">{i18n.t("Calidad")}</th>
                <th scope="col">{i18n.t("Puntaje")}</th>
                <th scope="col">{i18n.t("Estado")}</th>
                <th scope="col">{i18n.t("Detalles")}</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((row) => (
                <tr
                  key={row.id}
                  className={row.eligible ? "" : "market-row-excluded"}
                >
                  <td>{row.rank ?? "—"}</td>
                  <td>
                    <strong>
                      {row.base}/{row.quote}
                    </strong>
                    <small>{row.venue}</small>
                  </td>
                  <td>{row.bid}</td>
                  <td>{row.ask}</td>
                  <td>{(Number(row.spread_ratio) * 100).toFixed(3)}%</td>
                  <td>
                    <span
                      className={`quality-pill quality-${row.quality_status.toLowerCase()}`}
                    >
                      {row.quality_status === "PASS" && i18n.t("OK")}
                      {row.quality_status === "WARNING" && i18n.t("AVISO")}
                      {row.quality_status === "FAILURE" && i18n.t("FALLO")}
                    </span>
                    {row.quality_reasons.length > 0 && (
                      <small
                        className="muted"
                        title={row.quality_reasons.join("; ")}
                      >
                        {row.quality_reasons.length} {i18n.t("motivo(s)")}
                      </small>
                    )}
                  </td>
                  <td>
                    {row.score !== null ? Number(row.score).toFixed(4) : "—"}
                  </td>
                  <td>
                    {row.eligible ? (
                      <span className="service-status good">
                        <FaArrowTrendUp size={13} /> {i18n.t("Elegible")}
                      </span>
                    ) : (
                      <span
                        className="service-status"
                        title={row.rejection_reasons.join("; ")}
                      >
                        <FaTriangleExclamation size={13} /> {i18n.t("Excluido")}
                      </span>
                    )}
                  </td>
                  <td className="market-details">
                    <button className="button button-outline" onClick={() => setSelectedInstrument(row.id)}>
                      {i18n.t("Ver detalle")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {selectedInstrument && (
        <section className="market-detail-panel" aria-live="polite">
          <div className="panel-heading"><div><p className="eyebrow">{i18n.t("DETALLE DE MERCADO")}</p><h2>{detail.data ? `${detail.data.base}/${detail.data.quote}` : i18n.t("Cargando detalle…")}</h2></div><button className="button button-outline" onClick={() => setSelectedInstrument(null)}>{i18n.t("Cerrar")}</button></div>
          {detail.isError ? <p className="error" role="alert">{i18n.t("No se pudo cargar el detalle de este mercado.")}</p> : detail.isPending ? <PageSkeleton rows={2} label={i18n.t("Cargando detalle…")} /> : detail.data && <><CandleChart candles={detail.data.candles} /><div className="market-detail-stats"><span><small>{i18n.t("Compra")}</small><strong>{detail.data.bid}</strong></span><span><small>{i18n.t("Venta")}</small><strong>{detail.data.ask}</strong></span><span><small>{i18n.t("Volumen reciente")}</small><strong>{detail.data.candles.at(-1)?.volume ?? "—"}</strong></span><span><small>{i18n.t("Calidad")}</small><strong>{detail.data.quality_status}</strong></span></div></>}
        </section>
      )}
      <p className="footnote">
        {i18n.t("Última actualización")}:{" "}
        {markets.data
          ? new Intl.DateTimeFormat(i18n.resolvedLanguage, {
              dateStyle: "short",
              timeStyle: "medium",
              timeZone: "UTC",
            }).format(new Date(markets.data.as_of))
          : "—"}{" "}
        UTC
      </p>
    </article>
  );
}
