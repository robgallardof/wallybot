import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import {
  Activity,
  FlaskConical,
  LayoutDashboard,
  LineChart,
  LogOut,
  Settings2,
  ShieldCheck,
  Wallet,
} from "lucide-react";
import i18n from "../../lib/i18n";
import type { meSchema } from "../../lib/dto";
import type { z } from "zod";
import { LanguageSelector } from "../LanguageSelector";
import { ThemeToggle } from "../ThemeToggle";

const navigation = [
  ["dashboard", "Resumen", LayoutDashboard],
  ["portfolio", "Portafolio", Wallet],
  ["markets", "Mercados", LineChart],
  ["research", "Investigación", FlaskConical],
  ["risk", "Riesgo", ShieldCheck],
  ["events", "Actividad", Activity],
  ["system", "Sistema", Settings2],
] as const;

export function DashboardShell({
  user,
  logout,
  page,
  navigate,
  hasError,
  mutationError,
  children,
}: {
  user: z.infer<typeof meSchema>;
  logout: () => void;
  page: string;
  navigate: (next: string) => void;
  hasError: boolean;
  mutationError?: string;
  children: ReactNode;
}) {
  useTranslation();
  const title = navigation.find(([key]) => key === page)?.[1] ?? "Resumen";

  return (
    <div className="app-layout">
      <a className="skip-link" href="#main-content">
        {i18n.t("Saltar al contenido")}
      </a>
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
              aria-current={page === key ? "page" : undefined}
            >
              <Icon size={18} />
              {i18n.t(label)}
              {page === key && <span className="nav-dot" />}
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
      <main className="main" id="main-content" tabIndex={-1}>
        <header className="topbar">
          <div className="appearance-controls">
            <LanguageSelector />
            <ThemeToggle />
          </div>
          <span>
            {i18n.t("Espacio de trabajo")}
            <span className="slash">/</span> <strong>{i18n.t(title)}</strong>
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
                {page === "dashboard"
                  ? i18n.t("Una visión clara.")
                  : i18n.t(title)}
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
          {hasError && (
            <p role="alert" className="error">
              {i18n.t(
                "No se pudo actualizar el panel. Comprueba la conexión y los servicios; los datos anteriores pueden estar desactualizados.",
              )}
            </p>
          )}
          {mutationError && (
            <p role="alert" className="error">
              {i18n.t(mutationError)}
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
          {children}
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
