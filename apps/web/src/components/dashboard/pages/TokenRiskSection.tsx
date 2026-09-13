import { useTranslation } from "react-i18next";
import i18n from "../../../lib/i18n";
import type { tokenRiskSchema } from "../../../lib/dto";
import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";

export function TokenRiskSection({
  tokenRisk,
}: {
  tokenRisk: UseQueryResult<z.infer<typeof tokenRiskSchema>>;
}) {
  useTranslation();

  if (tokenRisk.isPending) {
    return (
      <p className="muted" role="status">
        {i18n.t("Cargando riesgo de tokens…")}
      </p>
    );
  }
  if (tokenRisk.isError && !tokenRisk.data) {
    return (
      <div>
        <p role="alert" className="error">
          {i18n.t(
            "No se pudo cargar el riesgo de tokens. El servicio puede no estar disponible.",
          )}
        </p>
        <button
          className="button button-outline"
          onClick={() => void tokenRisk.refetch()}
          disabled={tokenRisk.isFetching}
        >
          {i18n.t("Reintentar")}
        </button>
      </div>
    );
  }

  const rows = [...(tokenRisk.data?.rows ?? [])].sort((a, b) => {
    const riskA = a.risk_score !== null ? Number(a.risk_score) : -1;
    const riskB = b.risk_score !== null ? Number(b.risk_score) : -1;
    return riskB - riskA;
  });

  return (
    <article className="panel wide-panel">
      <div className="panel-heading">
        <h2>{i18n.t("Riesgo de tokens")}</h2>
        <button
          className="button button-outline"
          onClick={() => void tokenRisk.refetch()}
          disabled={tokenRisk.isFetching}
        >
          {i18n.t(tokenRisk.isFetching ? "Actualizando…" : "Actualizar")}
        </button>
      </div>
      <p className="muted">
        {i18n.t(
          "Puntaje 0-100: autoridad de acuñación/congelación, liquidez bloqueada, impuestos y honeypot. Mayor puntaje es más riesgo, no una recomendación de inversión.",
        )}
      </p>
      {tokenRisk.isError && (
        <p role="alert" className="error">
          {i18n.t(
            "No se pudo actualizar. Se muestran los últimos datos recibidos; pueden estar desactualizados.",
          )}
        </p>
      )}
      {rows.length === 0 ? (
        <p className="muted">
          {i18n.t("No hay tokens evaluados todavía.")}
        </p>
      ) : (
        <div
          className="markets-table-wrap"
          role="region"
          aria-label={i18n.t("Riesgo de tokens")}
          tabIndex={0}
        >
          <table className="markets-table">
            <thead>
              <tr>
                <th scope="col">Token</th>
                <th scope="col">{i18n.t("Cadena")}</th>
                <th scope="col">{i18n.t("Estado")}</th>
                <th scope="col">{i18n.t("Puntaje de riesgo")}</th>
                <th scope="col">{i18n.t("Detalles")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.chain}:${row.token_id}`}>
                  <td>
                    <code>{row.token_id}</code>
                  </td>
                  <td>{row.chain}</td>
                  <td>
                    <span
                      className={`quality-pill quality-${row.status === "SCORED" ? "pass" : "warning"}`}
                    >
                      {row.status === "SCORED"
                        ? i18n.t("Evaluado")
                        : i18n.t("Datos insuficientes")}
                    </span>
                  </td>
                  <td>
                    {row.risk_score !== null
                      ? Number(row.risk_score).toFixed(0)
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
