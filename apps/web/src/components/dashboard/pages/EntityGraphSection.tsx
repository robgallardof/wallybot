import { useTranslation } from "react-i18next";
import i18n from "../../../lib/i18n";
import type { entityGraphSchema } from "../../../lib/dto";
import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";

export function EntityGraphSection({
  entityGraph,
}: {
  entityGraph: UseQueryResult<z.infer<typeof entityGraphSchema>>;
}) {
  useTranslation();

  if (entityGraph.isPending) {
    return (
      <p className="muted" role="status">
        {i18n.t("Cargando relaciones de entidades…")}
      </p>
    );
  }
  if (entityGraph.isError && !entityGraph.data) {
    return (
      <div>
        <p role="alert" className="error">
          {i18n.t(
            "No se pudieron cargar las relaciones de entidades. El servicio puede no estar disponible.",
          )}
        </p>
        <button
          className="button button-outline"
          onClick={() => void entityGraph.refetch()}
          disabled={entityGraph.isFetching}
        >
          {i18n.t("Reintentar")}
        </button>
      </div>
    );
  }

  const rows = entityGraph.data?.rows ?? [];

  return (
    <article className="panel wide-panel">
      <div className="panel-heading">
        <h2>{i18n.t("Grafo de correlación de entidades")}</h2>
        <button
          className="button button-outline"
          onClick={() => void entityGraph.refetch()}
          disabled={entityGraph.isFetching}
        >
          {i18n.t(entityGraph.isFetching ? "Actualizando…" : "Actualizar")}
        </button>
      </div>
      <p className="muted">
        {i18n.t(
          "Relaciones tipadas entre wallets, entidades, tokens, eventos y transacciones, cada una con su propia procedencia.",
        )}
      </p>
      {entityGraph.isError && (
        <p role="alert" className="error">
          {i18n.t(
            "No se pudo actualizar. Se muestran los últimos datos recibidos; pueden estar desactualizados.",
          )}
        </p>
      )}
      {rows.length === 0 ? (
        <p className="muted">
          {i18n.t("No hay relaciones registradas todavía.")}
        </p>
      ) : (
        <div
          className="markets-table-wrap"
          role="region"
          aria-label={i18n.t("Grafo de correlación de entidades")}
          tabIndex={0}
        >
          <table className="markets-table">
            <thead>
              <tr>
                <th scope="col">{i18n.t("Origen")}</th>
                <th scope="col">{i18n.t("Relación")}</th>
                <th scope="col">{i18n.t("Destino")}</th>
                <th scope="col">{i18n.t("Fuente")}</th>
                <th scope="col">{i18n.t("Confianza")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <code>
                      {row.source_type}:{row.source_id}
                    </code>
                  </td>
                  <td>{row.relationship_type}</td>
                  <td>
                    <code>
                      {row.target_type}:{row.target_id}
                    </code>
                  </td>
                  <td>{row.attribution_source}</td>
                  <td>{Number(row.attribution_confidence).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}
