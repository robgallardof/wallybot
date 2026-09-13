import { useTranslation } from "react-i18next";
import i18n from "../../../lib/i18n";
import type { whaleFlowSchema } from "../../../lib/dto";
import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";

export function WhaleFlowSection({
  whaleFlow,
}: {
  whaleFlow: UseQueryResult<z.infer<typeof whaleFlowSchema>>;
}) {
  useTranslation();

  if (whaleFlow.isPending) {
    return (
      <p className="muted" role="status">
        {i18n.t("Cargando transferencias de ballenas…")}
      </p>
    );
  }
  if (whaleFlow.isError && !whaleFlow.data) {
    return (
      <div>
        <p role="alert" className="error">
          {i18n.t(
            "No se pudieron cargar las transferencias de ballenas. El servicio puede no estar disponible.",
          )}
        </p>
        <button
          className="button button-outline"
          onClick={() => void whaleFlow.refetch()}
          disabled={whaleFlow.isFetching}
        >
          {i18n.t("Reintentar")}
        </button>
      </div>
    );
  }

  const rows = whaleFlow.data?.rows ?? [];

  return (
    <article className="panel wide-panel">
      <div className="panel-heading">
        <h2>{i18n.t("Transferencias de ballenas")}</h2>
        <button
          className="button button-outline"
          onClick={() => void whaleFlow.refetch()}
          disabled={whaleFlow.isFetching}
        >
          {i18n.t(whaleFlow.isFetching ? "Actualizando…" : "Actualizar")}
        </button>
      </div>
      <p className="muted">
        {i18n.t(
          "Transferencias on-chain que superan un umbral en USD. Es una señal de magnitud, nunca una interpretación de compra o venta.",
        )}
      </p>
      {whaleFlow.isError && (
        <p role="alert" className="error">
          {i18n.t(
            "No se pudo actualizar. Se muestran los últimos datos recibidos; pueden estar desactualizados.",
          )}
        </p>
      )}
      {rows.length === 0 ? (
        <p className="muted">
          {i18n.t("No se detectaron transferencias de ballenas todavía.")}
        </p>
      ) : (
        <div
          className="markets-table-wrap"
          role="region"
          aria-label={i18n.t("Transferencias de ballenas")}
          tabIndex={0}
        >
          <table className="markets-table">
            <thead>
              <tr>
                <th scope="col">Wallet</th>
                <th scope="col">{i18n.t("Cadena")}</th>
                <th scope="col">Token</th>
                <th scope="col">{i18n.t("Acción")}</th>
                <th scope="col">{i18n.t("Valor (USD)")}</th>
                <th scope="col">{i18n.t("Umbral (USD)")}</th>
                <th scope="col">{i18n.t("Detalles")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${row.wallet_id}-${row.occurred_at}-${index}`}>
                  <td>
                    <code>{row.wallet_id}</code>
                  </td>
                  <td>{row.chain}</td>
                  <td>{row.token}</td>
                  <td>{row.action}</td>
                  <td>{Number(row.value_usd).toLocaleString()}</td>
                  <td>{Number(row.threshold_usd).toLocaleString()}</td>
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
