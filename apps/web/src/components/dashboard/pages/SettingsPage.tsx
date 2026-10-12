import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Bot, FlaskConical, KeyRound, Lock, MessageCircle, Send, ShieldCheck } from "lucide-react";
import i18n from "../../../lib/i18n";
import type {
  aiAutonomyControlSchema,
  dashboardSchema,
  enrollmentSchema,
  sessionListSchema,
  telegramConfigSchema,
  telegramConfirmationListSchema,
  telegramConfirmationSchema,
} from "../../../lib/dto";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import { Button } from "../../ui/button";
import { MfaForm } from "../../auth/MfaForm";
import { LiveTradingPanel } from "./LiveTradingPanel";

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
  security,
  aiAutonomy,
  changeAiAutonomy,
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
    z.infer<typeof telegramConfigSchema>,
    Error,
    { bot_token?: string; chat_id?: number | null; enabled: boolean; start_pairing?: boolean }
  >;
  confirmMfa: UseMutationResult<unknown, Error, { code: string }>;
  telegramConfirmations: UseQueryResult<z.infer<typeof telegramConfirmationListSchema>>;
  confirmTelegramConfirmation: UseMutationResult<
    z.infer<typeof telegramConfirmationSchema>,
    Error,
    string
  >;
  security: {
    sessions: UseQueryResult<z.infer<typeof sessionListSchema>>;
    changePassword: UseMutationResult<
      { ok: boolean },
      Error,
      { current_password: string; new_password: string }
    >;
    startTotpReplace: UseMutationResult<z.infer<typeof enrollmentSchema>, Error, void>;
    finishTotpReplace: UseMutationResult<
      { ok: boolean },
      Error,
      { challenge: string; code: string }
    >;
    revokeSession: UseMutationResult<{ ok: boolean }, Error, string>;
  };
  aiAutonomy: UseQueryResult<z.infer<typeof aiAutonomyControlSchema>>;
  changeAiAutonomy: UseMutationResult<
    z.infer<typeof aiAutonomyControlSchema>,
    Error,
    {
      status: "DISABLED" | "ENABLED";
      target_core_pct?: string;
      target_growth_pct?: string;
      target_speculative_pct?: string;
      digest_interval_hours?: number;
      codex_enabled?: boolean;
      claude_enabled?: boolean;
      require_consensus?: boolean;
    }
  >;
}) {
  useTranslation();
  const environment = dashboard.data?.environment;
  const isPaper = environment === "PAPER";
  const [botToken, setBotToken] = useState("");
  const [telegramEnabled, setTelegramEnabled] = useState(
    telegram.data?.enabled ?? false,
  );
  const [mfaCode, setMfaCode] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [totpEnrollment, setTotpEnrollment] = useState<z.infer<typeof enrollmentSchema> | null>(
    null,
  );
  const [totpCode, setTotpCode] = useState("");
  const [corePct, setCorePct] = useState("0.70");
  const [growthPct, setGrowthPct] = useState("0.20");
  const [speculativePct, setSpeculativePct] = useState("0.10");
  const [digestHours, setDigestHours] = useState("6");
  const [codexEnabled, setCodexEnabled] = useState(true);
  const [claudeEnabled, setClaudeEnabled] = useState(true);
  const [requireConsensus, setRequireConsensus] = useState(true);

  useEffect(() => {
    if (telegram.data) {
      setTelegramEnabled(telegram.data.enabled);
    }
  }, [telegram.data]);

  useEffect(() => {
    if (aiAutonomy.data) {
      setCorePct(aiAutonomy.data.target_core_pct);
      setGrowthPct(aiAutonomy.data.target_growth_pct);
      setSpeculativePct(aiAutonomy.data.target_speculative_pct);
      setDigestHours(String(aiAutonomy.data.digest_interval_hours));
      setCodexEnabled(aiAutonomy.data.codex_enabled);
      setClaudeEnabled(aiAutonomy.data.claude_enabled);
      setRequireConsensus(aiAutonomy.data.require_consensus);
    }
  }, [aiAutonomy.data]);

  function submitTelegram(event: React.FormEvent) {
    event.preventDefault();
    saveTelegram.mutate(
      {
        bot_token: botToken.trim() || undefined,
        enabled: botToken.trim() ? true : telegramEnabled,
      },
      { onSuccess: () => setBotToken("") },
    );
  }

  function submitAiAutonomyToggle() {
    changeAiAutonomy.mutate({
      status: aiAutonomy.data?.status === "ENABLED" ? "DISABLED" : "ENABLED",
    });
  }

  function submitAiAutonomyTargets(event: React.FormEvent) {
    event.preventDefault();
    changeAiAutonomy.mutate({
      status: aiAutonomy.data?.status ?? "DISABLED",
      target_core_pct: corePct,
      target_growth_pct: growthPct,
      target_speculative_pct: speculativePct,
      digest_interval_hours: Number(digestHours),
      codex_enabled: codexEnabled,
      claude_enabled: claudeEnabled,
      require_consensus: requireConsensus,
    });
  }

  function restartTelegramPairing() {
    saveTelegram.mutate({ enabled: telegramEnabled, start_pairing: true });
  }

  function submitMfaConfirm(event: React.FormEvent) {
    event.preventDefault();
    confirmMfa.mutate(
      { code: mfaCode.trim() },
      { onSuccess: () => setMfaCode("") },
    );
  }

  function submitPasswordChange(event: React.FormEvent) {
    event.preventDefault();
    security.changePassword.mutate(
      { current_password: currentPassword, new_password: newPassword },
      { onSuccess: () => { setCurrentPassword(""); setNewPassword(""); } },
    );
  }

  function startTotpReplace() {
    security.startTotpReplace.mutate(undefined, {
      onSuccess: (result) => setTotpEnrollment(result),
    });
  }

  function submitTotpReplace(event: React.FormEvent) {
    event.preventDefault();
    if (!totpEnrollment) return;
    security.finishTotpReplace.mutate(
      { challenge: totpEnrollment.challenge, code: totpCode.trim() },
      {
        onSuccess: () => {
          setTotpEnrollment(null);
          setTotpCode("");
        },
      },
    );
  }

  return (
    <section className="settings-stack" aria-label={i18n.t("Configuración")}>
      <LiveTradingPanel role={role} />
      {environment !== "LIVE" && <article className="panel wide-panel settings-panel">
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
        <p className="settings-command-help">
          {i18n.t(
            "Cuando tu chat esté vinculado, enviá /help o /commands al bot para conocer sus comandos seguros.",
          )}
        </p>
        <div className="settings-action-row">
          <div className="settings-safety">
            <ShieldCheck size={18} />
            <span>
              {i18n.t(
                "PAPER es una prueba opcional sin dinero real. Para operar con tu cuenta usa la configuración LIVE de arriba.",
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
      </article>}

      <article className="panel wide-panel settings-panel">
        <div className="settings-heading">
          <span className="settings-heading-icon">
            <Bot size={19} />
          </span>
          <div>
            <p className="eyebrow">{i18n.t("Permisos IA")}</p>
            <h2>
              {aiAutonomy.data?.status === "ENABLED"
                ? i18n.t("Análisis de IA activado")
                : i18n.t("Análisis de IA desactivado")}
            </h2>
          </div>
          <span
            className={
              aiAutonomy.data?.status === "ENABLED"
                ? "settings-status paper"
                : "settings-status"
            }
          >
            <i /> {aiAutonomy.data?.status === "ENABLED" ? "ENABLED" : "DISABLED"}
          </span>
        </div>
        <p className="muted settings-description">
          {i18n.t(
            "Codex y Claude revisan el mismo contexto y crean propuestas sólo cuando coinciden. No compran, venden, transfieren ni retiran fondos. La simulación permanece desactivada hasta que la habilites explícitamente arriba.",
          )}
        </p>
        <div className="settings-action-row">
          {role === "ADMIN" ? (
            <Button disabled={!aiAutonomy.data || changeAiAutonomy.isPending} onClick={submitAiAutonomyToggle}>
              {aiAutonomy.data?.status === "ENABLED"
                ? i18n.t("Pausar análisis de IA")
                : i18n.t("Activar análisis de IA")}
            </Button>
          ) : (
            <p className="settings-readonly">
              {i18n.t("Tu rol VIEWER permite consultar, pero no cambiar la configuración.")}
            </p>
          )}
        </div>
        {role === "ADMIN" && (
          <form className="settings-form" onSubmit={submitAiAutonomyTargets}>
            <label>
              {i18n.t("Objetivo tier seguro (CORE)")}
              <input
                type="number" min="0" max="1" step="0.01"
                value={corePct} onChange={(event) => setCorePct(event.target.value)}
              />
            </label>
            <label>
              {i18n.t("Objetivo tier medio (GROWTH)")}
              <input
                type="number" min="0" max="1" step="0.01"
                value={growthPct} onChange={(event) => setGrowthPct(event.target.value)}
              />
            </label>
            <label>
              {i18n.t("Objetivo tier riesgo (SPECULATIVE)")}
              <input
                type="number" min="0" max="1" step="0.01"
                value={speculativePct} onChange={(event) => setSpeculativePct(event.target.value)}
              />
            </label>
            <label>
              {i18n.t("Notificarme cada (horas)")}
              <input
                type="number" min="1" step="1"
                value={digestHours} onChange={(event) => setDigestHours(event.target.value)}
              />
            </label>
            <label className="settings-toggle">
              <input
                type="checkbox"
                checked={codexEnabled}
                onChange={(event) => setCodexEnabled(event.target.checked)}
              />
              <span aria-hidden="true" />
              {i18n.t("Usar Codex como analista")}
            </label>
            <label className="settings-toggle">
              <input
                type="checkbox"
                checked={claudeEnabled}
                onChange={(event) => setClaudeEnabled(event.target.checked)}
              />
              <span aria-hidden="true" />
              {i18n.t("Usar Claude como analista")}
            </label>
            <label className="settings-toggle">
              <input
                type="checkbox"
                checked={requireConsensus}
                onChange={(event) => setRequireConsensus(event.target.checked)}
              />
              <span aria-hidden="true" />
              {i18n.t("Exigir coincidencia entre ambos")}
            </label>
            <p className="muted settings-description">
              {i18n.t("Si exigís coincidencia, una recomendación sólo se guarda cuando ambos analistas responden y sus precios propuestos no difieren de forma material.")}
            </p>
            <button className="button button-secondary" disabled={changeAiAutonomy.isPending}>
              {i18n.t("Guardar preferencias")}
            </button>
          </form>
        )}
        {changeAiAutonomy.isError && (
          <p className="error" role="alert">
            {i18n.t(changeAiAutonomy.error.message)}
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
            "Creá tu bot con @BotFather y guardá primero su token. WallyBot te dará un código de un solo uso: enviáselo con /start y vinculamos el chat automáticamente. El token se cifra y no vuelve a mostrarse.",
          )}
        </p>
        {telegram.data?.pairing_status === "WAITING_FOR_START" && (
          <div className="telegram-pairing" role="status">
            <strong>{i18n.t("Vinculá tu chat en Telegram")}</strong>
            <p>{i18n.t("Abrí tu bot y enviá el comando que aparece abajo. El chat se detectará solo; no necesitás buscar un Chat ID.")}</p>
            {saveTelegram.data?.pairing_code ? (
              <code>/start {saveTelegram.data.pairing_code}</code>
            ) : (
              <Button type="button" variant="outline" onClick={restartTelegramPairing} disabled={saveTelegram.isPending}>
                {i18n.t("Generar un nuevo código de vinculación")}
              </Button>
            )}
          </div>
        )}
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
              {telegram.data?.has_bot_token ? i18n.t("Actualizar bot") : i18n.t("Guardar y vincular bot")}
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

      <article className="panel wide-panel settings-panel">
        <div className="settings-heading">
          <span className="settings-heading-icon">
            <Lock size={19} />
          </span>
          <div>
            <p className="eyebrow">{i18n.t("Seguridad de la cuenta")}</p>
            <h2>{i18n.t("Contraseña")}</h2>
          </div>
        </div>
        <p className="muted settings-description">
          {i18n.t(
            "Cambiar tu contraseña cierra todas tus demás sesiones activas -- esta sesión sigue abierta. Si tu sesión no confirmó tu autenticador en los últimos 5 minutos, te lo va a pedir antes de continuar.",
          )}
        </p>
        <form className="settings-form" onSubmit={submitPasswordChange}>
          <label>
            {i18n.t("Contraseña actual")}
            <input
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              autoComplete="current-password"
              required
              maxLength={256}
            />
          </label>
          <label>
            {i18n.t("Contraseña nueva")}
            <input
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              autoComplete="new-password"
              required
              minLength={12}
              maxLength={256}
            />
          </label>
          <button
            className="button button-primary"
            disabled={security.changePassword.isPending || newPassword.length < 12}
          >
            {i18n.t("Cambiar contraseña")}
          </button>
        </form>
        {security.changePassword.isError && (
          <p className="error" role="alert">
            {i18n.t(security.changePassword.error.message)}
          </p>
        )}
        {security.changePassword.isSuccess && (
          <p className="settings-readonly" role="status">
            {i18n.t("Contraseña actualizada.")}
          </p>
        )}
      </article>

      <article className="panel wide-panel settings-panel">
        <div className="settings-heading">
          <span className="settings-heading-icon">
            <KeyRound size={19} />
          </span>
          <div>
            <p className="eyebrow">{i18n.t("Seguridad de la cuenta")}</p>
            <h2>{i18n.t("Autenticador (TOTP)")}</h2>
          </div>
        </div>
        <p className="muted settings-description">
          {i18n.t(
            "Reemplazar tu autenticador no desactiva el actual hasta confirmar el nuevo código -- así nunca te quedás sin acceso por un QR mal escaneado. Al confirmar, se cierran todas tus demás sesiones activas.",
          )}
        </p>
        {totpEnrollment ? (
          <MfaForm
            setup
            secret={totpEnrollment.secret}
            enrollmentUri={totpEnrollment.uri}
            code={totpCode}
            setCode={setTotpCode}
            busy={security.finishTotpReplace.isPending}
            onSubmit={submitTotpReplace}
          />
        ) : (
          <Button onClick={startTotpReplace} disabled={security.startTotpReplace.isPending}>
            {i18n.t("Reemplazar autenticador")}
          </Button>
        )}
        {(security.startTotpReplace.isError || security.finishTotpReplace.isError) && (
          <p className="error" role="alert">
            {i18n.t(
              (security.startTotpReplace.error ?? security.finishTotpReplace.error)?.message ??
                "",
            )}
          </p>
        )}
      </article>

      <article className="panel wide-panel settings-panel">
        <div className="settings-heading">
          <span className="settings-heading-icon">
            <ShieldCheck size={19} />
          </span>
          <div>
            <p className="eyebrow">{i18n.t("Seguridad de la cuenta")}</p>
            <h2>{i18n.t("Sesiones activas")}</h2>
          </div>
        </div>
        <p className="muted settings-description">
          {i18n.t(
            "Cada fila es un inicio de sesión distinto (navegador o dispositivo). Cerrar una sesión la invalida de inmediato.",
          )}
        </p>
        {security.sessions.isPending && <p className="muted">{i18n.t("Cargando…")}</p>}
        {security.sessions.isError && (
          <p className="error" role="alert">
            {i18n.t("No se pudieron cargar las sesiones.")}
          </p>
        )}
        {security.sessions.data && (
          <div className="markets-table-wrap">
            <table className="markets-table">
              <thead>
                <tr>
                  <th>{i18n.t("Iniciada")}</th>
                  <th>{i18n.t("Última actividad")}</th>
                  <th>{i18n.t("Vence")}</th>
                  <th>{i18n.t("Estado")}</th>
                  <th>{i18n.t("Acción")}</th>
                </tr>
              </thead>
              <tbody>
                {security.sessions.data.rows.map((row) => (
                  <tr key={row.session_id}>
                    <td>{new Date(row.created_at).toLocaleString(i18n.resolvedLanguage)}</td>
                    <td>{new Date(row.last_seen).toLocaleString(i18n.resolvedLanguage)}</td>
                    <td>{new Date(row.expires_at).toLocaleString(i18n.resolvedLanguage)}</td>
                    <td>
                      {row.is_current ? (
                        <span className="quality-pill quality-pass">
                          {i18n.t("Esta sesión")}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      <Button
                        disabled={security.revokeSession.isPending}
                        onClick={() => security.revokeSession.mutate(row.session_id)}
                      >
                        {i18n.t("Cerrar sesión")}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {security.revokeSession.isError && (
          <p className="error" role="alert">
            {i18n.t(security.revokeSession.error.message)}
          </p>
        )}
      </article>
    </section>
  );
}
