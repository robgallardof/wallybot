import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { FlaskConical, KeyRound, MessageCircle, Send, ShieldCheck } from "lucide-react";
import i18n from "../../../lib/i18n";
import type {
  dashboardSchema,
  telegramConfigSchema,
  telegramConfirmationListSchema,
  telegramConfirmationSchema,
} from "../../../lib/dto";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import { Button } from "../../ui/button";

const TELEGRAM_ACTION_LABELS: Record<string, string> = {
  PAUSE: "Pausar instancia",
  RESUME: "Reanudar instancia",
};

/**
 * Lets an ADMIN switch the instance between OBSERVE (default: real market data only, no
 * simulated orders) and PAPER (simulated trading against the same real data). This is the one
 * place that toggles `environment` -- every other control surface (RiskPage's pause/resume)
 * must preserve whatever value is already set here, never flip it as a side effect.
 */
export function SettingsPage({
  dashboard,
  change,
  role,
  telegram,
  saveTelegram,
  confirmMfa,
  telegramConfirmations,
  confirmTelegramConfirmation,
}: {
  dashboard: UseQueryResult<z.infer<typeof dashboardSchema>>;
  change: UseMutationResult<
    unknown,
    Error,
    { status: string; environment?: string }
  >;
  role: string;
  telegram: UseQueryResult<z.infer<typeof telegramConfigSchema>>;
  saveTelegram: UseMutationResult<
    unknown,
    Error,
    { bot_token?: string; chat_id?: number | null; enabled: boolean }
  >;
  confirmMfa: UseMutationResult<unknown, Error, { code: string }>;
  telegramConfirmations: UseQueryResult<z.infer<typeof telegramConfirmationListSchema>>;
  confirmTelegramConfirmation: UseMutationResult<
    z.infer<typeof telegramConfirmationSchema>,
    Error,
    string
  >;
}) {
  useTranslation();
  const environment = dashboard.data?.environment;
  const isPaper = environment === "PAPER";
  const [botToken, setBotToken] = useState("");
  const [chatId, setChatId] = useState(
    telegram.data?.chat_id != null ? String(telegram.data.chat_id) : "",
  );
  const [telegramEnabled, setTelegramEnabled] = useState(
    telegram.data?.enabled ?? false,
  );
  const [mfaCode, setMfaCode] = useState("");

  useEffect(() => {
    if (telegram.data) {
      setChatId(
        telegram.data.chat_id != null ? String(telegram.data.chat_id) : "",
      );
      setTelegramEnabled(telegram.data.enabled);
    }
  }, [telegram.data]);

  function submitTelegram(event: React.FormEvent) {
    event.preventDefault();
    saveTelegram.mutate(
      {
        bot_token: botToken.trim() || undefined,
        chat_id: chatId.trim() ? Number(chatId.trim()) : null,
        enabled: telegramEnabled,
      },
      { onSuccess: () => setBotToken("") },
    );
  }

  function submitMfaConfirm(event: React.FormEvent) {
    event.preventDefault();
    confirmMfa.mutate(
      { code: mfaCode.trim() },
      { onSuccess: () => setMfaCode("") },
    );
  }

  return (
    <section className="settings-stack" aria-label={i18n.t("Configuración")}>
      <article className="panel wide-panel settings-panel">
        <div className="settings-heading">
          <span className="settings-heading-icon">
            <FlaskConical size={19} />
          </span>
          <div>
            <p className="eyebrow">{i18n.t("Modo de simulación")}</p>
            <h2>
              {isPaper
                ? i18n.t("Simulación PAPER activada")
                : i18n.t("Observando mercados reales (OBSERVE)")}
            </h2>
          </div>
          <span
            className={isPaper ? "settings-status paper" : "settings-status"}
          >
            <i /> {isPaper ? "PAPER" : "OBSERVE"}
          </span>
        </div>
        <p className="muted settings-description">
          {i18n.t(
            "Por defecto tu instancia solo observa datos reales de mercado: no genera ni simula operaciones. Activa PAPER si querés que el sistema simule órdenes sobre esos mismos datos, sin dinero real ni conexión de ejecución.",
          )}
        </p>
        <div className="settings-action-row">
          <div className="settings-safety">
            <ShieldCheck size={18} />
            <span>
              {i18n.t(
                "PAPER nunca envía órdenes reales ni requiere claves de ejecución. La ejecución real (LIVE) no está disponible en esta fase.",
              )}
            </span>
          </div>
          {role === "ADMIN" ? (
            <Button
              disabled={!dashboard.data || change.isPending}
              onClick={() =>
                change.mutate({
                  status: dashboard.data?.status ?? "RUNNING",
                  environment: isPaper ? "OBSERVE" : "PAPER",
                })
              }
            >
              {isPaper
                ? i18n.t("Desactivar simulación (volver a OBSERVE)")
                : i18n.t("Activar simulación PAPER")}
            </Button>
          ) : (
            <p className="settings-readonly">
              {i18n.t(
                "Tu rol VIEWER permite consultar, pero no cambiar la configuración.",
              )}
            </p>
          )}
        </div>
        {change.isError && (
          <p className="error" role="alert">
            {i18n.t(change.error.message)}
          </p>
        )}
      </article>

      <article className="panel wide-panel settings-panel">
        <div className="settings-heading">
          <span className="settings-heading-icon">
            <Send size={19} />
          </span>
          <div>
            <p className="eyebrow">{i18n.t("Notificaciones de Telegram")}</p>
            <h2>{i18n.t("Notificaciones de Telegram")}</h2>
          </div>
          <span
            className={
              telegram.data?.has_bot_token
                ? "settings-status connected"
                : "settings-status"
            }
          >
            <i />{" "}
            {telegram.data?.has_bot_token
              ? i18n.t("Bot configurado.")
              : i18n.t("Todavía no configuraste un bot.")}
          </span>
        </div>
        <p className="muted settings-description">
          {i18n.t(
            "Creá tu propio bot con @BotFather en Telegram, pegá el token acá y el chat_id al que querés recibir avisos. El token se cifra y no se vuelve a mostrar una vez guardado.",
          )}
        </p>
        {role === "ADMIN" ? (
          <form className="settings-form" onSubmit={submitTelegram}>
            <label className="settings-token-field">
              {i18n.t("Token del bot")}
              <input
                type="password"
                value={botToken}
                onChange={(event) => setBotToken(event.target.value)}
                placeholder={
                  telegram.data?.has_bot_token
                    ? i18n.t("Ya configurado — dejar vacío para no cambiarlo")
                    : "123456:ABC-DEF..."
                }
                autoComplete="off"
                maxLength={4096}
              />
            </label>
            <label>
              Chat ID
              <input
                type="text"
                inputMode="numeric"
                value={chatId}
                onChange={(event) => setChatId(event.target.value)}
                placeholder="123456789"
              />
            </label>
            <label className="settings-toggle">
              <input
                type="checkbox"
                checked={telegramEnabled}
                onChange={(event) => setTelegramEnabled(event.target.checked)}
              />
              <span aria-hidden="true" />
              {i18n.t("Habilitado")}
            </label>
            <button
              className="button button-primary"
              disabled={saveTelegram.isPending}
            >
              {i18n.t("Guardar")}
            </button>
          </form>
        ) : (
          <p className="settings-readonly">
            {i18n.t(
              "Tu rol VIEWER permite consultar, pero no cambiar la configuración.",
            )}
          </p>
        )}
        {saveTelegram.isError && (
          <p className="error" role="alert">
            {i18n.t(saveTelegram.error.message)}
          </p>
        )}
      </article>

      {(telegramConfirmations.data?.rows.length ?? 0) > 0 && (
        <article className="panel wide-panel settings-panel">
          <div className="settings-heading">
            <span className="settings-heading-icon">
              <MessageCircle size={19} />
            </span>
            <div>
              <p className="eyebrow">{i18n.t("Solicitudes desde Telegram")}</p>
              <h2>{i18n.t("Solicitudes pendientes de confirmación")}</h2>
            </div>
          </div>
          <p className="muted settings-description">
            {i18n.t(
              "Un comando /pause o /resume enviado por Telegram nunca se ejecuta solo -- confirmalo acá con tu sesión de administrador para que tenga efecto. Vence a los 5 minutos.",
            )}
          </p>
          <div className="markets-table-wrap">
            <table className="markets-table">
              <thead>
                <tr>
                  <th>{i18n.t("Acción")}</th>
                  <th>{i18n.t("Solicitada")}</th>
                  <th>{i18n.t("Vence")}</th>
                  {role === "ADMIN" && <th>{i18n.t("Confirmar")}</th>}
                </tr>
              </thead>
              <tbody>
                {telegramConfirmations.data?.rows.map((row) => (
                  <tr key={row.confirmation_id}>
                    <td>{i18n.t(TELEGRAM_ACTION_LABELS[row.action] ?? row.action)}</td>
                    <td>{new Date(row.requested_at).toLocaleString(i18n.resolvedLanguage)}</td>
                    <td>{new Date(row.expires_at).toLocaleString(i18n.resolvedLanguage)}</td>
                    {role === "ADMIN" && (
                      <td>
                        <Button
                          disabled={confirmTelegramConfirmation.isPending}
                          onClick={() =>
                            confirmTelegramConfirmation.mutate(row.confirmation_id)
                          }
                        >
                          {i18n.t("Confirmar")}
                        </Button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {confirmTelegramConfirmation.isError && (
            <p className="error" role="alert">
              {i18n.t(confirmTelegramConfirmation.error.message)}
            </p>
          )}
        </article>
      )}

      {role === "ADMIN" && (
        <article className="panel wide-panel settings-panel">
          <div className="settings-heading">
            <span className="settings-heading-icon">
              <KeyRound size={19} />
            </span>
            <div>
              <p className="eyebrow">{i18n.t("Confirmar identidad")}</p>
              <h2>{i18n.t("Confirmar identidad (MFA)")}</h2>
            </div>
          </div>
          <p className="muted settings-description">
            {i18n.t(
              "Las acciones de administrador (activar PAPER, agregar una conexión, pausar el bot) piden una confirmación reciente con tu autenticador -- solo dura 5 minutos desde que iniciaste sesión. Si una acción falla pidiendo reautenticación, ingresá tu código acá y volvé a intentarla.",
            )}
          </p>
          <form className="settings-form" onSubmit={submitMfaConfirm}>
            <label>
              {i18n.t("Código de autenticación")}
              <input
                type="text"
                inputMode="numeric"
                value={mfaCode}
                onChange={(event) => setMfaCode(event.target.value)}
                placeholder="000000"
                autoComplete="one-time-code"
                maxLength={6}
              />
            </label>
            <button
              className="button button-primary"
              disabled={confirmMfa.isPending || mfaCode.trim().length !== 6}
            >
              {i18n.t("Confirmar")}
            </button>
          </form>
          {confirmMfa.isError && (
            <p className="error" role="alert">
              {i18n.t(confirmMfa.error.message)}
            </p>
          )}
          {confirmMfa.isSuccess && (
            <p className="settings-readonly" role="status">
              {i18n.t(
                "Identidad confirmada. Ya podés repetir la acción que había fallado.",
              )}
            </p>
          )}
        </article>
      )}
    </section>
  );
}
