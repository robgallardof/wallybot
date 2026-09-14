import { useTranslation } from "react-i18next";
import i18n from "../../../lib/i18n";
import type { walletActivitySchema } from "../../../lib/dto";
import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";

export function WalletActivitySection({
  walletActivity,
}: {
  walletActivity: UseQueryResult<z.infer<typeof walletActivitySchema>>;
}) {
  useTranslation();

  if (walletActivity.isPending) {
    return (
      <p className="muted" role="status">
        {i18n.t("Cargando actividad de wallets…")}
      </p>
    );
  }
  if (walletActivity.isError && !walletActivity.data) {
    return (
      <div>
        <p role="alert" className="error">
          {i18n.t(
            "No se pudo cargar la actividad de wallets. El servicio puede no estar disponible.",
          )}
        </p>
        <button
          className="button button-outline"
          onClick={() => void walletActivity.refetch()}
          disabled={walletActivity.isFetching}
        >
          {i18n.t("Reintentar")}
        </button>
      </div>
    );
  }

  const rows = walletActivity.data?.rows ?? [];

  return (
    <article className="panel wide-panel">
      <div className="panel-heading">
        <h2>{i18n.t("Actividad de wallets")}</h2>
        <button
          className="button button-outline"
          onClick={() => void walletActivity.refetch()}
          disabled={walletActivity.isFetching}
        >
          {i18n.t(walletActivity.isFetching ? "Actualizando…" : "Actualizar")}
        </button>
      </div>
      <p className="muted">
        {i18n.t(
          "Observaciones on-chain normalizadas de wallets monitoreadas. Registra lo que ocurrió, nunca una interpretación de compra o venta.",
        )}
      </p>
      {walletActivity.isError && (
        <p role="alert" className="error">
          {i18n.t(
            "No se pudo actualizar. Se muestran los últimos datos recibidos; pueden estar desactualizados.",
          )}
        </p>
      )}
      {rows.length === 0 ? (
        <p className="muted">
          {i18n.t("No hay actividad de wallets registrada todavía.")}
        </p>
      ) : (
        <div
          className="markets-table-wrap"
          role="region"
          aria-label={i18n.t("Actividad de wallets")}
          tabIndex={0}
        >
          <table className="markets-table">
            <thead>
              <tr>
                <th scope="col">Wallet</th>
                <th scope="col">{i18n.t("Cadena")}</th>
                <th scope="col">Token</th>
                <th scope="col">{i18n.t("Acción")}</th>
                <th scope="col">{i18n.t("Monto")}</th>
                <th scope="col">{i18n.t("Valor (USD)")}</th>
                <th scope="col">{i18n.t("Fuente")}</th>
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
                  <td>{Number(row.amount).toLocaleString()}</td>
                  <td>
                    {row.value_usd !== null
                      ? Number(row.value_usd).toLocaleString()
                      : i18n.t("No disponible")}
                  </td>
                  <td>{row.attribution_source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}
