import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import {
  Activity,
  BookOpen,
  Brain,
  Cable,
  FlaskConical,
  LayoutDashboard,
  LineChart,
  LogOut,
  Menu,
  Settings,
  Settings2,
  ShieldCheck,
  Wallet,
} from "lucide-react";
import i18n from "../../lib/i18n";
import type { meSchema } from "../../lib/dto";
import type { z } from "zod";
import { LanguageSelector } from "../LanguageSelector";
import { ThemeToggle } from "../ThemeToggle";
import { Button } from "../ui/button";

const navigation = [
  ["docs", "Documentación", BookOpen],
  ["dashboard", "Resumen", LayoutDashboard],
  ["portfolio", "Portafolio", Wallet],
  ["connections", "Conexiones", Cable],
  ["markets", "Mercados", LineChart],
  ["intelligence", "Inteligencia", Brain],
  ["research", "Investigación", FlaskConical],
  ["risk", "Riesgo", ShieldCheck],
  ["events", "Actividad", Activity],
  ["system", "Sistema", Settings2],
  ["settings", "Configuración", Settings],
] as const;

const PAGE_META: Record<string, { eyebrow: string; description: string }> = {
  dashboard: {
    eyebrow: "PANORAMA",
    description: "Lo esencial de tu instancia, sin métricas inventadas.",
  },
  portfolio: {
    eyebrow: "PORTAFOLIO",
    description: "Saldos, actividad y resultados de tu cuenta de simulación.",
  },
  connections: {
    eyebrow: "CONEXIONES",
    description: "Proveedores y wallets de consulta, separados de la ejecución.",
  },
  markets: {
    eyebrow: "MERCADOS",
    description: "Cotizaciones y calidad de datos para investigar con contexto.",
  },
  intelligence: {
    eyebrow: "INTELIGENCIA",
    description: "Señales observables para revisar antes de tomar una decisión.",
  },
  research: {
    eyebrow: "INVESTIGACIÓN",
    description: "Pruebas reproducibles sobre datos históricos; no ejecutan operaciones.",
  },
  risk: {
    eyebrow: "RIESGO",
    description: "Controles que priorizan preservar el capital y revisar excepciones.",
  },
  events: {
    eyebrow: "ACTIVIDAD",
    description: "Registro de eventos y cambios relevantes de tu instancia.",
  },
  system: {
    eyebrow: "SISTEMA",
    description: "Estado de las dependencias y procesos que sostienen WallyBot.",
  },
  settings: {
    eyebrow: "CONFIGURACIÓN",
    description: "Preferencias de tu instancia, simulación y alertas privadas.",
  },
  docs: {
    eyebrow: "GUÍA",
    description: "Qué hace cada sección y cómo empezar de forma segura.",
  },
};

export function DashboardShell({
  user,
  logout,
  page,
  navigate,
  hasError,
  mutationError,
  environment,
  children,
}: {
  user: z.infer<typeof meSchema>;
  logout: () => void;
  page: string;
  navigate: (next: string) => void;
  hasError: boolean;
  mutationError?: string;
  environment?: "OBSERVE" | "PAPER";
  children: ReactNode;
}) {
  useTranslation();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const title = navigation.find(([key]) => key === page)?.[1] ?? "Resumen";
  const meta = PAGE_META[page] ?? PAGE_META.dashboard;
  const showSafetyNotice = ["dashboard", "portfolio", "risk", "settings"].includes(page);

  function selectPage(key: string) {
    setMobileNavOpen(false);
    navigate(key);
  }

  return (
    <div className="app-layout">
      <a className="skip-link" href="#main-content">
        {i18n.t("Saltar al contenido")}
      </a>
      <aside className="sidebar">
        <div className="sidebar-header">
          <a className="brand" href="/dashboard">
            wally<span>bot</span>
            <i />
          </a>
          <Button
            aria-controls="control-navigation"
            aria-expanded={mobileNavOpen}
            aria-label={i18n.t("Abrir navegación")}
            className="mobile-menu-toggle"
            onClick={() => setMobileNavOpen((open) => !open)}
            variant="outline"
          >
            <Menu size={20} />
          </Button>
        </div>
        <div className="workspace">
          <span className="avatar">W</span>
          <div>
            {i18n.t("Mi espacio")}
            <small>{i18n.t("Instancia privada")}</small>
          </div>
          <span className="workspace-dot" />
        </div>
        <p className="nav-caption">{i18n.t("CENTRO DE CONTROL")}</p>
        <nav
          className={mobileNavOpen ? "sidebar-nav mobile-open" : "sidebar-nav"}
          id="control-navigation"
        >
          {navigation.map(([key, label, Icon]) => (
            <button
              key={key}
              className={page === key ? "nav-item active" : "nav-item"}
              onClick={() => selectPage(key)}
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
          <button
            className="user-button"
            onClick={logout}
            aria-label={i18n.t("Cerrar sesión")}
          >
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
              <i /> {environment ?? "OBSERVE"}
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
              <span className="eyebrow">{i18n.t(meta.eyebrow)}</span>
              <h1>{page === "dashboard" ? i18n.t("Una visión clara.") : i18n.t(title)}</h1>
              <p className="muted">{i18n.t(meta.description)}</p>
            </div>
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
          {showSafetyNotice && (
            <div className="notice">
              <ShieldCheck size={19} />
              <div>
                <strong>{i18n.t("Entorno seguro")}</strong>
                <span>
                  {" "}
                  {environment === "PAPER"
                    ? i18n.t("Simulando órdenes con datos de mercado; no se mueven fondos externos.")
                    : i18n.t("Observando mercados reales; todavía no se generan órdenes.")}
                </span>
              </div>
            </div>
          )}
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
