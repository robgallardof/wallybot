import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { UseMutationResult } from "@tanstack/react-query";
import type { z } from "zod";
import i18n from "../../../lib/i18n";
import type { providerConnectionListSchema } from "../../../lib/dto";
import { SettingsSwitch } from "../../ui/SettingsSwitch";

type ConnectionRow = z.infer<typeof providerConnectionListSchema>["rows"][number];

export type ConnectionUpdate = {
  id: string;
  label: string;
  mode: string;
  api_key?: string;
  api_secret?: string;
};

// Real spot trading is supported only through these reviewed exchange adapters.
export const TRADING_PROVIDERS = new Set<string>(["KRAKEN", "BINANCE"]);

/** Label for the first credential field: wallets store an address and Tiingo a token. */
export function credentialLabel(provider: string) {
  if (provider === "WALLET") return i18n.t("Dirección pública");
  if (provider === "TIINGO") return i18n.t("Token API");
  return i18n.t("Clave API");
}

export function hasSecret(provider: string) {
  return provider !== "WALLET" && provider !== "TIINGO";
}

/**
 * Inline editor for one stored connection. Credentials are never prefilled: leaving them empty
 * keeps the encrypted ones, and turning trading on re-verifies the key server-side.
 */
export function ConnectionEditor({
  row,
  update,
  onClose,
}: {
  row: ConnectionRow;
  update: UseMutationResult<unknown, Error, ConnectionUpdate>;
  onClose: () => void;
}) {
  useTranslation();
  const [label, setLabel] = useState(row.label);
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [trading, setTrading] = useState(row.mode === "TRADE_ONLY");
  const canTrade = TRADING_PROVIDERS.has(row.provider);
  const isWallet = row.provider === "WALLET";

  function submit(event: React.FormEvent) {
    event.preventDefault();
    update.mutate(
      {
        id: row.id,
        label: label.trim(),
        mode: canTrade && trading ? "TRADE_ONLY" : "READ_ONLY",
        api_key: apiKey.trim() || undefined,
        api_secret: hasSecret(row.provider) ? apiSecret.trim() || undefined : undefined,
      },
      { onSuccess: onClose },
    );
  }

  const keepHint = row.has_credentials
    ? i18n.t("Déjalo vacío para conservar el valor guardado.")
    : undefined;

  return (
    <form
      className="connection-form connection-editor"
      onSubmit={submit}
      aria-label={i18n.t("Editar {{name}}", { name: row.label })}
    >
      <label>
        {i18n.t("Nombre")}
        <input
          value={label}
          onChange={(event) => setLabel(event.target.value)}
          required
          maxLength={100}
        />
      </label>
      <label>
        {credentialLabel(row.provider)}
        <input
          type={isWallet ? "text" : "password"}
          value={apiKey}
          onChange={(event) => setApiKey(event.target.value)}
          autoComplete="off"
          maxLength={4096}
          placeholder={keepHint}
        />
      </label>
      {hasSecret(row.provider) && (
        <label>
          {i18n.t("Secreto API")}
          <input
            type="password"
            value={apiSecret}
            onChange={(event) => setApiSecret(event.target.value)}
            autoComplete="off"
            maxLength={4096}
            placeholder={keepHint}
          />
        </label>
      )}
      {canTrade && (
        <SettingsSwitch
          label={i18n.t("Trading spot real")}
          description={i18n.t(
            "Al activarlo se verifica la clave: permiso de trading spot, sin retiros y saldos legibles. No se pone ninguna orden.",
          )}
          checked={trading}
          onChange={setTrading}
        />
      )}
      {update.isError && (
        <p className="error" role="alert">
          {i18n.t(update.error.message)}
        </p>
      )}
      <div className="connection-editor-actions">
        <button className="button button-primary" disabled={update.isPending}>
          {i18n.t(update.isPending ? "Guardando conexión…" : "Guardar cambios")}
        </button>
        <button type="button" className="button" onClick={onClose} disabled={update.isPending}>
          {i18n.t("Cancelar")}
        </button>
      </div>
    </form>
  );
}
