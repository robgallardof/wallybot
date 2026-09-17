import { useTranslation } from "react-i18next";
import {
  BookOpen,
  ClipboardList,
  ExternalLink,
  FlaskConical,
  GitBranch,
  Rocket,
  Waypoints,
} from "lucide-react";
import i18n from "../../../lib/i18n";

/**
 * Static onboarding page for whoever clones this repo and wants to run their own instance --
 * unlike every other page here, it renders no query data on purpose: this is meant to still be
 * readable the moment the stack first comes up, before setup, PostgreSQL or Redis exist.
 */
export function DocsPage() {
  useTranslation();
  return (
    <article className="panel wide-panel docs-panel">
      <div className="panel-heading">
        <h2>{i18n.t("Documentación y primeros pasos")}</h2>
        <BookOpen size={20} />
      </div>
      <p className="muted">
        {i18n.t(
          "Esta página resume cómo levantar tu propia instancia y dónde encontrar el resto de la documentación en el repositorio. Es contenido fijo, no depende del backend.",
        )}
      </p>

      <section aria-labelledby="docs-first-steps">
        <h3 id="docs-first-steps">
          <Rocket size={16} /> {i18n.t("Primeros pasos")}
        </h3>
        <ol className="docs-steps">
          <li>
            {i18n.t(
              "Requisitos: Docker Engine/Desktop con Compose y Python 3.12+.",
            )}
          </li>
          <li>
            <code>python scripts/bootstrap.py</code>
            {" — "}
            {i18n.t("genera tus secretos locales (nunca los subas al repo).")}
          </li>
          <li>
            <code>docker compose up -d --build</code>
            {" — "}
            {i18n.t("construye y levanta todos los servicios.")}
          </li>
          <li>
            {i18n.t("Abre")} <code>http://localhost:3333/setup</code>
            {", "}
            {i18n.t(
              "lee el token en .secrets/bootstrap_token, crea tu administrador e inscribe tu autenticador (TOTP). Guarda los códigos de recuperación: no se muestran una segunda vez.",
            )}
          </li>
          <li>
            {i18n.t(
              "Por defecto la instancia arranca en modo OBSERVE (solo observa, nunca simula ni ejecuta). Activá el modo PAPER desde",
            )}{" "}
            <strong>{i18n.t("Configuración")}</strong>
            {i18n.t(" si querés que simule operaciones.")}
          </li>
        </ol>
      </section>

      <section aria-labelledby="docs-architecture">
        <h3 id="docs-architecture">
          <Waypoints size={16} /> {i18n.t("Arquitectura, en breve")}
        </h3>
        <p>
          {i18n.t(
            "WallyBot es un monolito modular: procesos independientes (api, worker, scheduler, research_worker, web) que comparten paquetes tipados de dominio/aplicación/infraestructura bajo wallybot/. El dominio (wallybot/domain) nunca importa FastAPI, SQLAlchemy, CCXT ni SDKs de IA -- es una regla de arquitectura, no una preferencia de estilo.",
          )}
        </p>
        <p>
          {i18n.t(
            "El detalle completo vive en archivos Markdown en la raíz del repo, no en esta página: ARCHITECTURE.md (diseño y capas), DATA.md (datos de mercado), SECURITY.md, RISK.md, TESTING.md y DEPLOYMENT.md. Ábrelos directamente en tu editor o en GitHub.",
          )}
        </p>
      </section>

      <section aria-labelledby="docs-graphify">
        <h3 id="docs-graphify">
          <GitBranch size={16} /> {i18n.t("Explorar el código con Graphify")}
        </h3>
        <p>
          {i18n.t(
            "Graphify es una herramienta de línea de comandos (no forma parte del stack que corre en producción) que convierte el repositorio en un grafo de conocimiento navegable -- útil para entender cómo se relacionan los módulos antes de tocar código.",
          )}
        </p>
        <pre className="docs-code">
          <code>{"uv tool install graphifyy\ngraphify . --wiki"}</code>
        </pre>
        <p className="muted">
          {i18n.t(
            "El primer comando genera un diagrama interactivo (graphify-out/graph.html) y un reporte en texto plano (graphify-out/GRAPH_REPORT.md) que podés abrir en el navegador o en tu editor. Es una herramienta de desarrollo opcional, no un requisito para correr tu bot.",
          )}
        </p>
        <a
          className="button button-outline docs-diagram-link"
          href="/architecture.html"
          target="_blank"
          rel="noopener noreferrer"
        >
          <ExternalLink size={16} />
          {i18n.t("Ver diagrama de arquitectura")}
        </a>
        <p className="muted">
          {i18n.t(
            "Snapshot generado con Graphify (graphify export callflow-html): módulos, procesos y cómo se llaman entre sí. Se abre en una pestaña nueva porque es HTML estático servido tal cual, no una página de la app -- se regenera a mano cuando la arquitectura cambia mucho, no en cada build.",
          )}
        </p>
        <p>
          {i18n.t(
            "El uso diario no es solo el build inicial -- es un flujo de cuatro comandos que se repite mientras trabajás:",
          )}
        </p>
        <ol className="docs-steps">
          <li>
            <code>{'graphify query "¿cómo se conecta X con Y?"'}</code>
            {" — "}
            {i18n.t(
              "primera pregunta sobre cualquier duda de arquitectura o relación entre archivos: devuelve un subgrafo acotado, mucho más chico que leer el reporte completo o grepear a mano.",
            )}
          </li>
          <li>
            <code>{'graphify path "A" "B"'}</code>
            {" — "}
            {i18n.t(
              "el camino concreto entre dos símbolos o módulos puntuales.",
            )}
          </li>
          <li>
            <code>{'graphify explain "concepto"'}</code>
            {" — "}
            {i18n.t(
              "un concepto acotado (ej. una entidad de dominio o un flujo) sin todo el grafo alrededor.",
            )}
          </li>
          <li>
            <code>graphify update .</code>
            {" — "}
            {i18n.t(
              "después de modificar código: solo AST, sin costo de API, mantiene el grafo al día para la próxima consulta.",
            )}
          </li>
        </ol>
        <p className="muted">
          {i18n.t(
            "Si usás Claude Code o Codex CLI sobre este repo, ambos ya están instruidos (AGENTS.md) para seguir este mismo flujo antes de leer o grepear archivos fuente a mano.",
          )}
        </p>
      </section>

      <section aria-labelledby="docs-testing">
        <h3 id="docs-testing">
          <FlaskConical size={16} /> {i18n.t("Pruebas y calidad")}
        </h3>
        <pre className="docs-code">
          <code>
            {
              'uv run pytest -m "not integration"\nuv run pytest -m integration\nuv run ruff check .\nuv run pyright'
            }
          </code>
        </pre>
        <p className="muted">
          {i18n.t(
            "Las pruebas de integración necesitan Docker corriendo (levantan Postgres y Redis descartables vía testcontainers) -- las que no son de integración no. Ambos comandos de lint/tipos deben quedar limpios antes de dar por terminado un cambio.",
          )}
        </p>
      </section>

      <section aria-labelledby="docs-status">
        <h3 id="docs-status">
          <ClipboardList size={16} /> {i18n.t("Estado actual del proyecto")}
        </h3>
        <p>
          {i18n.t(
            "Esta página no refleja qué falta o qué se rompió último -- eso vive en dos lugares que se actualizan con cada sesión de desarrollo, humana o asistida por IA:",
          )}
        </p>
        <ul className="docs-steps">
          <li>
            <code>docs/PENDING.md</code>
            {" — "}
            {i18n.t(
              "backlog de producto por fase, con criterios de aceptación explícitos y el orden de entrega recomendado.",
            )}
          </li>
          <li>
            <code>.ai/CURRENT.md</code>
            {i18n.t(" y ")}
            <code>.ai/HANDOFF.md</code>
            {" — "}
            {i18n.t(
              "la tarea activa y el estado que dejó la última sesión para quien continúe sin haber visto la conversación.",
            )}
          </li>
        </ul>
      </section>
    </article>
  );
}
