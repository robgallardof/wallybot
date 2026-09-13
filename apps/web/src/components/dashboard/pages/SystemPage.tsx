import { useTranslation } from "react-i18next";
import type { systemSchema } from "../../../lib/dto";
import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import { Service } from "../Service";

export function SystemPage({
  system,
}: {
  system: UseQueryResult<z.infer<typeof systemSchema>>;
}) {
  const { t, i18n } = useTranslation();
  const data = system.data;
  return (
    <article className="panel wide-panel system-panel">
      <div className="panel-heading">
        <div>
          <h2>{t("Servicios y dependencias")}</h2>
          <p>
            {t("Comprueba las conexiones y la última señal de cada proceso.")}
          </p>
        </div>
        <button
          className="button button-outline"
          disabled={system.isFetching}
          onClick={() => void system.refetch()}
        >
          {system.isFetching ? t("Actualizando…") : t("Actualizar")}
        </button>
      </div>
      <p className="muted system-updated">
        {t("ACTUALIZACIÓN CADA 10 S")}
        {system.dataUpdatedAt > 0 && (
          <>
            {" "}
            · {t("Última consulta correcta")}:{" "}
            <time dateTime={new Date(system.dataUpdatedAt).toISOString()}>
              {new Date(system.dataUpdatedAt).toLocaleTimeString(i18n.language)}
            </time>
          </>
        )}
      </p>
      {system.isError && (
        <p className="error" role="alert">
          {data
            ? t(
                "No se pudo actualizar el sistema. Los estados mostrados corresponden a la última consulta correcta.",
              )
            : t(
                "No se pudo consultar el sistema. Intenta actualizar de nuevo.",
              )}
        </p>
      )}
      {system.isPending && (
        <p className="muted" role="status">
          {t("Comprobando servicios…")}
        </p>
      )}
      {data && (
        <div className="system-groups">
          <section aria-labelledby="system-connections">
            <h3 id="system-connections">{t("Conexiones esenciales")}</h3>
            <Service name="API" status={data.api} />
            <Service name="PostgreSQL" status={data.database} />
            <Service name="Redis" status={data.redis} />
          </section>
          <section aria-labelledby="system-processes">
            <h3 id="system-processes">{t("Procesos en segundo plano")}</h3>
            <p className="muted">
              {t("La antigüedad de la señal se mide al consultar el sistema.")}
            </p>
            {Object.entries(data.services).map(([name, s]) => (
              <Service
                key={name}
                name={name}
                description={
                  s.age_seconds === null
                    ? t("Sin señal registrada")
                    : t("Última señal hace {{seconds}} s", {
                        seconds: s.age_seconds,
                      })
                }
                status={s.status}
              />
            ))}
            {Object.keys(data.services).length === 0 && (
              <p className="muted">
                {t("No se han recibido estados de procesos.")}
              </p>
            )}
          </section>
          <section aria-labelledby="system-integrations">
            <h3 id="system-integrations">{t("Integraciones")}</h3>
            <Service name="Exchange" status={data.exchange} />
            <Service name={t("Analista IA")} status={data.ai} />
            <Service name="Telegram" status={data.telegram} />
            <p className="muted">
              {t(
                "Estos estados son los informados por el sistema; no certifican acceso para operar.",
              )}
            </p>
          </section>
        </div>
      )}
    </article>
  );
}
