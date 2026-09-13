import { useTranslation } from "react-i18next";
import i18n from "../../../lib/i18n";
import type { smartMoneySchema } from "../../../lib/dto";
import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";

export function SmartMoneyPage({
  smartMoney,
}: {
  smartMoney: UseQueryResult<z.infer<typeof smartMoneySchema>>;
}) {
  useTranslation();

  if (smartMoney.isPending) {
    return (
      <p className="muted" role="status">
        {i18n.t("Cargando puntajes de Smart Money…")}
      </p>
    );
  }
  if (smartMoney.isError && !smartMoney.data) {
    return (
      <div>
        <p role="alert" className="error">
          {i18n.t(
            "No se pudieron cargar los puntajes de Smart Money. El servicio puede no estar disponible.",
          )}
        </p>
        <button
          className="button button-outline"
          onClick={() => void smartMoney.refetch()}
          disabled={smartMoney.isFetching}
        >
          {i18n.t("Reintentar")}
        </button>
      </div>
    );
  }

  const rows = smartMoney.data?.rows ?? [];
  const sorted = [...rows].sort((a, b) => {
    const scoreA = a.score !== null ? Number(a.score) : -1;
    const scoreB = b.score !== null ? Number(b.score) : -1;
    return scoreB - scoreA;
  });

  return (
    <article className="panel wide-panel">
      <div className="panel-heading">
        <h2>{i18n.t("Wallets Smart Money")}</h2>
        <button
          className="button button-outline"
          onClick={() => void smartMoney.refetch()}
          disabled={smartMoney.isFetching}
        >
          {i18n.t(smartMoney.isFetching ? "Actualizando…" : "Actualizar")}
        </button>
      </div>
      <p className="muted">
        {i18n.t(
          "Puntaje 0-100 a partir de operaciones on-chain observadas: tasa de acierto y PnL realizado. Nunca clasifica una wallet como Smart Money por una sola operación ganadora.",
        )}
      </p>
      <p className="footnote">
        {i18n.t(
          "Señal de observación, no una recomendación de inversión ni una orden de compra.",
        )}
      </p>
      {smartMoney.isError && (
        <p role="alert" className="error">
          {i18n.t(
            "No se pudo actualizar. Se muestran los últimos datos recibidos; pueden estar desactualizados.",
          )}
        </p>
      )}
      {rows.length === 0 ? (
        <p className="muted">
          {i18n.t("No hay wallets monitoreadas con puntaje todavía.")}
        </p>
      ) : (
        <div
          className="markets-table-wrap"
          role="region"
          aria-label={i18n.t("Wallets Smart Money")}
          tabIndex={0}
        >
          <table className="markets-table">
            <thead>
              <tr>
                <th scope="col">Wallet</th>
                <th scope="col">{i18n.t("Estado")}</th>
                <th scope="col">{i18n.t("Puntaje")}</th>
                <th scope="col">{i18n.t("Operaciones")}</th>
                <th scope="col">{i18n.t("Tasa de acierto")}</th>
                <th scope="col">PnL (USD)</th>
                <th scope="col">{i18n.t("Detalles")}</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((row) => (
                <tr key={row.wallet_id}>
                  <td>
                    <code>{row.wallet_id}</code>
                  </td>
                  <td>
                    <span
                      className={`quality-pill quality-${row.status === "SCORED" ? "pass" : "warning"}`}
                    >
                      {row.status === "SCORED"
                        ? i18n.t("Evaluada")
                        : i18n.t("Datos insuficientes")}
                    </span>
                  </td>
                  <td>{row.score !== null ? Number(row.score).toFixed(1) : "—"}</td>
                  <td>{row.trade_count}</td>
                  <td>
                    {row.win_rate !== null
                      ? `${(Number(row.win_rate) * 100).toFixed(0)}%`
                      : "—"}
                  </td>
                  <td>
                    {row.realized_pnl_usd !== null
                      ? Number(row.realized_pnl_usd).toFixed(2)
                      : "—"}
                  </td>
                  <td className="market-details">
                    <details>
                      <summary>{i18n.t("Ver motivos")}</summary>
                      {row.reasons.length ? (
                        <ul>
                          {row.reasons.map((reason) => (
                            <li key={reason}>{reason}</li>
                          ))}
                        </ul>
                      ) : (
                        <p>{i18n.t("Sin motivos informados.")}</p>
                      )}
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}
