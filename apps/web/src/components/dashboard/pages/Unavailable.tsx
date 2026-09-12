import { useTranslation } from "react-i18next";
import { FlaskConical } from "lucide-react";
import i18n from "../../../lib/i18n";

export function Unavailable({ page }: { page: "portfolio" | "research" }) {
  useTranslation();
  return (
    <article className="panel unavailable">
      <FlaskConical size={32} />
      <h2>
        {page === "portfolio"
          ? i18n.t("Tu portafolio, cuando haya datos.")
          : i18n.t("Ideas que se prueban con datos.")}
      </h2>
      <p>
        {page === "portfolio"
          ? i18n.t(
              "La contabilidad, las posiciones y la simulación se incorporan en las fases 3 y 4.",
            )
          : i18n.t(
              "Los experimentos y backtests reproducibles se incorporan en la fase 5.",
            )}
      </p>
      <span className="subtle-pill">{i18n.t("PLANIFICADO · AÚN NO DISPONIBLE")}</span>
    </article>
  );
}
