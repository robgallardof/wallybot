import { useTranslation } from "react-i18next";
import { AlertTriangle, TrendingUp } from "lucide-react";
import i18n from "../../../lib/i18n";
import type { marketsSchema } from "../../../lib/dto";
import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";

export function MarketsPage({
  markets,
}: {
  markets: UseQueryResult<z.infer<typeof marketsSchema>>;
}) {
  useTranslation();

  if (markets.isPending) {
    return <p className="muted">{i18n.t("Cargando mercados…")}</p>;
  }
  if (markets.isError) {
    return (
      <p role="alert" className="error">
        {i18n.t(
          "No se pudieron cargar los mercados. El proveedor de datos puede no estar disponible.",
        )}
      </p>
    );
  }

  const rows = markets.data?.rows ?? [];
  const sorted = [...rows].sort((a, b) => {
    if (a.rank !== null && b.rank !== null) return a.rank - b.rank;
    if (a.rank !== null) return -1;
    if (b.rank !== null) return 1;
    return a.id.localeCompare(b.id);
  });

  return (
    <article className="panel wide-panel">
      <div className="panel-heading">
        <h2>{i18n.t("Mercados descubiertos")}</h2>
        <span className="subtle-pill">{i18n.t("ACTUALIZACIÓN CADA 30 S")}</span>
      </div>
      <p className="muted">
        {i18n.t(
          "Datos públicos de Kraken. Sin claves de trading. Los fallos del proveedor se muestran como fallo, nunca como cotización válida.",
        )}
      </p>
      {rows.length === 0 ? (
        <p className="muted">{i18n.t("No se descubrió ningún instrumento.")}</p>
      ) : (
        <div className="markets-table-wrap">
          <table className="markets-table">
            <thead>
              <tr>
                <th scope="col">{i18n.t("Rango")}</th>
                <th scope="col">{i18n.t("Instrumento")}</th>
                <th scope="col">{i18n.t("Compra")}</th>
                <th scope="col">{i18n.t("Venta")}</th>
                <th scope="col">Spread</th>
                <th scope="col">{i18n.t("Calidad")}</th>
                <th scope="col">{i18n.t("Puntaje")}</th>
                <th scope="col">{i18n.t("Estado")}</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((row) => (
                <tr key={row.id} className={row.eligible ? "" : "market-row-excluded"}>
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
                  <td>{row.score !== null ? Number(row.score).toFixed(4) : "—"}</td>
                  <td>
                    {row.eligible ? (
                      <span className="service-status good">
                        <TrendingUp size={14} /> {i18n.t("Elegible")}
                      </span>
                    ) : (
                      <span
                        className="service-status"
                        title={row.rejection_reasons.join("; ")}
                      >
                        <AlertTriangle size={14} /> {i18n.t("Excluido")}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
