import { useTranslation } from "react-i18next";
import {
  FaArrowUpRightFromSquare,
  FaCircleQuestion,
  FaFlask,
  FaRadio,
  FaWallet,
} from "react-icons/fa6";
import i18n from "../../../lib/i18n";
import type { eventsSchema, portfolioSchema, systemSchema } from "../../../lib/dto";
import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import { Service } from "../Service";
import { EventList } from "../EventList";
import { liveVenueLabel, useLiveTrading } from "../../../hooks/useLiveTrading";

export function Overview({
  system,
  events,
  portfolio,
  environment,
  navigate,
}: {
  system: UseQueryResult<z.infer<typeof systemSchema>>;
  events: UseQueryResult<z.infer<typeof eventsSchema>>;
  portfolio: UseQueryResult<z.infer<typeof portfolioSchema>>;
  environment?: "OBSERVE" | "PAPER" | "LIVE";
  navigate: (next: string) => void;
}) {
  useTranslation();
  const { live } = useLiveTrading(environment === "LIVE");
  const operational =
    system.data &&
    system.data.redis === "HEALTHY" &&
    Object.values(system.data.services).every((s) => s.status === "HEALTHY");
  const balances = portfolio.data?.balances ?? [];
  const positions = balances.filter((balance) => balance.purpose === "POSITION");
  const cashBalances = balances.filter((balance) => balance.purpose === "CASH");
  const performance = portfolio.data?.performance ?? [];
  const cashCurrency = live.data?.cash_currency ?? "USDT";
  const formatAmount = (value: number) =>
    new Intl.NumberFormat(i18n.resolvedLanguage, {
      maximumFractionDigits: 2,
      minimumFractionDigits: 2,
    }).format(value);
  return (
    <>
      <section className="metrics-grid">
        {[
          [
            i18n.t(environment === "LIVE" ? "Efectivo real" : "Efectivo PAPER"),
            environment === "LIVE" ? `${live.data?.balances.find(row => row.asset === cashCurrency)?.amount ?? "—"} ${cashCurrency}` : portfolio.data ? cashBalances.length ? cashBalances.map(balance => `${formatAmount(Number(balance.amount))} ${balance.currency}`).join(" · ") : "—" : "—",
            environment === "LIVE" ? i18n.t("Saldo reconciliado con {{venue}}", { venue: liveVenueLabel(live.data?.venue) }) : portfolio.data
              ? i18n.t("Saldo de simulación disponible")
              : i18n.t("Cargando saldo de simulación"),
          ],
          [
            i18n.t(environment === "LIVE" ? "Valor de la cuenta real" : "Resultado realizado"),
            environment === "LIVE" ? `${live.data?.equity_usd ?? "—"} ${cashCurrency}` : performance.length ? performance.map(item => `${formatAmount(Number(item.realized_pnl))} ${item.quote}`).join(" · ") : "—",
            environment === "LIVE" ? live.data?.as_of ?? i18n.t("Sin valoración verificada") : performance.length ? i18n.t("Calculado con lotes FIFO") : i18n.t("Sin cierres registrados"),
          ],
          [
            i18n.t("Posiciones abiertas"),
            environment === "LIVE" ? String(live.data?.balances.filter(row => row.asset !== cashCurrency && Number(row.amount) > 0).length ?? 0) : portfolio.data ? String(positions.length) : "—",
            environment === "LIVE" ? i18n.t("Posiciones reales reconciliadas") : portfolio.data ? i18n.t("Posiciones registradas en PAPER") : i18n.t("Cargando actividad"),
          ],
          [
            i18n.t("Modo de operación"),
            environment ?? "OBSERVE",
            environment === "LIVE" ? i18n.t("Dinero real; aprobación y límites obligatorios") : environment === "PAPER"
              ? i18n.t("Órdenes simuladas; sin dinero real")
              : i18n.t("Datos reales; no se generan órdenes"),
          ],
        ].map(([label, value, note], i) => (
          <article className="metric" key={label}>
            <div>
              {label}
              <FaCircleQuestion size={13} />
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
              <FaWallet size={24} />
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
            <FaRadio size={15} />
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
            <FaArrowUpRightFromSquare size={14} />
          </button>
        </article>
      </section>
      <section className="bottom-grid">
        <article className="panel">
          <div className="panel-heading">
            <h2>{i18n.t("Actividad reciente")}</h2>
            <button className="text-button" onClick={() => navigate("events")}>
              {i18n.t("Ver todo")}
              <FaArrowUpRightFromSquare size={13} />
            </button>
          </div>
          <EventList events={events.data?.slice(0, 4)} />
        </article>
        <article className="next-step">
          <span className="eyebrow">{i18n.t("EL SIGUIENTE PASO")}</span>
          <FaFlask size={24} />
          <h2>{i18n.t("Revisa antes de operar.")}</h2>
          <p>
            {i18n.t(
              "Comprueba tu conexión, el entorno y los límites de tu cuenta. Conectar Binance no activa operaciones reales.",
            )}
          </p>
          <button className="text-button" onClick={() => navigate("portfolio")}>
            {i18n.t("Revisar mi cuenta")}
            <FaArrowUpRightFromSquare size={14} />
          </button>
        </article>
      </section>
    </>
  );
}
