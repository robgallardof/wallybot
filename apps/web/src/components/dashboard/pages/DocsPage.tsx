import { useTranslation } from "react-i18next";
import { BookOpen, GitBranch, Rocket, Waypoints } from "lucide-react";
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
            {i18n.t("Requisitos: Docker Engine/Desktop con Compose y Python 3.12+.")}
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
          <code>{"uv tool install graphifyy\ngraphify . --wiki\ngraphify query \"¿cómo se conecta el scanner de mercado con el API?\""}</code>
        </pre>
        <p className="muted">
          {i18n.t(
            "El primer comando genera un diagrama interactivo (graphify-out/graph.html) y un reporte en texto plano (graphify-out/GRAPH_REPORT.md) que podés abrir en el navegador o en tu editor. Es una herramienta de desarrollo opcional, no un requisito para correr tu bot.",
          )}
        </p>
      </section>
    </article>
  );
}
