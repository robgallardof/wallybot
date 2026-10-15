import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { UseMutationResult } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";
import i18n from "../../../lib/i18n";

type Environment = "OBSERVE" | "PAPER" | "LIVE";

const MODES: { value: Environment; title: string; help: string }[] = [
  {
    value: "OBSERVE",
    title: "Observar",
    help: "Solo observa mercados y genera análisis. No opera.",
  },
  {
    value: "PAPER",
    title: "Simulación",
    help: "Simula órdenes con dinero ficticio sobre datos reales.",
  },
  {
    value: "LIVE",
    title: "Dinero real",
    help: "Opera tu cuenta real dentro de los límites que configures.",
  },
];

/**
 * Single place to switch the instance's operating mode. OBSERVE and PAPER apply directly; LIVE is
 * never a one-click change: it sends the operator to the real-account panel, where a verified
 * trading connection, explicit limits, typing LIVE and a fresh TOTP are still required.
 */
export function OperationModeSwitch({
  environment,
  status,
  role,
  change,
  liveAnchorId,
}: {
  environment?: Environment;
  status?: string;
  role?: string;
  change: UseMutationResult<unknown, Error, { status: string; environment?: string }>;
  liveAnchorId: string;
}) {
  useTranslation();
  const [liveGuide, setLiveGuide] = useState(false);
  const canChange = role === "ADMIN" && environment !== undefined && !change.isPending;

  function choose(mode: Environment) {
    if (mode === environment) return;
    if (mode === "LIVE") {
      setLiveGuide(true);
      const panel = document.getElementById(liveAnchorId);
      panel?.scrollIntoView({ behavior: "smooth", block: "start" });
      panel?.querySelector<HTMLElement>("select, input, button")?.focus({ preventScroll: true });
      return;
    }
    if (
      environment === "LIVE" &&
      !window.confirm(i18n.t("Salir de LIVE desactiva las operaciones con dinero real. ¿Continuar?"))
    )
      return;
    setLiveGuide(false);
    change.mutate({ status: status ?? "RUNNING", environment: mode });
  }

  return (
    <article className="panel wide-panel settings-panel">
      <div className="settings-heading">
        <span className="settings-heading-icon">
          <FlaskConical size={19} />
        </span>
        <div>
          <p className="eyebrow">{i18n.t("Modo de operación")}</p>
          <h2>{i18n.t("¿Qué hace WallyBot con tus análisis?")}</h2>
        </div>
      </div>
      <div className="operation-mode-switch" role="group" aria-label={i18n.t("Modo de operación")}>
        {MODES.map((mode) => (
          <button
            key={mode.value}
            type="button"
            className={`operation-mode ${mode.value === environment ? "active" : ""} ${mode.value.toLowerCase()}`}
            aria-pressed={mode.value === environment}
            disabled={!canChange}
            onClick={() => choose(mode.value)}
          >
            <strong>{mode.value}</strong>
            <span>{i18n.t(mode.title)}</span>
            <small>{i18n.t(mode.help)}</small>
          </button>
        ))}
      </div>
      {liveGuide && environment !== "LIVE" && (
        <p className="settings-command-help" role="status">
          {i18n.t(
            "Para pasar a LIVE: 1) en Conexiones, edita tu Binance y activa «Trading spot real»; 2) en «Operaciones con dinero real», elige esa conexión, define los límites, escribe LIVE y confirma con tu código TOTP.",
          )}
        </p>
      )}
      {role !== "ADMIN" && (
        <p className="settings-readonly">
          {i18n.t("Tu rol VIEWER permite consultar, pero no cambiar la configuración.")}
        </p>
      )}
      {change.isError && (
        <p className="error" role="alert">
          {i18n.t(change.error.message)}
        </p>
      )}
    </article>
  );
}
