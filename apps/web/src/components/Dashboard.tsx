import i18n from "../lib/i18n";
import { useTranslation } from "react-i18next";
import { usePathname, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  CircleHelp,
  FlaskConical,
  LayoutDashboard,
  LogOut,
  Pause,
  Play,
  Radio,
  Settings2,
  ShieldCheck,
  Wallet,
} from "lucide-react";
import { z } from "zod";
import {
  api,
  dashboardSchema,
  eventsSchema,
  meSchema,
  systemSchema,
} from "../lib/api";
import { Button } from "./ui/button";
import { LanguageSelector } from "./LanguageSelector";
import { ThemeToggle } from "./ThemeToggle";

const labels: Record<string, string> = {
  HEALTHY: "Disponible",
  UNAVAILABLE: "Sin conexión",
  STALE: "Sin señal reciente",
  NOT_CONFIGURED: "Sin configurar",
  DISABLED: "Desactivado",
};

export function Dashboard({
  user,
  logout,
}: {
  user: z.infer<typeof meSchema>;
  logout: () => void;
}) {
  useTranslation();
  const router = useRouter();
  const initial = usePathname().slice(1);
  const page = ["system", "events", "research", "portfolio", "risk"].includes(
    initial,
  )
    ? initial
    : "dashboard";
  const client = useQueryClient();
  const dashboard = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api("/dashboard", dashboardSchema),
    refetchInterval: 10000,
  });
  const system = useQuery({
    queryKey: ["system"],
    queryFn: () => api("/system", systemSchema),
    refetchInterval: 10000,
  });
  const events = useQuery({
    queryKey: ["events"],
    queryFn: () => api("/events", eventsSchema),
    refetchInterval: 10000,
  });
  const change = useMutation({
    mutationFn: (status: string) =>
      api(
        "/control",
        z.object({ status: z.string(), environment: z.string() }),
        { status },
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["dashboard"] });
      void client.invalidateQueries({ queryKey: ["events"] });
    },
  });
  const navigation = [
    ["dashboard", i18n.t("Resumen"), LayoutDashboard],
    ["portfolio", i18n.t("Portafolio"), Wallet],
    ["research", i18n.t("Investigación"), FlaskConical],
    ["risk", i18n.t("Riesgo"), ShieldCheck],
    ["events", i18n.t("Actividad"), Activity],
    ["system", i18n.t("Sistema"), Settings2],
  ] as const;
  const title = navigation.find((n) => n[0] === page)?.[1] ?? i18n.t("Resumen");
  function navigate(next: string) {
    router.push(`/${next}`);
  }
  const operational =
    system.data &&
    system.data.redis === "HEALTHY" &&
    Object.values(system.data.services).every((s) => s.status === "HEALTHY");

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <a className="brand" href="/dashboard">
          wally<span>bot</span>
          <i />
        </a>
        <div className="workspace">
          <span className="avatar">W</span>
          <div>
            {i18n.t("Mi espacio")}
            <small>{i18n.t("Instancia privada")}</small>
          </div>
          <span className="workspace-dot" />
        </div>
        <p className="nav-caption">{i18n.t("CENTRO DE CONTROL")}</p>
        <nav>
          {navigation.map(([key, label, Icon]) => (
            <button
              key={key}
              className={page === key ? "nav-item active" : "nav-item"}
              onClick={() => navigate(key)}
            >
              <Icon size={18} />
              {label}
              {key === "dashboard" && <span className="nav-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="safety-note">
            <ShieldCheck size={20} />
            <strong>{i18n.t("Primero, preservar.")}</strong>
            <p>
              {i18n.t("La ejecución real no está disponible en esta fase.")}
            </p>
          </div>
          <button className="user-button" onClick={logout}>
            <span className="avatar small">
              {user.username.slice(0, 1).toUpperCase()}
            </span>
            <span>
              {user.username}
              <small>{user.role}</small>
            </span>
            <LogOut size={16} />
          </button>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div className="flex items-center gap-2">
            <LanguageSelector />
            <ThemeToggle />
          </div>
          <span>
            {i18n.t("Espacio de trabajo")}
            <span className="slash">/</span> <strong>{title}</strong>
          </span>
          <div>
            <span className="paper-pill">
              <i /> PAPER
            </span>
            <span className="top-date">
              {new Intl.DateTimeFormat(i18n.resolvedLanguage, {
                dateStyle: "medium",
                timeZone: "UTC",
              }).format(new Date())}{" "}
              · UTC
            </span>
            <button
              className="mobile-logout"
              aria-label={i18n.t("Cerrar sesión")}
              onClick={logout}
            >
              <LogOut size={17} />
            </button>
          </div>
        </header>
        <div className="page">
          <div className="page-heading">
            <div>
              <span className="eyebrow">{i18n.t("PORTFOLIO & RESEARCH")}</span>
              <h1>
                {page === "dashboard" ? i18n.t("Una visión clara.") : title}
              </h1>
              <p className="muted">
                {page === "dashboard"
                  ? i18n.t(
                      "Tu capital, tu actividad y el estado de tu sistema, en un solo lugar.",
                    )
                  : i18n.t("Información de tu instancia privada de WallyBot.")}
              </p>
            </div>
            <span className="phase-tag">
              {i18n.t("FASE 01")}
              <span>{i18n.t("Base operativa")}</span>
            </span>
          </div>
          {(dashboard.error || system.error || events.error) && (
            <p role="alert" className="error">
              {i18n.t(
                "No se pudo actualizar el panel. Comprueba la conexión y los servicios; los datos anteriores pueden estar desactualizados.",
              )}
            </p>
          )}
          {change.error && (
            <p role="alert" className="error">
              {i18n.t(change.error.message)}
            </p>
          )}
          <div className="notice">
            <ShieldCheck size={19} />
            <div>
              <strong>
                {i18n.t("Estás en un entorno seguro de preparación.")}
              </strong>
              <span>
                {" "}
                {i18n.t(
                  "Modo PAPER. No hay conexión de ejecución ni dinero real en uso.",
                )}
              </span>
            </div>
          </div>
          {page === "dashboard" && (
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
                    "PAPER",
                    i18n.t("Ejecución real deshabilitada"),
                  ],
                ].map(([label, value, note], i) => (
                  <article className="metric" key={label}>
                    <div>
                      {label}
                      <CircleHelp size={14} />
                    </div>
                    <strong className={i === 3 ? "green-value" : ""}>
                      {value}
                    </strong>
                    <small>{note}</small>
                  </article>
                ))}
              </section>
              <section className="overview-grid">
                <article className="panel capital">
                  <div className="panel-heading">
                    <div>
                      <h2>{i18n.t("Evolución del portafolio")}</h2>
                      <p>
                        {i18n.t("El rendimiento se construye con evidencia.")}
                      </p>
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
                        {i18n.t(
                          "tu patrimonio y compararlo con los benchmarks.",
                        )}
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
                    <small>
                      {i18n.t("Se mostrarán datos cuando estén disponibles")}
                    </small>
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
                      <small>
                        {i18n.t("Estado observado de los servicios")}
                      </small>
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
                  <button
                    className="text-button"
                    onClick={() => navigate("system")}
                  >
                    {i18n.t("Ver todos los servicios")}
                    <ArrowUpRight size={16} />
                  </button>
                </article>
              </section>
              <section className="bottom-grid">
                <article className="panel">
                  <div className="panel-heading">
                    <h2>{i18n.t("Actividad reciente")}</h2>
                    <button
                      className="text-button"
                      onClick={() => navigate("events")}
                    >
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
          )}
          {page === "system" && (
            <article className="panel wide-panel">
              <div className="panel-heading">
                <h2>{i18n.t("Servicios y dependencias")}</h2>
                <span className="subtle-pill">
                  {i18n.t("ACTUALIZACIÓN CADA 10 S")}
                </span>
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
          )}
          {page === "events" && (
            <article className="panel wide-panel">
              <div className="panel-heading">
                <h2>{i18n.t("Registro de actividad")}</h2>
                <span className="subtle-pill">
                  {i18n.t("ÚLTIMOS 100 EVENTOS")}
                </span>
              </div>
              <EventList events={events.data} />
            </article>
          )}
          {page === "risk" && (
            <article className="panel wide-panel">
              <div className="panel-heading">
                <h2>{i18n.t("Control de la instancia")}</h2>
                <ShieldCheck size={20} />
              </div>
              <h3>
                {dashboard.data?.status === "PAUSED"
                  ? i18n.t("Instancia pausada")
                  : i18n.t("Instancia en preparación")}
              </h3>
              <p className="muted">
                {i18n.t(
                  "Pausar registra el estado de control. La monitorización y el mantenimiento siguen activos. Esta fase aún no genera operaciones.",
                )}
              </p>
              {user.role === "ADMIN" ? (
                <Button
                  disabled={!dashboard.data || change.isPending}
                  onClick={() =>
                    change.mutate(
                      dashboard.data?.status === "PAUSED"
                        ? "RUNNING"
                        : "PAUSED",
                    )
                  }
                >
                  {dashboard.data?.status === "PAUSED" ? (
                    <Play size={16} />
                  ) : (
                    <Pause size={16} />
                  )}
                  {dashboard.data?.status === "PAUSED"
                    ? i18n.t("Reanudar instancia PAPER")
                    : i18n.t("Pausar instancia")}
                </Button>
              ) : (
                <p>
                  {i18n.t(
                    "Tu rol VIEWER permite consultar, pero no cambiar controles.",
                  )}
                </p>
              )}
              <p className="footnote">
                {i18n.t(
                  "Requiere una sesión verificada con MFA en los últimos 5 minutos. Los límites de cartera y RiskEngine se implementan en la fase 3.",
                )}
              </p>
            </article>
          )}
          {["portfolio", "research"].includes(page) && (
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
              <span className="subtle-pill">
                {i18n.t("PLANIFICADO · AÚN NO DISPONIBLE")}
              </span>
            </article>
          )}
          <footer className="page-footer">
            <span>
              WALLYBOT <span>v0.1 · Foundation</span>
            </span>
            <span>
              <ShieldCheck size={13} />{" "}
              {i18n.t("La preservación del capital guía cada decisión.")}
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}

function Service({ name, status }: { name: string; status?: string }) {
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
function EventList({ events }: { events?: z.infer<typeof eventsSchema> }) {
  useTranslation();
  if (!events) return <p className="muted">{i18n.t("Cargando actividad…")}</p>;
  if (!events.length)
    return (
      <p className="muted">{i18n.t("Todavía no hay actividad registrada.")}</p>
    );
  return (
    <div className="event-list">
      {events.map((event) => (
        <div key={event.id} className="event-row">
          <span className="event-icon">
            <Activity size={15} />
          </span>
          <div>
            <strong>{event.event.replaceAll("_", " ")}</strong>
            <small>{event.message}</small>
          </div>
          <time>
            {new Date(event.timestamp * 1000).toLocaleTimeString(
              i18n.resolvedLanguage,
              {
                timeZone: "UTC",
                hour: "2-digit",
                minute: "2-digit",
              },
            )}{" "}
            UTC
          </time>
        </div>
      ))}
    </div>
  );
}
