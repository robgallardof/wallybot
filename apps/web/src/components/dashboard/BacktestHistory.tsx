import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import type { backtestHistorySchema } from "../../lib/dto";

export function BacktestHistory({
  history,
}: {
  history: UseQueryResult<z.infer<typeof backtestHistorySchema>>;
}) {
  const { t, i18n } = useTranslation();
  const [search, setSearch] = useState("");
  const [timeframe, setTimeframe] = useState("all");
  const [order, setOrder] = useState("newest");
  const rows = history.data?.rows ?? [];
  const query = search.trim().toLocaleLowerCase();
  const visible = rows
    .filter(
      (row) =>
        (timeframe === "all" || row.timeframe === timeframe) &&
        `${row.instrument_base}/${row.instrument_quote} ${row.instrument_venue} ${row.strategy_id} ${row.experiment_id}`
          .toLocaleLowerCase()
          .includes(query),
    )
    .sort(
      (a, b) =>
        (order === "newest" ? -1 : 1) *
        (Date.parse(a.created_at) - Date.parse(b.created_at)),
    );
  const date = (value: string) =>
    new Intl.DateTimeFormat(i18n.resolvedLanguage, {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "UTC",
    }).format(new Date(value));

  function reset() {
    setSearch("");
    setTimeframe("all");
    setOrder("newest");
  }

  return (
    <article className="panel wide-panel backtest-history">
      <div className="panel-heading">
        <div>
          <h2>{t("Historial de experimentos")}</h2>
          <p>
            {t(
              "Busca entre los experimentos recibidos y consulta el período de cada simulación.",
            )}
          </p>
        </div>
        <button
          className="button button-outline"
          onClick={() => void history.refetch()}
          disabled={history.isFetching}
        >
          {t(history.isFetching ? "Actualizando…" : "Actualizar")}
        </button>
      </div>
      {history.isPending ? (
        <p className="muted" role="status">
          {t("Cargando historial de backtests…")}
        </p>
      ) : (
        <>
          {history.isError && (
            <p role="alert" className="error">
              {t(
                history.data
                  ? "No se pudo actualizar. Se muestra el último historial recibido; puede estar desactualizado."
                  : "No se pudo cargar el historial de backtests.",
              )}
            </p>
          )}
          {history.data &&
            (rows.length === 0 ? (
              <p className="muted">
                {t("Todavía no se ejecutó ningún backtest.")}
              </p>
            ) : (
              <>
                <div
                  className="activity-filters"
                  role="search"
                  aria-label={t("Filtrar experimentos")}
                >
                  <label>
                    {t("Buscar experimentos")}
                    <input
                      type="search"
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                      placeholder={t("Instrumento, estrategia o identificador")}
                    />
                  </label>
                  <label>
                    {t("Marco temporal del historial")}
                    <select
                      value={timeframe}
                      onChange={(event) => setTimeframe(event.target.value)}
                    >
                      <option value="all">
                        {t("Todos los marcos temporales")}
                      </option>
                      {[...new Set(rows.map((row) => row.timeframe))]
                        .sort()
                        .map((value) => (
                          <option key={value} value={value}>
                            {value}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label>
                    {t("Orden del historial")}
                    <select
                      value={order}
                      onChange={(event) => setOrder(event.target.value)}
                    >
                      <option value="newest">
                        {t("Más recientes primero")}
                      </option>
                      <option value="oldest">
                        {t("Más antiguos primero")}
                      </option>
                    </select>
                  </label>
                </div>
                <p role="status" className="muted">
                  {t("{{shown}} de {{total}} experimentos", {
                    shown: visible.length,
                    total: rows.length,
                  })}
                </p>
                {visible.length === 0 ? (
                  <div className="activity-empty">
                    <h3>{t("No hay experimentos que coincidan")}</h3>
                    <button className="button button-outline" onClick={reset}>
                      {t("Limpiar filtros")}
                    </button>
                  </div>
                ) : (
                  <div
                    className="markets-table-wrap"
                    role="region"
                    aria-label={t("Historial de experimentos")}
                    tabIndex={0}
                  >
                    <table className="markets-table">
                      <thead>
                        <tr>
                          {[
                            "Instrumento",
                            "Marco temporal",
                            "Operaciones",
                            "Capital final",
                            "Retorno",
                            "Drawdown",
                            "Ejecutado",
                            "Detalles",
                          ].map((heading) => (
                            <th key={heading} scope="col">
                              {t(heading)}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {visible.map((row) => (
                          <tr key={row.experiment_id}>
                            <th scope="row">
                              <strong>
                                {row.instrument_base}/{row.instrument_quote}
                              </strong>
                              <small>{row.instrument_venue}</small>
                            </th>
                            <td>{row.timeframe}</td>
                            <td>{row.trade_count}</td>
                            <td>
                              {row.final_equity} {row.instrument_quote}
                            </td>
                            <td>
                              {(Number(row.total_return_pct) * 100).toFixed(2)}%
                            </td>
                            <td>
                              {(Number(row.max_drawdown_pct) * 100).toFixed(2)}%
                            </td>
                            <td>
                              <time dateTime={row.created_at}>
                                {date(row.created_at)} UTC
                              </time>
                            </td>
                            <td>
                              <details className="experiment-details">
                                <summary
                                  aria-label={t(
                                    "Detalles de {{instrument}} · {{id}}",
                                    {
                                      instrument: `${row.instrument_base}/${row.instrument_quote}`,
                                      id: row.experiment_id,
                                    },
                                  )}
                                >
                                  {t("Ver detalles")}
                                </summary>
                                <dl>
                                  <dt>{t("Identificador del experimento")}</dt>
                                  <dd>
                                    <code>{row.experiment_id}</code>
                                  </dd>
                                  <dt>{t("Estrategia")}</dt>
                                  <dd>
                                    <code>{row.strategy_id}</code>
                                  </dd>
                                  <dt>{t("Período analizado (UTC)")}</dt>
                                  <dd>
                                    <time dateTime={row.window_start}>
                                      {date(row.window_start)}
                                    </time>{" "}
                                    —{" "}
                                    <time dateTime={row.window_end}>
                                      {date(row.window_end)}
                                    </time>
                                  </dd>
                                  <dt>{t("Capital inicial")}</dt>
                                  <dd>
                                    {row.starting_equity} {row.instrument_quote}
                                  </dd>
                                  <dt>{t("Tasa de acierto")}</dt>
                                  <dd>
                                    {row.win_rate === null
                                      ? t("No disponible")
                                      : `${(Number(row.win_rate) * 100).toFixed(0)}%`}
                                  </dd>
                                </dl>
                              </details>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            ))}
        </>
      )}
    </article>
  );
}
