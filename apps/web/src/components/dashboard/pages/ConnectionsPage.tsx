import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import i18n from "../../../lib/i18n";
import type { providerConnectionListSchema } from "../../../lib/dto";
import { SettingsSwitch } from "../../ui/SettingsSwitch";
import {
  ConnectionEditor,
  type ConnectionUpdate,
  TRADING_PROVIDERS,
  credentialLabel,
  hasSecret,
} from "./ConnectionEditor";

const PROVIDERS = [
  "BINANCE",
  "BITSO",
  "KRAKEN",
  "COINBASE",
  "WALLET",
  "TIINGO",
] as const;

/**
 * Lets the operator store query credentials or a verified spot trading connection. Credentials are
 * sent once and never redisplayed; the form always starts blank, and the table only shows
 * whether a connection already has credentials stored (`has_credentials`), never the values.
 */
export function ConnectionsPage({
  connections,
  add,
  update,
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
  update: UseMutationResult<unknown, Error, ConnectionUpdate>;
}) {
  useTranslation();
  const [provider, setProvider] =
    useState<(typeof PROVIDERS)[number]>("BINANCE");
  const [label, setLabel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [trading, setTrading] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const isWallet = provider === "WALLET";

  function submit(event: React.FormEvent) {
    event.preventDefault();
    add.mutate(
      {
        provider,
        label: label.trim(),
        mode: TRADING_PROVIDERS.has(provider) && trading ? "TRADE_ONLY" : "READ_ONLY",
        api_key: apiKey.trim() || undefined,
        api_secret: hasSecret(provider) ? apiSecret.trim() || undefined : undefined,
      },
      {
        onSuccess: () => {
          setLabel("");
          setApiKey("");
          setApiSecret("");
          setTrading(false);
        },
      },
    );
  }

  const editingRow = connections.data?.rows.find((row) => row.id === editingId);

  function toggleEditor(id: string) {
    update.reset();
    setEditingId((current) => (current === id ? null : id));
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
          "Conecta tus fuentes o una cuenta spot de Binance con permisos de trading. Las credenciales se cifran y nunca se vuelven a mostrar. Conectar una cuenta no activa operaciones reales.",
        )}
      </p>
      <section className="connection-setup" aria-labelledby="new-connection-title">
        <div className="section-intro">
          <div>
            <span className="eyebrow">{i18n.t("NUEVA CONEXIÓN")}</span>
            <h3 id="new-connection-title">{i18n.t("Elegí un proveedor")}</h3>
          </div>
          <p>
            {isWallet
              ? i18n.t("Solo se guarda una dirección pública; nunca una clave privada.")
              : provider === "BINANCE"
                ? i18n.t(
                    "Para Binance spot: activa solo «Enable Reading» y «Enable Spot & Margin Trading», restringe la clave a la IP pública de esta PC y deja desactivados retiros, transferencias, margen y futuros. No pagues comisiones con BNB.",
                  )
                : provider === "KRAKEN"
                  ? i18n.t(
                      "Para Kraken spot: consulta de fondos, órdenes abiertas/cerradas, crear y cancelar órdenes. Sin permisos de depósito, retiro ni transferencia.",
                    )
                  : i18n.t(
                      "Para otras fuentes, agrega únicamente credenciales de consulta. Vincular una fuente no habilita operaciones.",
                    )}
          </p>
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
          {TRADING_PROVIDERS.has(provider) && (
            <SettingsSwitch
              label={i18n.t("Conectar cuenta para trading spot real")}
              checked={trading}
              onChange={setTrading}
            />
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
            {credentialLabel(provider)}
            <input
              type={isWallet ? "text" : "password"}
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              autoComplete="off"
              maxLength={4096}
            />
          </label>
          {hasSecret(provider) && (
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
              <th>{i18n.t("Acciones")}</th>
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
                <td>
                  <button
                    type="button"
                    className="button"
                    aria-expanded={editingId === row.id}
                    aria-label={i18n.t("Editar {{name}}", { name: row.label })}
                    onClick={() => toggleEditor(row.id)}
                  >
                    {i18n.t(editingId === row.id ? "Cerrar" : "Editar")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editingRow && (
        <section
          className="connection-editor-panel"
          aria-labelledby="edit-connection-title"
          ref={(node) => node?.scrollIntoView({ block: "nearest", behavior: "smooth" })}
        >
          <span className="eyebrow">{i18n.t("EDITAR CONEXIÓN")}</span>
          <h3 id="edit-connection-title">
            {editingRow.provider} · {editingRow.label}
          </h3>
          <ConnectionEditor
            key={editingRow.id}
            row={editingRow}
            update={update}
            onClose={() => setEditingId(null)}
          />
        </section>
      )}
      {!connections.isPending && (connections.data?.rows.length ?? 0) === 0 && (
        <p className="connection-empty">{i18n.t("Aún no hay conexiones. Agregá una fuente de lectura para empezar.")}</p>
      )}
      </section>
    </article>
  );
}
