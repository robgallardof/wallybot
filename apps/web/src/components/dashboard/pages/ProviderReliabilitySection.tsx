import { useTranslation } from "react-i18next";
import i18n from "../../../lib/i18n";
import type { providerReliabilitySchema } from "../../../lib/dto";
import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";

export function ProviderReliabilitySection({
  providerReliability,
}: {
  providerReliability: UseQueryResult<z.infer<typeof providerReliabilitySchema>>;
}) {
  useTranslation();

  if (providerReliability.isPending) {
    return (
      <p className="muted" role="status">
        {i18n.t("Cargando confiabilidad de proveedores…")}
      </p>
    );
  }
  if (providerReliability.isError && !providerReliability.data) {
    return (
      <div>
        <p role="alert" className="error">
          {i18n.t(
            "No se pudo cargar la confiabilidad de proveedores. El servicio puede no estar disponible.",
          )}
        </p>
        <button
          className="button button-outline"
          onClick={() => void providerReliability.refetch()}
          disabled={providerReliability.isFetching}
        >
          {i18n.t("Reintentar")}
        </button>
      </div>
    );
  }

  const rows = providerReliability.data?.rows ?? [];
  const statusClass: Record<string, string> = {
    HEALTHY: "pass",
    DEGRADED: "warning",
    UNRELIABLE: "warning",
    INSUFFICIENT_DATA: "warning",
  };
  const statusLabel: Record<string, string> = {
    HEALTHY: i18n.t("Saludable"),
    DEGRADED: i18n.t("Degradado"),
    UNRELIABLE: i18n.t("No confiable"),
    INSUFFICIENT_DATA: i18n.t("Datos insuficientes"),
  };

  return (
    <article className="panel wide-panel">
      <div className="panel-heading">
        <h2>{i18n.t("Confiabilidad de proveedores")}</h2>
        <button
          className="button button-outline"
          onClick={() => void providerReliability.refetch()}
          disabled={providerReliability.isFetching}
        >
          {i18n.t(providerReliability.isFetching ? "Actualizando…" : "Actualizar")}
        </button>
      </div>
      <p className="muted">
        {i18n.t(
          "Tasa de error, latencia y antigüedad de la última llamada exitosa por proveedor de datos.",
        )}
      </p>
      {providerReliability.isError && (
        <p role="alert" className="error">
          {i18n.t(
            "No se pudo actualizar. Se muestran los últimos datos recibidos; pueden estar desactualizados.",
          )}
        </p>
      )}
      {rows.length === 0 ? (
        <p className="muted">{i18n.t("No hay proveedores evaluados todavía.")}</p>
      ) : (
        <div
          className="markets-table-wrap"
          role="region"
          aria-label={i18n.t("Confiabilidad de proveedores")}
          tabIndex={0}
        >
          <table className="markets-table">
            <thead>
              <tr>
                <th scope="col">{i18n.t("Proveedor")}</th>
                <th scope="col">{i18n.t("Estado")}</th>
                <th scope="col">{i18n.t("Llamadas")}</th>
                <th scope="col">{i18n.t("Tasa de error")}</th>
                <th scope="col">{i18n.t("Latencia (ms)")}</th>
                <th scope="col">{i18n.t("Detalles")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.provider}>
                  <td>{row.provider}</td>
                  <td>
                    <span className={`quality-pill quality-${statusClass[row.status]}`}>
                      {statusLabel[row.status]}
                    </span>
                  </td>
                  <td>{row.call_count}</td>
                  <td>
                    {row.error_rate !== null
                      ? `${(Number(row.error_rate) * 100).toFixed(1)}%`
                      : "—"}
                  </td>
                  <td>
                    {row.average_latency_ms !== null
                      ? Number(row.average_latency_ms).toFixed(0)
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
