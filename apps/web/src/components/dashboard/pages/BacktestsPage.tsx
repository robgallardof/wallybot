import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import i18n from "../../../lib/i18n";
import type { backtestHistorySchema, backtestRunSchema } from "../../../lib/dto";
import type { RunBacktestInput } from "../../../hooks/useBacktestsData";
import { ApiError } from "../../../lib/api-client";

function toIsoOrEmpty(localValue: string): string {
  if (!localValue) return "";
  const date = new Date(localValue);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString();
}

export function BacktestsPage({
  history,
  run,
}: {
  history: UseQueryResult<z.infer<typeof backtestHistorySchema>>;
  run: UseMutationResult<z.infer<typeof backtestRunSchema>, Error, RunBacktestInput>;
}) {
  useTranslation();
  const [base, setBase] = useState("XBT");
  const [quote, setQuote] = useState("USD");
  const [timeframe, setTimeframe] = useState("1h");
  const [windowStart, setWindowStart] = useState("");
  const [windowEnd, setWindowEnd] = useState("");
  const [featureWindow, setFeatureWindow] = useState("20");
  const [riskOffThreshold, setRiskOffThreshold] = useState("0.5");
  const [startingEquity, setStartingEquity] = useState("10000");
  const [allocationPct, setAllocationPct] = useState("0.1");
  const [feeRate, setFeeRate] = useState("0.001");
  const [slippagePct, setSlippagePct] = useState("0.0005");
  const [bootstrap, setBootstrap] = useState(false);
  const [bootstrapSeed, setBootstrapSeed] = useState("42");

  function submit(event: React.FormEvent) {
    event.preventDefault();
    run.mutate({
      instrument_base: base.trim().toUpperCase(),
      instrument_quote: quote.trim().toUpperCase(),
      timeframe,
      window_start: toIsoOrEmpty(windowStart),
      window_end: toIsoOrEmpty(windowEnd),
      feature_window: Number(featureWindow),
      risk_off_threshold: riskOffThreshold,
      starting_equity: startingEquity,
      allocation_pct: allocationPct,
      fee_rate: feeRate,
      slippage_pct: slippagePct,
      bootstrap_seed: bootstrap ? Number(bootstrapSeed) : null,
    });
  }

  const rows = history.data?.rows ?? [];
  const result = run.data;

  return (
    <div className="backtests-stack">
      <article className="panel wide-panel">
        <div className="panel-heading">
          <h2>{i18n.t("Ejecutar un backtest")}</h2>
        </div>
        <p className="muted">
          {i18n.t(
            "Reproduce la estrategia trend-following sobre datos históricos ya almacenados. Requiere que ese instrumento y ventana ya tengan datos guardados en Parquet.",
          )}
        </p>
        <p className="footnote">
          {i18n.t(
            "Resultado de una simulación histórica, nunca una orden real ni una recomendación de inversión.",
          )}
        </p>
        <form className="backtest-form" onSubmit={submit}>
          <label>
            {i18n.t("Base")}
            <input
              value={base}
              onChange={(event) => setBase(event.target.value)}
              placeholder="XBT"
            />
          </label>
          <label>
            {i18n.t("Cotización")}
            <input
              value={quote}
              onChange={(event) => setQuote(event.target.value)}
              placeholder="USD"
            />
          </label>
          <label>
            {i18n.t("Marco temporal")}
            <select
              value={timeframe}
              onChange={(event) => setTimeframe(event.target.value)}
            >
              <option value="1m">1m</option>
              <option value="5m">5m</option>
              <option value="1h">1h</option>
              <option value="1d">1d</option>
            </select>
          </label>
          <label>
            {i18n.t("Desde")}
            <input
              type="datetime-local"
              value={windowStart}
              onChange={(event) => setWindowStart(event.target.value)}
              required
            />
          </label>
          <label>
            {i18n.t("Hasta")}
            <input
              type="datetime-local"
              value={windowEnd}
              onChange={(event) => setWindowEnd(event.target.value)}
              required
            />
          </label>
          <label>
            {i18n.t("Ventana de features")}
            <input
              type="number"
              min={1}
              value={featureWindow}
              onChange={(event) => setFeatureWindow(event.target.value)}
            />
          </label>
          <label>
            {i18n.t("Umbral risk-off")}
            <input
              value={riskOffThreshold}
              onChange={(event) => setRiskOffThreshold(event.target.value)}
            />
          </label>
          <label>
            {i18n.t("Capital inicial")}
            <input
              value={startingEquity}
              onChange={(event) => setStartingEquity(event.target.value)}
            />
          </label>
          <label>
            {i18n.t("% de asignación")}
            <input
              value={allocationPct}
              onChange={(event) => setAllocationPct(event.target.value)}
            />
          </label>
          <label>
            {i18n.t("Comisión")}
            <input value={feeRate} onChange={(event) => setFeeRate(event.target.value)} />
          </label>
          <label>
            {i18n.t("Slippage")}
            <input
              value={slippagePct}
              onChange={(event) => setSlippagePct(event.target.value)}
            />
          </label>
          <label className="backtest-checkbox">
            <input
              type="checkbox"
              checked={bootstrap}
              onChange={(event) => setBootstrap(event.target.checked)}
            />
            {i18n.t("Remuestreo bootstrap")}
          </label>
          {bootstrap && (
            <label>
              {i18n.t("Semilla")}
              <input
                type="number"
                value={bootstrapSeed}
                onChange={(event) => setBootstrapSeed(event.target.value)}
              />
            </label>
          )}
          <button className="button button-primary" type="submit" disabled={run.isPending}>
            {i18n.t(run.isPending ? "Ejecutando…" : "Ejecutar backtest")}
          </button>
        </form>
        {run.isError && (
          <p role="alert" className="error">
            {run.error instanceof ApiError
              ? run.error.message
              : i18n.t("No se pudo ejecutar el backtest.")}
          </p>
        )}
        {result && (
          <div className="backtest-result" role="status">
            <h3>
              {result.instrument_base}/{result.instrument_quote} · {result.timeframe}
            </h3>
            <dl className="backtest-result-grid">
              <div>
                <dt>{i18n.t("Operaciones")}</dt>
                <dd>{result.trade_count}</dd>
              </div>
              <div>
                <dt>{i18n.t("Capital final")}</dt>
                <dd>{Number(result.final_equity).toFixed(2)}</dd>
              </div>
              <div>
                <dt>{i18n.t("Retorno total")}</dt>
                <dd>{(Number(result.total_return_pct) * 100).toFixed(2)}%</dd>
              </div>
              <div>
                <dt>{i18n.t("Máximo drawdown")}</dt>
                <dd>{(Number(result.max_drawdown_pct) * 100).toFixed(2)}%</dd>
              </div>
              <div>
                <dt>{i18n.t("Tasa de acierto")}</dt>
                <dd>
                  {result.win_rate !== null
                    ? `${(Number(result.win_rate) * 100).toFixed(0)}%`
                    : "—"}
                </dd>
              </div>
            </dl>
            {result.bootstrap && (
              <p className="muted">
                {i18n.t(
                  "Bootstrap ({{samples}} muestras): PnL medio {{mean}}, probabilidad de pérdida {{loss}}%",
                  {
                    samples: result.bootstrap.sample_count,
                    mean: Number(result.bootstrap.mean_total_pnl).toFixed(2),
                    loss: (Number(result.bootstrap.probability_of_loss) * 100).toFixed(0),
                  },
                )}
              </p>
            )}
          </div>
        )}
      </article>

      <article className="panel wide-panel">
        <div className="panel-heading">
          <h2>{i18n.t("Historial de experimentos")}</h2>
          <button
            className="button button-outline"
            onClick={() => void history.refetch()}
            disabled={history.isFetching}
          >
            {i18n.t(history.isFetching ? "Actualizando…" : "Actualizar")}
          </button>
        </div>
        {history.isPending ? (
          <p className="muted" role="status">
            {i18n.t("Cargando historial de backtests…")}
          </p>
        ) : history.isError && !history.data ? (
          <p role="alert" className="error">
            {i18n.t("No se pudo cargar el historial de backtests.")}
          </p>
        ) : (
          <>
            {history.isError && (
              <p role="alert" className="error">
                {i18n.t(
                  "No se pudo actualizar. Se muestra el último historial recibido; puede estar desactualizado.",
                )}
              </p>
            )}
            {rows.length === 0 ? (
              <p className="muted">
                {i18n.t("Todavía no se ejecutó ningún backtest.")}
              </p>
            ) : (
              <div
                className="markets-table-wrap"
                role="region"
                aria-label={i18n.t("Historial de experimentos")}
                tabIndex={0}
              >
                <table className="markets-table">
                  <thead>
                    <tr>
                      <th scope="col">{i18n.t("Instrumento")}</th>
                      <th scope="col">{i18n.t("Marco temporal")}</th>
                      <th scope="col">{i18n.t("Operaciones")}</th>
                      <th scope="col">{i18n.t("Capital final")}</th>
                      <th scope="col">{i18n.t("Retorno")}</th>
                      <th scope="col">{i18n.t("Drawdown")}</th>
                      <th scope="col">{i18n.t("Ejecutado")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.experiment_id}>
                        <td>
                          <strong>
                            {row.instrument_base}/{row.instrument_quote}
                          </strong>
                          <small>{row.instrument_venue}</small>
                        </td>
                        <td>{row.timeframe}</td>
                        <td>{row.trade_count}</td>
                        <td>{Number(row.final_equity).toFixed(2)}</td>
                        <td>{(Number(row.total_return_pct) * 100).toFixed(2)}%</td>
                        <td>{(Number(row.max_drawdown_pct) * 100).toFixed(2)}%</td>
                        <td>
                          {new Intl.DateTimeFormat(i18n.resolvedLanguage, {
                            dateStyle: "short",
                            timeStyle: "short",
                            timeZone: "UTC",
                          }).format(new Date(row.created_at))}{" "}
                          UTC
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </article>
    </div>
  );
}
