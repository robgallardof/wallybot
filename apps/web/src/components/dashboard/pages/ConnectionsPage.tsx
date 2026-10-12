import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import i18n from "../../../lib/i18n";
import type { providerConnectionListSchema } from "../../../lib/dto";

const PROVIDERS = [
  "BINANCE",
  "BITSO",
  "KRAKEN",
  "COINBASE",
  "WALLET",
  "TIINGO",
] as const;

/**
 * Lets the operator store their own broker/exchange/wallet credentials, read-only or PAPER only
 * -- TRADE_ONLY/LIVE are not offered here (a separate, reviewed capability). Credentials are
 * sent once and never redisplayed; the form always starts blank, and the table only shows
 * whether a connection already has credentials stored (`has_credentials`), never the values.
 */
export function ConnectionsPage({
  connections,
  add,
}: {
  connections: UseQueryResult<z.infer<typeof providerConnectionListSchema>>;
  add: UseMutationResult<
    unknown,
    Error,
    {
      provider: string;
      label: string;
      mode: string;
      api_key?: string;
      api_secret?: string;
    }
  >;
}) {
  useTranslation();
  const [provider, setProvider] =
    useState<(typeof PROVIDERS)[number]>("KRAKEN");
  const [label, setLabel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [trading, setTrading] = useState(false);
  const isWallet = provider === "WALLET";
  // TIINGO takes a single API key, same as a wallet address -- no secret field for either.
  const singleCredential = provider === "WALLET" || provider === "TIINGO";

  function submit(event: React.FormEvent) {
    event.preventDefault();
    add.mutate(
      {
        provider,
        label: label.trim(),
        mode: provider === "KRAKEN" && trading ? "TRADE_ONLY" : "READ_ONLY",
        api_key: apiKey.trim() || undefined,
        api_secret: singleCredential
          ? undefined
          : apiSecret.trim() || undefined,
      },
      {
        onSuccess: () => {
          setLabel("");
          setApiKey("");
          setApiSecret("");
        },
      },
    );
  }

  return (
    <article className="panel wide-panel connections-panel">
      <div className="panel-heading">
        <div>
          <h2>{i18n.t("Conexiones")}</h2>
          <p>{i18n.t("Agrega fuentes de consulta y conserva una vista clara de lo configurado.")}</p>
        </div>
        <span className="subtle-pill">
          {i18n.t("{{count}} registradas", { count: connections.data?.rows.length ?? 0 })}
        </span>
      </div>
      <p className="muted">
        {i18n.t(
          "Conecta tus fuentes o una cuenta Kraken spot con permisos de trading. Las credenciales se cifran y nunca se vuelven a mostrar. Conectar una cuenta no activa operaciones reales.",
        )}
      </p>
      <section className="connection-setup" aria-labelledby="new-connection-title">
        <div className="section-intro">
          <div>
            <span className="eyebrow">{i18n.t("NUEVA CONEXIÓN")}</span>
            <h3 id="new-connection-title">{i18n.t("Elegí un proveedor")}</h3>
          </div>
          <p>{isWallet ? i18n.t("Solo se guarda una dirección pública; nunca una clave privada.") : i18n.t("Para Kraken spot: consulta de fondos, órdenes abiertas/cerradas, crear y cancelar órdenes. Sin permisos de depósito, retiro ni transferencia.")}</p>
        </div>
        <form className="connection-form" onSubmit={submit}>
          <label>
            {i18n.t("Proveedor")}
            <select
              value={provider}
              onChange={(event) =>
                setProvider(event.target.value as (typeof PROVIDERS)[number])
              }
            >
              {PROVIDERS.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          {provider === "KRAKEN" && (
            <label>
              <input type="checkbox" checked={trading} onChange={(event) => setTrading(event.target.checked)} />
              {i18n.t("Conectar cuenta para trading spot real")}
            </label>
          )}
          <label>
            {i18n.t("Nombre")}
            <input
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              required
              maxLength={100}
              placeholder={i18n.t("Ej.: Cuenta de análisis")}
            />
          </label>
          <label>
            {isWallet ? i18n.t("Dirección pública") : i18n.t("Clave API")}
            <input
              type={isWallet ? "text" : "password"}
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              autoComplete="off"
              maxLength={4096}
            />
          </label>
          {!singleCredential && (
            <label>
              {i18n.t("Secreto API")}
              <input
                type="password"
                value={apiSecret}
                onChange={(event) => setApiSecret(event.target.value)}
                autoComplete="off"
                maxLength={4096}
              />
            </label>
          )}
          <button className="button button-primary" disabled={add.isPending}>
            {i18n.t(add.isPending ? "Guardando conexión…" : "Agregar conexión")}
          </button>
        </form>
      </section>
      {add.isError && (
        <p className="error" role="alert">
          {i18n.t(add.error.message)}
        </p>
      )}
      <section className="connection-registry" aria-labelledby="registered-connections-title">
        <div className="section-intro">
          <div>
            <span className="eyebrow">{i18n.t("REGISTRO")}</span>
            <h3 id="registered-connections-title">{i18n.t("Conexiones registradas")}</h3>
          </div>
          <p>{i18n.t("Las credenciales nunca se muestran después de guardarlas.")}</p>
        </div>
      <div className="markets-table-wrap">
        <table className="markets-table">
          <thead>
            <tr>
              <th>{i18n.t("Proveedor")}</th>
              <th>{i18n.t("Nombre")}</th>
              <th>{i18n.t("Modo")}</th>
              <th>{i18n.t("Estado")}</th>
              <th>{i18n.t("Credenciales")}</th>
            </tr>
          </thead>
          <tbody>
            {(connections.data?.rows ?? []).map((row) => (
              <tr key={row.id}>
                <td>{row.provider}</td>
                <td>{row.label}</td>
                <td>{row.mode}</td>
                <td>{row.status}</td>
                <td>
                  {row.has_credentials
                    ? i18n.t("Guardadas")
                    : i18n.t("Sin credenciales")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!connections.isPending && (connections.data?.rows.length ?? 0) === 0 && (
        <p className="connection-empty">{i18n.t("Aún no hay conexiones. Agregá una fuente de lectura para empezar.")}</p>
      )}
      </section>
    </article>
  );
}
