import { useTranslation } from "react-i18next";
import {
  BellRing,
  BookOpen,
  Brain,
  Cable,
  ChartNoAxesCombined,
  CircleDollarSign,
  ExternalLink,
  FlaskConical,
  GitBranch,
  ShieldCheck,
  WalletCards,
} from "lucide-react";
import i18n from "../../../lib/i18n";

const areas = [
  {
    href: "/markets",
    icon: ChartNoAxesCombined,
    title: "Mercados",
    description:
      "Consulta cotizaciones, calidad de datos y los instrumentos disponibles para análisis.",
  },
  {
    href: "/connections",
    icon: Cable,
    title: "Conexiones",
    description:
      "Registra tus proveedores y direcciones públicas para consultar datos de tu propio espacio.",
  },
  {
    href: "/intelligence",
    icon: Brain,
    title: "Inteligencia",
    description:
      "Revisa señales, actividad de wallets y calidad de proveedores antes de tomar decisiones.",
  },
  {
    href: "/research",
    icon: FlaskConical,
    title: "Investigación",
    description:
      "Prueba hipótesis y compara resultados sin convertir una señal en una orden real.",
  },
  {
    href: "/risk",
    icon: ShieldCheck,
    title: "Riesgo",
    description:
      "Consulta los límites y pausa el sistema cuando necesites revisar una condición.",
  },
  {
    href: "/settings",
    icon: BellRing,
    title: "Configuración",
    description:
      "Elige OBSERVE o PAPER y configura alertas privadas de Telegram.",
  },
] as const;

export function DocsPage() {
  useTranslation();
  return (
    <div className="docs-stack">
      <article className="panel docs-hero">
        <span className="docs-hero-icon">
          <BookOpen size={22} />
        </span>
        <div>
          <p className="eyebrow">{i18n.t("Documentación y primeros pasos")}</p>
          <h2>{i18n.t("Todo tu espacio, explicado.")}</h2>
          <p className="muted">
            {i18n.t(
              "WallyBot te ayuda a observar, investigar y organizar decisiones. Esta guía te indica qué hace cada sección y cuál es el siguiente paso seguro.",
            )}
          </p>
        </div>
      </article>

      <article className="panel docs-safety-panel">
        <span>
          <GitBranch size={21} />
        </span>
        <div>
          <p className="eyebrow">{i18n.t("Explorá el código")}</p>
          <h2>{i18n.t("Repositorio oficial de Graphify")}</h2>
          <p>
            {i18n.t(
              "La herramienta que este repo usa para navegar su propio código como un grafo de conocimiento. Instrucciones de instalación y documentación completa viven ahí, no acá.",
            )}
          </p>
        </div>
        <a
          className="button button-outline"
          href="https://github.com/Graphify-Labs/graphify"
          target="_blank"
          rel="noopener noreferrer"
        >
          <ExternalLink size={16} /> {i18n.t("Ver en GitHub")}
        </a>
      </article>

      <article className="panel docs-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">{i18n.t("Primera configuración")}</p>
            <h2>{i18n.t("Empezá en cinco pasos")}</h2>
          </div>
          <span className="subtle-pill">{i18n.t("TU INSTANCIA PRIVADA")}</span>
        </div>
        <ol className="setup-steps">
          <li>
            <span>01</span>
            <div>
              <strong>{i18n.t("Protegé tu acceso")}</strong>
              <p>
                {i18n.t(
                  "Crea tu usuario administrador, activa el autenticador y guarda los códigos de recuperación.",
                )}
              </p>
            </div>
          </li>
          <li>
            <span>02</span>
            <div>
              <strong>{i18n.t("Conectá solo para consultar")}</strong>
              <p>
                {i18n.t(
                  "Agrega un exchange, broker o wallet con acceso de lectura. Nunca habilites permisos de retiro.",
                )}
              </p>
            </div>
          </li>
          <li>
            <span>03</span>
            <div>
              <strong>{i18n.t("Revisá los mercados")}</strong>
              <p>
                {i18n.t(
                  "Explora precios, filtros y calidad de los datos antes de investigar una oportunidad.",
                )}
              </p>
            </div>
          </li>
          <li>
            <span>04</span>
            <div>
              <strong>{i18n.t("Probá tu idea")}</strong>
              <p>
                {i18n.t(
                  "Usá Investigación para medir una estrategia. PAPER simula órdenes con datos reales, sin dinero real.",
                )}
              </p>
            </div>
          </li>
          <li>
            <span>05</span>
            <div>
              <strong>{i18n.t("Elegí cómo recibir avisos")}</strong>
              <p>
                {i18n.t(
                  "Configurá Telegram si querés recibir alertas en tu chat privado.",
                )}
              </p>
            </div>
          </li>
        </ol>
      </article>

      <section className="docs-areas" aria-label={i18n.t("Áreas de WallyBot")}>
        {areas.map(({ href, icon: Icon, title, description }) => (
          <a className="docs-area-card" href={href} key={href}>
            <span>
              <Icon size={19} />
            </span>
            <h3>{i18n.t(title)}</h3>
            <p>{i18n.t(description)}</p>
            <small>{i18n.t("Abrir sección")} →</small>
          </a>
        ))}
      </section>

      <article className="panel docs-safety-panel">
        <span>
          <ShieldCheck size={21} />
        </span>
        <div>
          <p className="eyebrow">{i18n.t("Límite de seguridad")}</p>
          <h2>{i18n.t("La información no mueve tu dinero.")}</h2>
          <p>
            {i18n.t(
              "OBSERVE solo lee mercados reales. PAPER simula operaciones. WallyBot no puede retirar fondos ni transferir activos desde esta instancia.",
            )}
          </p>
        </div>
        <a className="button button-outline" href="/settings">
          <CircleDollarSign size={16} /> {i18n.t("Ver configuración")}
        </a>
      </article>

      <article className="panel docs-wallet-note">
        <WalletCards size={19} />
        <p>
          {i18n.t(
            "Cada conexión, wallet y configuración pertenece a tu cuenta. Otros usuarios no ven ni pueden modificar tu actividad.",
          )}
        </p>
      </article>
    </div>
  );
}
