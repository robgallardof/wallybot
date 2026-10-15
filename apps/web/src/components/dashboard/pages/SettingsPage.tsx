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
import { OperationModeSwitch } from "./OperationModeSwitch";
import { SettingsSwitch } from "../../ui/SettingsSwitch";

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
  checkAnalysts,
  startAnalyst,
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
  checkAnalysts: UseMutationResult<z.infer<typeof aiAutonomyControlSchema>, Error, void>;
  startAnalyst: UseMutationResult<
    z.infer<typeof aiAutonomyControlSchema>,
    Error,
    "codex" | "claude"
  >;
}) {
  useTranslation();
  const environment = dashboard.data?.environment;
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
  const saved = aiAutonomy.data;
  const checkPending = Boolean(aiAutonomy.data?.check_pending);
  const savedCore = saved?.target_core_pct;
  const savedGrowth = saved?.target_growth_pct;
  const savedSpeculative = saved?.target_speculative_pct;
  const savedHours = saved?.digest_interval_hours;
  const savedCodex = saved?.codex_enabled;
  const savedClaude = saved?.claude_enabled;
  const savedConsensus = saved?.require_consensus;

  useEffect(() => {
    if (telegram.data) {
      setTelegramEnabled(telegram.data.enabled);
    }
  }, [telegram.data]);

  useEffect(() => {
    if (savedCore !== undefined && savedGrowth !== undefined && savedSpeculative !== undefined && savedHours !== undefined && savedCodex !== undefined && savedClaude !== undefined && savedConsensus !== undefined) {
      setCorePct(savedCore);
      setGrowthPct(savedGrowth);
      setSpeculativePct(savedSpeculative);
      setDigestHours(String(savedHours));
      setCodexEnabled(savedCodex);
      setClaudeEnabled(savedClaude);
      setRequireConsensus(savedConsensus);
    }
  }, [savedCore, savedGrowth, savedSpeculative, savedHours, savedCodex, savedClaude, savedConsensus]);

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
      <nav className="settings-index" aria-label={i18n.t("Secciones de configuración")}>
        <a href="#settings-mode"><FlaskConical size={18} />{i18n.t("Operación")}</a>
        <a href="#settings-analysts"><Bot size={18} />{i18n.t("Analistas")}</a>
        <a href="#settings-telegram"><Send size={18} />Telegram</a>
        {role === "ADMIN" && <a href="#settings-security"><Lock size={18} />{i18n.t("Seguridad")}</a>}
      </nav>
      <div id="settings-mode" className="settings-anchor">
        <OperationModeSwitch
          environment={environment}
          status={dashboard.data?.status}
          role={role}
          change={change}
          liveAnchorId="settings-trading"
        />
      </div>
      <div id="settings-trading" className="settings-anchor"><LiveTradingPanel role={role} /></div>

      <article className="panel wide-panel settings-panel settings-anchor" id="settings-analysts">
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
            "Elige Codex, Claude o ambos. Los analistas preparan propuestas; cada operación requiere tu aprobación y la validación de riesgo. Antigravity todavía no está integrado.",
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
        <p className="analyst-policy-summary">
          <strong>{i18n.t("Regla guardada")}: </strong>
          {i18n.t(aiAutonomy.data?.require_consensus
            ? "Consenso obligatorio: Codex y Claude deben responder y coincidir. Si uno falla, no hay propuesta."
            : "Sin consenso obligatorio: una respuesta válida puede bastar. Si ambos proponen y discrepan, no hay propuesta.")}
        </p>
        <div className="analyst-status-heading">
          <h3>{i18n.t("Disponibilidad de analistas")}</h3>
          <Button variant="outline" disabled={aiAutonomy.isFetching}
            onClick={() => void aiAutonomy.refetch()}>{i18n.t("Actualizar estado")}</Button>
          {role === "ADMIN" && (
            <Button variant="outline"
              disabled={checkAnalysts.isPending || checkPending}
              onClick={() => void checkAnalysts.mutateAsync()}>
              {checkAnalysts.isPending || checkPending ? i18n.t("Comprobando…") : i18n.t("Comprobar ahora")}
            </Button>
          )}
        </div>
        <ul className="analyst-availability" aria-label={i18n.t("Disponibilidad de analistas")}>
          {(aiAutonomy.data?.analysts ?? []).map((item) => {
            const name = item.analyst === "codex" ? "Codex" : "Claude";
            const enabled =
              item.analyst === "codex"
                ? aiAutonomy.data?.codex_enabled
                : aiAutonomy.data?.claude_enabled;
            const state = checkPending && enabled
              ? i18n.t("Comprobando…")
              : item.available === null
                ? i18n.t("Sin comprobar todavía")
                : item.available
                  ? i18n.t("Disponible")
                  : i18n.t("No disponible");
            const checkedAt = item.checked_at ? Date.parse(item.checked_at) : NaN;
            // The worker re-checks idle CLIs hourly; only flag results clearly older than that.
            const stale = !checkPending && Number.isFinite(checkedAt) &&
              (Date.now() - checkedAt > 2 * 60 * 60 * 1000 || checkedAt > Date.now() + 60_000);
            return (
              <li key={item.analyst}>
                <div className="analyst-status-title"><strong>{name}</strong>
                  <span className={`analyst-state ${stale ? "stale" : item.available && !checkPending ? "ready" : "pending"}`}>
                    {stale ? i18n.t("Comprobación desactualizada") : state}
                  </span>
                  {role === "ADMIN" && (
                    <Button variant="outline"
                      disabled={startAnalyst.isPending || checkPending}
                      aria-label={i18n.t("Iniciar {{name}}", { name })}
                      onClick={() => void startAnalyst.mutateAsync(item.analyst)}>
                      {startAnalyst.isPending && startAnalyst.variables === item.analyst
                        ? i18n.t("Iniciando…")
                        : i18n.t("Iniciar {{name}}", { name })}
                    </Button>
                  )}
                </div>
                {item.checked_at && (
                  <span className="muted">
                    {i18n.t("comprobado")} {new Date(item.checked_at).toLocaleString(i18n.resolvedLanguage)}
                  </span>
                )}
                {enabled && !checkPending && item.available === false && (
                  <p className="error" role="alert">
                    {i18n.t(
                      "{{name}} no disponible. Puede ser límite de uso, sesión cerrada o CLI no instalada. Usa «Comprobar ahora» para ejecutar una prueba nueva. Para iniciar sesión: {{command}}.",
                      {
                        name,
                        command: item.analyst === "codex" ? "codex login" : "claude auth login",
                      },
                    )}
                    {aiAutonomy.data?.require_consensus &&
                      " " +
                        i18n.t(
                          "Mientras exijas coincidencia no se crearán propuestas. Si prefieres no usarlo, desactívalo y desmarca la coincidencia tú mismo: WallyBot no cambia estos ajustes automáticamente.",
                        )}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
        {role === "ADMIN" && (
          <form className="settings-form analyst-preferences" onSubmit={submitAiAutonomyTargets}>
            <fieldset className="settings-fields"><legend>{i18n.t("Asignación y avisos")}</legend>
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
            </fieldset>
            <fieldset className="settings-switches"><legend>{i18n.t("Analistas y consenso")}</legend>
              <SettingsSwitch label={i18n.t("Usar Codex como analista")} checked={codexEnabled} onChange={setCodexEnabled} />
              <SettingsSwitch label={i18n.t("Usar Claude como analista")} checked={claudeEnabled} onChange={setClaudeEnabled} />
              <SettingsSwitch label={i18n.t("Exigir coincidencia entre ambos")} checked={requireConsensus} onChange={setRequireConsensus}
                description={i18n.t("Requiere ambos analistas activados. No se desactiva automáticamente si uno falla.")} />
            </fieldset>
            <p className="muted settings-description">
              {i18n.t("Si exigís coincidencia, una recomendación sólo se guarda cuando ambos analistas responden y sus precios propuestos no difieren de forma material.")}
            </p>
            {requireConsensus && (!codexEnabled || !claudeEnabled) && <p className="error" role="alert">{i18n.t("El consenso requiere activar Codex y Claude, o desmarcar explícitamente la coincidencia.")}</p>}
            <button className="button button-primary settings-save" disabled={changeAiAutonomy.isPending || (requireConsensus && (!codexEnabled || !claudeEnabled)) || (!codexEnabled && !claudeEnabled)}>
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

      <article className="panel wide-panel settings-panel settings-anchor" id="settings-telegram">
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
            <SettingsSwitch label={i18n.t("Habilitado")} checked={telegramEnabled} onChange={setTelegramEnabled} />
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
        <article className="panel wide-panel settings-panel settings-anchor" id="settings-security">
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
