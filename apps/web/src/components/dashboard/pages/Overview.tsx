import { useTranslation } from "react-i18next";
import { ArrowUpRight, CircleHelp, FlaskConical, Radio, Wallet } from "lucide-react";
import i18n from "../../../lib/i18n";
import type { eventsSchema, systemSchema } from "../../../lib/dto";
import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import { Service } from "../Service";
import { EventList } from "../EventList";

export function Overview({
  system,
  events,
  navigate,
}: {
  system: UseQueryResult<z.infer<typeof systemSchema>>;
  events: UseQueryResult<z.infer<typeof eventsSchema>>;
  navigate: (next: string) => void;
}) {
  useTranslation();
  const operational =
    system.data &&
    system.data.redis === "HEALTHY" &&
    Object.values(system.data.services).every((s) => s.status === "HEALTHY");
  return (
    <>
      <section className="metrics-grid">
        {[
          [
            i18n.t("Patrimonio total"),
            "—",
            i18n.t("Esperando datos de portafolio"),
          ],
          [
            i18n.t("Resultado neto"),
            "—",
            i18n.t("Sin operaciones registradas"),
          ],
          [
            i18n.t("Posiciones abiertas"),
            "0",
            i18n.t("La simulación llega en la fase 4"),
          ],
          [
            i18n.t("Modo de operación"),
            "OBSERVAR",
            i18n.t("Datos reales; no se enviarán órdenes"),
          ],
        ].map(([label, value, note], i) => (
          <article className="metric" key={label}>
            <div>
              {label}
              <CircleHelp size={14} />
            </div>
            <strong className={i === 3 ? "green-value" : ""}>{value}</strong>
            <small>{note}</small>
          </article>
        ))}
      </section>
      <section className="overview-grid">
        <article className="panel capital">
          <div className="panel-heading">
            <div>
              <h2>{i18n.t("Evolución del portafolio")}</h2>
              <p>{i18n.t("El rendimiento se construye con evidencia.")}</p>
            </div>
            <span className="subtle-pill">{i18n.t("SIN DATOS")}</span>
          </div>
          <div className="empty-chart">
            <div className="chart-grid" />
            <div className="empty-chart-label">
              <Wallet size={26} />
              <h3>{i18n.t("Todo empieza con una base sólida")}</h3>
              <p>
                {i18n.t(
                  "Cuando la simulación esté disponible, podrás seguir aquí",
                )}
                <br />
                {i18n.t("tu patrimonio y compararlo con los benchmarks.")}
              </p>
              <span>
                {i18n.t(
                  "Sin resultados ficticios. Sin rentabilidad supuesta.",
                )}
              </span>
            </div>
          </div>
          <div className="chart-footer">
            <span>
              <i /> {i18n.t("Patrimonio")}
            </span>
            <span>
              <i /> Benchmark
            </span>
            <small>{i18n.t("Se mostrarán datos cuando estén disponibles")}</small>
          </div>
        </article>
        <article className="panel system-summary">
          <div className="panel-heading">
            <h2>{i18n.t("Estado del sistema")}</h2>
            <Radio size={17} />
          </div>
          <div className="system-state">
            <span
              className={
                operational ? "status-light" : "status-light pending"
              }
            />
            <div>
              <strong>
                {system.isPending
                  ? i18n.t("Comprobando servicios")
                  : operational
                    ? i18n.t("Base operativa disponible")
                    : i18n.t("Requiere atención")}
              </strong>
              <small>{i18n.t("Estado observado de los servicios")}</small>
            </div>
          </div>
          <Service name="API" status={system.data?.api} />
          <Service name="PostgreSQL" status={system.data?.database} />
          <Service name="Redis" status={system.data?.redis} />
          <Service
            name={i18n.t("Procesador")}
            status={system.data?.services.worker?.status}
          />
          <Service
            name={i18n.t("Planificador")}
            status={system.data?.services.scheduler?.status}
          />
          <button className="text-button" onClick={() => navigate("system")}>
            {i18n.t("Ver todos los servicios")}
            <ArrowUpRight size={16} />
          </button>
        </article>
      </section>
      <section className="bottom-grid">
        <article className="panel">
          <div className="panel-heading">
            <h2>{i18n.t("Actividad reciente")}</h2>
            <button className="text-button" onClick={() => navigate("events")}>
              {i18n.t("Ver todo")}
              <ArrowUpRight size={15} />
            </button>
          </div>
          <EventList events={events.data?.slice(0, 4)} />
        </article>
        <article className="next-step">
          <span className="eyebrow">{i18n.t("EL SIGUIENTE PASO")}</span>
          <FlaskConical size={26} />
          <h2>{i18n.t("Observar antes de actuar.")}</h2>
          <p>
            {i18n.t(
              "La siguiente fase incorpora mercados, datos validados y un explorador de oportunidades.",
            )}
          </p>
          <span>{i18n.t("FASE 02 · DATOS DE MERCADO")}</span>
        </article>
      </section>
    </>
  );
}
