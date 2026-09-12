import { useTranslation } from "react-i18next";
import i18n from "../../../lib/i18n";
import type { systemSchema } from "../../../lib/dto";
import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import { Service } from "../Service";

export function SystemPage({
  system,
}: {
  system: UseQueryResult<z.infer<typeof systemSchema>>;
}) {
  useTranslation();
  return (
    <article className="panel wide-panel">
      <div className="panel-heading">
        <h2>{i18n.t("Servicios y dependencias")}</h2>
        <span className="subtle-pill">{i18n.t("ACTUALIZACIÓN CADA 10 S")}</span>
      </div>
      <Service name="API" status={system.data?.api} />
      <Service name="PostgreSQL" status={system.data?.database} />
      <Service name="Redis" status={system.data?.redis} />
      {Object.entries(system.data?.services ?? {}).map(([name, s]) => (
        <Service
          key={name}
          name={`${name} · ${s.age_seconds === null ? i18n.t("sin señal") : `${s.age_seconds}s`}`}
          status={s.status}
        />
      ))}
      <Service name="Exchange" status="NOT_CONFIGURED" />
      <Service name={i18n.t("Analista IA")} status="DISABLED" />
      <Service name="Telegram" status="DISABLED" />
    </article>
  );
}
