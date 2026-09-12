import { useTranslation } from "react-i18next";
import i18n from "../../lib/i18n";

const labels: Record<string, string> = {
  HEALTHY: "Disponible",
  UNAVAILABLE: "Sin conexión",
  STALE: "Sin señal reciente",
  NOT_CONFIGURED: "Sin configurar",
  DISABLED: "Desactivado",
};

export function Service({ name, status }: { name: string; status?: string }) {
  useTranslation();
  return (
    <div className="service-row">
      <span>{name}</span>
      <span
        className={
          status === "HEALTHY" ? "service-status good" : "service-status"
        }
      >
        <i />
        {status ? i18n.t(labels[status] ?? status) : i18n.t("Comprobando…")}
      </span>
    </div>
  );
}
