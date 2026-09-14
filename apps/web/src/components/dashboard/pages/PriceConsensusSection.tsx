import { useTranslation } from "react-i18next";
import i18n from "../../../lib/i18n";
import type { priceConsensusSchema } from "../../../lib/dto";
import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";

export function PriceConsensusSection({
  priceConsensus,
}: {
  priceConsensus: UseQueryResult<z.infer<typeof priceConsensusSchema>>;
}) {
  useTranslation();

  if (priceConsensus.isPending) {
    return (
      <p className="muted" role="status">
        {i18n.t("Cargando consenso de precios…")}
      </p>
    );
  }
  if (priceConsensus.isError && !priceConsensus.data) {
    return (
      <div>
        <p role="alert" className="error">
          {i18n.t(
            "No se pudo cargar el consenso de precios. El servicio puede no estar disponible.",
          )}
        </p>
        <button
          className="button button-outline"
          onClick={() => void priceConsensus.refetch()}
          disabled={priceConsensus.isFetching}
        >
          {i18n.t("Reintentar")}
        </button>
      </div>
    );
  }

  const rows = priceConsensus.data?.rows ?? [];

  return (
    <article className="panel wide-panel">
      <div className="panel-heading">
        <h2>{i18n.t("Consenso de precios")}</h2>
        <button
          className="button button-outline"
          onClick={() => void priceConsensus.refetch()}
          disabled={priceConsensus.isFetching}
        >
          {i18n.t(priceConsensus.isFetching ? "Actualizando…" : "Actualizar")}
        </button>
      </div>
      <p className="muted">
        {i18n.t(
          "Precio de consenso entre proveedores independientes; una cotización obsoleta o atípica se excluye antes de calcular.",
        )}
      </p>
      {priceConsensus.isError && (
        <p role="alert" className="error">
          {i18n.t(
            "No se pudo actualizar. Se muestran los últimos datos recibidos; pueden estar desactualizados.",
          )}
        </p>
      )}
      {rows.length === 0 ? (
        <p className="muted">{i18n.t("No hay consensos calculados todavía.")}</p>
      ) : (
        <div
          className="markets-table-wrap"
          role="region"
          aria-label={i18n.t("Consenso de precios")}
          tabIndex={0}
        >
          <table className="markets-table">
            <thead>
              <tr>
                <th scope="col">{i18n.t("Instrumento")}</th>
                <th scope="col">{i18n.t("Estado")}</th>
                <th scope="col">{i18n.t("Precio de consenso")}</th>
                <th scope="col">{i18n.t("Fuentes incluidas")}</th>
                <th scope="col">{i18n.t("Detalles")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.instrument_id}>
                  <td>
                    <code>{row.instrument_id}</code>
                  </td>
                  <td>
                    <span
                      className={`quality-pill quality-${row.status === "CONSENSUS" ? "pass" : "warning"}`}
                    >
                      {row.status === "CONSENSUS"
                        ? i18n.t("Consenso")
                        : i18n.t("Datos insuficientes")}
                    </span>
                  </td>
                  <td>{row.consensus_price !== null ? row.consensus_price : "—"}</td>
                  <td>{row.included_sources.join(", ") || "—"}</td>
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
