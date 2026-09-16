import { useTranslation } from "react-i18next";
import { FlaskConical, ShieldCheck } from "lucide-react";
import i18n from "../../../lib/i18n";
import type { dashboardSchema } from "../../../lib/dto";
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
}: {
  dashboard: UseQueryResult<z.infer<typeof dashboardSchema>>;
  change: UseMutationResult<unknown, Error, { status: string; environment?: string }>;
  role: string;
}) {
  useTranslation();
  const environment = dashboard.data?.environment;
  const isPaper = environment === "PAPER";

  return (
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
  );
}
