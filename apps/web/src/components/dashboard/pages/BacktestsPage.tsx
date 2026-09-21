import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import i18n from "../../../lib/i18n";
import type {
  backtestHistorySchema,
  backtestRunSchema,
} from "../../../lib/dto";
import type { RunBacktestInput } from "../../../hooks/useBacktestsData";
import { BacktestHistory } from "../BacktestHistory";
import { ApiError } from "../../../lib/api-client";

function toIsoOrEmpty(localValue: string): string {
  if (!localValue) return "";
  const date = new Date(localValue);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString();
}

function toLocalInputValue(date: Date): string {
  const offsetMilliseconds = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offsetMilliseconds).toISOString().slice(0, 16);
}

function suggestedWindow(): { start: string; end: string } {
  const end = new Date();
  end.setMinutes(0, 0, 0);
  const start = new Date(end);
  start.setHours(start.getHours() - 48);
  return { start: toLocalInputValue(start), end: toLocalInputValue(end) };
}

export function BacktestsPage({
  history,
  run,
}: {
  history: UseQueryResult<z.infer<typeof backtestHistorySchema>>;
  run: UseMutationResult<
    z.infer<typeof backtestRunSchema>,
    Error,
    RunBacktestInput
  >;
}) {
  useTranslation();
  const [base, setBase] = useState("XBT");
  const [quote, setQuote] = useState("USD");
  const [timeframe, setTimeframe] = useState("1h");
  const [windowStart, setWindowStart] = useState(() => suggestedWindow().start);
  const [windowEnd, setWindowEnd] = useState(() => suggestedWindow().end);
  const [featureWindow, setFeatureWindow] = useState("20");
  const [riskOffThreshold, setRiskOffThreshold] = useState("0.5");
  const [startingEquity, setStartingEquity] = useState("10000");
  const [allocationPct, setAllocationPct] = useState("0.1");
  const [feeRate, setFeeRate] = useState("0.001");
  const [slippagePct, setSlippagePct] = useState("0.0005");
  const [bootstrap, setBootstrap] = useState(false);
  const [bootstrapSeed, setBootstrapSeed] = useState("42");
  const [walkForward, setWalkForward] = useState(false);
  const [walkForwardWindows, setWalkForwardWindows] = useState("3");
  const [dateError, setDateError] = useState(false);
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const start = toIsoOrEmpty(windowStart);
    const end = toIsoOrEmpty(windowEnd);
    if (!start || !end || start >= end) {
      setDateError(true);
      return;
    }
    setDateError(false);
    run.mutate({
      instrument_base: base.trim().toUpperCase(),
      instrument_quote: quote.trim().toUpperCase(),
      timeframe,
      window_start: start,
      window_end: end,
      feature_window: Number(featureWindow),
      risk_off_threshold: riskOffThreshold,
      starting_equity: startingEquity,
      allocation_pct: allocationPct,
      fee_rate: feeRate,
      slippage_pct: slippagePct,
      bootstrap_seed: bootstrap ? Number(bootstrapSeed) : null,
      walk_forward_windows: walkForward ? Number(walkForwardWindows) : null,
    });
  }

  const result = run.data;

  return (
    <div className="backtests-stack">
      <article className="panel wide-panel">
        <div className="panel-heading">
          <h2>{i18n.t("Ejecutar un backtest")}</h2>
        </div>
        <p className="muted">
          {i18n.t(
            "Reproduce la estrategia trend-following sobre datos históricos ya almacenados. El historial disponible actualmente es de 1 hora; el rango sugerido se completa automáticamente.",
          )}
        </p>
        <p className="footnote">
          {i18n.t(
            "Resultado de una simulación histórica, nunca una orden real ni una recomendación de inversión.",
          )}
        </p>
        <p className="muted" id="backtest-timezone">
          {i18n.t("Fechas en tu zona horaria: {{zone}}. Se envían en UTC.", {
            zone: timeZone,
          })}
        </p>
        {dateError && (
          <p className="error" role="alert" id="backtest-date-error">
            {i18n.t("La fecha final debe ser posterior a la fecha inicial.")}
          </p>
        )}
        <form className="backtest-form" onSubmit={submit}>
          <label>
            {i18n.t("Base")}
            <input
              value={base}
              onChange={(event) => setBase(event.target.value)}
              placeholder="XBT"
              required
              maxLength={16}
              pattern=".*\S.*"
            />
          </label>
          <label>
            {i18n.t("Cotización")}
            <input
              value={quote}
              onChange={(event) => setQuote(event.target.value)}
              placeholder="USD"
              required
              maxLength={16}
              pattern=".*\S.*"
            />
          </label>
          <label>
            {i18n.t("Marco temporal")}
            <select
              value={timeframe}
              onChange={(event) => setTimeframe(event.target.value)}
            >
              <option value="1h">1h</option>
            </select>
          </label>
          <label>
            {i18n.t("Desde")}
            <input
              type="datetime-local"
              value={windowStart}
              onChange={(event) => {
                setWindowStart(event.target.value);
                setDateError(false);
              }}
              aria-invalid={dateError}
              aria-describedby={
                dateError
                  ? "backtest-timezone backtest-date-error"
                  : "backtest-timezone"
              }
              required
            />
          </label>
          <label>
            {i18n.t("Hasta")}
            <input
              type="datetime-local"
              value={windowEnd}
              onChange={(event) => {
                setWindowEnd(event.target.value);
                setDateError(false);
              }}
              aria-invalid={dateError}
              aria-describedby={
                dateError
                  ? "backtest-timezone backtest-date-error"
                  : "backtest-timezone"
              }
              required
            />
          </label>
          <label>
            {i18n.t("Ventana de features")}
            <input
              type="number"
              min={1}
              max={500}
              required
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
            {i18n.t("Asignación (fracción)")}
            <input
              inputMode="decimal"
              aria-describedby="backtest-allocation-help"
              aria-label={i18n.t("Asignación (fracción)")}
              value={allocationPct}
              onChange={(event) => setAllocationPct(event.target.value)}
            />
            <small id="backtest-allocation-help" className="muted">
              {i18n.t(
                "0.1 equivale al 10 %. Usa un valor mayor que 0 y hasta 1.",
              )}
            </small>
          </label>
          <label>
            {i18n.t("Comisión")}
            <input
              inputMode="decimal"
              aria-describedby="backtest-fee-help"
              aria-label={i18n.t("Comisión")}
              value={feeRate}
              onChange={(event) => setFeeRate(event.target.value)}
            />
            <small id="backtest-fee-help" className="muted">
              {i18n.t("Fracción: 0.001 equivale al 0.1 %.")}
            </small>
          </label>
          <label>
            {i18n.t("Slippage")}
            <input
              value={slippagePct}
              inputMode="decimal"
              aria-describedby="backtest-slippage-help"
              aria-label={i18n.t("Slippage")}
              onChange={(event) => setSlippagePct(event.target.value)}
            />
            <small id="backtest-slippage-help" className="muted">
              {i18n.t("Fracción: 0.0005 equivale al 0.05 %.")}
            </small>
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
          <label className="backtest-checkbox">
            <input
              type="checkbox"
              checked={walkForward}
              onChange={(event) => setWalkForward(event.target.checked)}
            />
            {i18n.t("Validación walk-forward")}
          </label>
          {walkForward && (
            <label>
              {i18n.t("Número de ventanas")}
              <input
                type="number"
                min={2}
                max={20}
                value={walkForwardWindows}
                onChange={(event) => setWalkForwardWindows(event.target.value)}
              />
            </label>
          )}
          <button
            className="button button-primary"
            type="submit"
            disabled={run.isPending}
          >
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
              {result.instrument_base}/{result.instrument_quote} ·{" "}
              {result.timeframe}
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
                    loss: (
                      Number(result.bootstrap.probability_of_loss) * 100
                    ).toFixed(0),
                  },
                )}
              </p>
            )}
            {result.walk_forward && (
              <div className="markets-table-wrap">
                <table className="markets-table">
                  <thead>
                    <tr>
                      <th>{i18n.t("Ventana")}</th>
                      <th>{i18n.t("Operaciones")}</th>
                      <th>{i18n.t("Retorno total")}</th>
                      <th>{i18n.t("Máximo drawdown")}</th>
                      <th>{i18n.t("Tasa de acierto")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.walk_forward.map((window) => (
                      <tr key={window.index}>
                        <td>{window.index + 1}</td>
                        <td>{window.trade_count}</td>
                        <td>{(Number(window.total_return_pct) * 100).toFixed(2)}%</td>
                        <td>{(Number(window.max_drawdown_pct) * 100).toFixed(2)}%</td>
                        <td>
                          {window.win_rate !== null
                            ? `${(Number(window.win_rate) * 100).toFixed(0)}%`
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </article>

      <BacktestHistory history={history} />
    </div>
  );
}
