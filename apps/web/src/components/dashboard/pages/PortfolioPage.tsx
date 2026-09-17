import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import { ArrowRight, CircleDollarSign, WalletCards } from "lucide-react";
import type { z } from "zod";
import i18n from "../../../lib/i18n";
import type { portfolioSchema } from "../../../lib/dto";

function displayAmount(amount: string): string {
  const value = Number(amount);
  if (!Number.isFinite(value)) return amount;
  return new Intl.NumberFormat(i18n.resolvedLanguage, {
    maximumFractionDigits: 8,
  }).format(value);
}

export function PortfolioPage({
  portfolio,
  fund,
  navigate,
}: {
  portfolio: UseQueryResult<z.infer<typeof portfolioSchema>>;
  fund: UseMutationResult<z.infer<typeof portfolioSchema>, Error, { amount: string }>;
  navigate: (page: string) => void;
}) {
  useTranslation();
  const [amount, setAmount] = useState("10000");
  const data = portfolio.data;
  const balances = data?.balances ?? [];
  const positions = balances.filter((balance) => balance.purpose === "POSITION");

  function submitFunding(event: React.FormEvent) {
    event.preventDefault();
    fund.mutate({ amount });
  }

  return (
    <div className="portfolio-stack">
      <article className="panel wide-panel portfolio-hero">
        <div className="portfolio-hero-copy">
          <span className="section-kicker">
            <WalletCards size={16} /> {i18n.t("Libro propio · PAPER")}
          </span>
          <h2>{i18n.t("Tu portafolio")}</h2>
          <p className="muted">
            {i18n.t(
              "Saldos y operaciones registrados por tu instancia. No se consultan ni mueven fondos externos desde esta pantalla.",
            )}
          </p>
        </div>
        <div className="portfolio-stats" aria-label={i18n.t("Resumen de portafolio")}>
          <div>
            <small>{i18n.t("Conexiones")}</small>
            <strong>{data?.connection_count ?? "—"}</strong>
          </div>
          <div>
            <small>{i18n.t("Posiciones")}</small>
            <strong>{data ? positions.length : "—"}</strong>
          </div>
          <div>
            <small>{i18n.t("Operaciones")}</small>
            <strong>{data?.activity.length ?? "—"}</strong>
          </div>
        </div>
      </article>

      {portfolio.isPending && <p className="muted">{i18n.t("Cargando portafolio…")}</p>}
      {portfolio.isError && (
        <p className="error" role="alert">
          {i18n.t("No se pudo cargar tu portafolio. Inténtalo de nuevo.")}
        </p>
      )}

      {data && balances.length === 0 && (
        <article className="panel portfolio-empty">
          <CircleDollarSign size={28} />
          <div>
            <h2>{i18n.t("Aún no hay saldos registrados")}</h2>
            <p className="muted">
              {i18n.t(
                "Conectar un proveedor conserva tus credenciales cifradas, pero no importa fondos automáticamente. Cuando una simulación PAPER registre actividad, aparecerá aquí.",
              )}
            </p>
            <form className="settings-form" onSubmit={submitFunding}>
              <label>
                {i18n.t("Efectivo inicial (USD)")}
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                  required
                />
              </label>
              <button className="button button-primary" disabled={fund.isPending}>
                {i18n.t("Fondear cuenta PAPER")}
              </button>
            </form>
            {fund.isError && (
              <p className="error" role="alert">
                {i18n.t(fund.error.message)}
              </p>
            )}
            <button className="button button-secondary" onClick={() => navigate("connections")}>
              {i18n.t("Ver conexiones")} <ArrowRight size={16} />
            </button>
          </div>
        </article>
      )}

      {data && balances.length > 0 && (
        <article className="panel wide-panel">
          <div className="panel-heading">
            <h2>{i18n.t("Saldos registrados")}</h2>
            <span className="subtle-pill">{data.environment}</span>
          </div>
          <div className="markets-table-wrap">
            <table className="markets-table">
              <thead>
                <tr>
                  <th>{i18n.t("Activo")}</th>
                  <th>{i18n.t("Tipo")}</th>
                  <th>{i18n.t("Cantidad")}</th>
                </tr>
              </thead>
              <tbody>
                {balances.map((balance) => (
                  <tr key={`${balance.purpose}-${balance.currency}`}>
                    <td>{balance.currency}</td>
                    <td>{balance.purpose === "CASH" ? i18n.t("Efectivo") : i18n.t("Posición")}</td>
                    <td>{displayAmount(balance.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      )}

      {data && data.activity.length > 0 && (
        <article className="panel wide-panel">
          <div className="panel-heading">
            <h2>{i18n.t("Actividad reciente")}</h2>
          </div>
          <div className="markets-table-wrap">
            <table className="markets-table">
              <thead>
                <tr>
                  <th>{i18n.t("Fecha")}</th>
                  <th>{i18n.t("Mercado")}</th>
                  <th>{i18n.t("Lado")}</th>
                  <th>{i18n.t("Cantidad")}</th>
                  <th>{i18n.t("Precio")}</th>
                </tr>
              </thead>
              <tbody>
                {data.activity.map((activity) => (
                  <tr key={activity.id}>
                    <td>{new Date(activity.occurred_at).toLocaleString(i18n.resolvedLanguage)}</td>
                    <td>{activity.base}/{activity.quote} · {activity.venue}</td>
                    <td>{activity.side}</td>
                    <td>{displayAmount(activity.quantity)}</td>
                    <td>{displayAmount(activity.price)} {activity.quote}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      )}
    </div>
  );
}
