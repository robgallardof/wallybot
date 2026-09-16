import { useState } from "react";
import { useTranslation } from "react-i18next";
import { FlaskConical, Send, ShieldCheck } from "lucide-react";
import i18n from "../../../lib/i18n";
import type { dashboardSchema, telegramConfigSchema } from "../../../lib/dto";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import { Button } from "../../ui/button";

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
}: {
  dashboard: UseQueryResult<z.infer<typeof dashboardSchema>>;
  change: UseMutationResult<unknown, Error, { status: string; environment?: string }>;
  role: string;
  telegram: UseQueryResult<z.infer<typeof telegramConfigSchema>>;
  saveTelegram: UseMutationResult<
    unknown,
    Error,
    { bot_token?: string; chat_id?: number | null; enabled: boolean }
  >;
}) {
  useTranslation();
  const environment = dashboard.data?.environment;
  const isPaper = environment === "PAPER";
  const [botToken, setBotToken] = useState("");
  const [chatId, setChatId] = useState(
    telegram.data?.chat_id != null ? String(telegram.data.chat_id) : "",
  );
  const [telegramEnabled, setTelegramEnabled] = useState(telegram.data?.enabled ?? false);

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

  return (
    <>
    <article className="panel wide-panel">
      <div className="panel-heading">
        <h2>{i18n.t("Modo de simulación")}</h2>
        <FlaskConical size={20} />
      </div>
      <h3>
        {isPaper
          ? i18n.t("Simulación PAPER activada")
          : i18n.t("Observando mercados reales (OBSERVE)")}
      </h3>
      <p className="muted">
        {i18n.t(
          "Por defecto tu instancia solo observa datos reales de mercado: no genera ni simula operaciones. Activa PAPER si querés que el sistema simule órdenes sobre esos mismos datos, sin dinero real ni conexión de ejecución.",
        )}
      </p>
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
        <p>
          {i18n.t("Tu rol VIEWER permite consultar, pero no cambiar la configuración.")}
        </p>
      )}
      <p className="footnote">
        <ShieldCheck size={13} />{" "}
        {i18n.t(
          "PAPER nunca envía órdenes reales ni requiere claves de ejecución. La ejecución real (LIVE) no está disponible en esta fase.",
        )}
      </p>
    </article>
    <article className="panel wide-panel">
      <div className="panel-heading">
        <h2>{i18n.t("Notificaciones de Telegram")}</h2>
        <Send size={20} />
      </div>
      <p className="muted">
        {i18n.t(
          "Creá tu propio bot con @BotFather en Telegram, pegá el token acá y el chat_id al que querés recibir avisos. El token se cifra y no se vuelve a mostrar una vez guardado.",
        )}
      </p>
      {role === "ADMIN" ? (
        <form className="market-filters" onSubmit={submitTelegram}>
          <label>
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
          <label>
            <input
              type="checkbox"
              checked={telegramEnabled}
              onChange={(event) => setTelegramEnabled(event.target.checked)}
            />{" "}
            {i18n.t("Habilitado")}
          </label>
          <button className="button button-primary" disabled={saveTelegram.isPending}>
            {i18n.t("Guardar")}
          </button>
        </form>
      ) : (
        <p>
          {i18n.t("Tu rol VIEWER permite consultar, pero no cambiar la configuración.")}
        </p>
      )}
      {saveTelegram.isError && (
        <p className="error" role="alert">
          {i18n.t("No se pudo guardar la configuración de Telegram.")}
        </p>
      )}
      <p className="footnote">
        {telegram.data?.has_bot_token
          ? i18n.t("Bot configurado.")
          : i18n.t("Todavía no configuraste un bot.")}
      </p>
    </article>
    </>
  );
}
