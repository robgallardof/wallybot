import { useTranslation } from "react-i18next";
import i18n from "../../../lib/i18n";

const areas = [
  ["/markets", "Mercados", "Datos públicos, cotizaciones, spreads y calidad. Es el punto de partida para observar, no una recomendación."],
  ["/connections", "Conexiones", "Registra proveedores o wallets de solo lectura. Las credenciales se cifran; WallyBot no recibe permisos de retiro."],
  ["/intelligence", "Inteligencia", "Reúne señales, wallets, riesgo de tokens y el consenso de Codex y Claude para que revises evidencia."],
  ["/research", "Investigación", "Ejecuta backtests y trabajos de investigación aislados. Un resultado no se transforma en una orden."],
  ["/portfolio", "Portafolio", "Muestra tu libro PAPER: saldo, operaciones simuladas, ganancias/pérdidas y el origen de cada operación aprobada por la IA."],
  ["/risk", "Riesgo", "Expone breakers y controles. Pausar impide nuevas decisiones; las operaciones sensibles exigen MFA."],
  ["/settings", "Configuración", "Elegí qué analistas usar, si exigís consenso, tu distribución, avisos y vinculá Telegram mediante un código de un solo uso."],
] as const;

function ArchitectureDiagram() {
  return <svg className="architecture-diagram" viewBox="0 0 920 330" role="img" aria-label={i18n.t("Arquitectura de WallyBot")}>
    <path className="architecture-path" d="M180 86H265M390 86H475M600 86H690M282 135V210M502 135V210M708 135V210" />
    <g className="architecture-node"><rect x="32" y="48" width="148" height="76" rx="14" /><text x="50" y="79">Fuentes</text><text className="architecture-subtext" x="50" y="102">Mercados · wallets</text></g>
    <g className="architecture-node architecture-node-accent"><rect x="265" y="48" width="125" height="76" rx="14" /><text x="283" y="79">Calidad</text><text className="architecture-subtext" x="283" y="102">Validación</text></g>
    <g className="architecture-node"><rect x="475" y="48" width="125" height="76" rx="14" /><text x="493" y="79">Analistas</text><text className="architecture-subtext" x="493" y="102">Codex · Claude</text></g>
    <g className="architecture-node"><rect x="690" y="48" width="190" height="76" rx="14" /><text x="708" y="79">Tu centro de control</text><text className="architecture-subtext" x="708" y="102">Decisión humana</text></g>
    <g className="architecture-node"><rect x="205" y="210" width="155" height="76" rx="14" /><text x="223" y="241">Investigación</text><text className="architecture-subtext" x="223" y="264">Backtests aislados</text></g>
    <g className="architecture-node architecture-node-accent"><rect x="425" y="210" width="155" height="76" rx="14" /><text x="443" y="241">Simulación</text><text className="architecture-subtext" x="443" y="264">Sólo si la activás</text></g>
    <g className="architecture-node"><rect x="645" y="210" width="155" height="76" rx="14" /><text x="663" y="241">Alertas</text><text className="architecture-subtext" x="663" y="264">Telegram · auditoría</text></g>
  </svg>;
}

export function DocsPage() {
  useTranslation();
  return <div className="docs-stack">
    <article className="panel docs-hero docs-hero-modern"><div className="docs-solid-mark">W</div><div><p className="eyebrow">{i18n.t("EMPEZÁ POR AQUÍ")}</p><h2>{i18n.t("Cómo funciona realmente WallyBot")}</h2><p className="muted">{i18n.t("Una guía del producto, no del repositorio: qué entra, qué valida el sistema, qué puede simular y qué siempre queda bajo tu control.")}</p></div><a className="button button-primary" href="#primeros-pasos">{i18n.t("Ver primeros pasos")}</a></article>

    <article className="panel architecture-panel"><div className="panel-heading"><div><p className="eyebrow">{i18n.t("ARQUITECTURA")}</p><h2>{i18n.t("Del dato a tu decisión")}</h2></div><span className="subtle-pill">OBSERVE · CONSENSO</span></div><p className="muted">{i18n.t("Cada capa tiene una responsabilidad: los datos se validan, Codex y Claude reciben el mismo contexto y sólo una coincidencia crea una propuesta. Vos decidís; la simulación está desactivada hasta activarla explícitamente. Ninguna parte de WallyBot puede retirar fondos.")}</p><ArchitectureDiagram /><div className="architecture-legend"><span><i />{i18n.t("Flujo de datos")}</span><span><i />{i18n.t("Control y simulación")}</span><span>{i18n.t("La decisión final es tuya")}</span></div></article>

    <section className="docs-explainer-grid" aria-label={i18n.t("Capas de WallyBot")}>
      <article><span>01</span><h3>{i18n.t("Observar")}</h3><p>{i18n.t("Mercados, wallets y proveedores aportan información; una fuente fallida se marca como fallida, no como válida.")}</p></article>
      <article><span>02</span><h3>{i18n.t("Contrastar")}</h3><p>{i18n.t("Codex y Claude revisan el mismo contexto. Si uno mantiene, falla, propone comprar mientras el otro vende o discrepa de forma material, WallyBot no crea una propuesta.")}</p></article>
      <article><span>03</span><h3>{i18n.t("Investigar")}</h3><p>{i18n.t("Backtests y agentes de investigación producen evidencia reproducible, no autorizaciones de compra.")}</p></article>
      <article><span>04</span><h3>{i18n.t("Decidir")}</h3><p>{i18n.t("OBSERVE solo mira. PAPER es una simulación opcional que sólo aparece si la activás en Configuración; ninguno mueve fondos externos.")}</p></article>
    </section>

    <article className="panel docs-panel" id="primeros-pasos"><div className="panel-heading"><div><p className="eyebrow">{i18n.t("PRIMEROS PASOS")}</p><h2>{i18n.t("Configurá tu espacio en este orden")}</h2></div></div><ol className="setup-steps">
      <li><span>01</span><div><strong>{i18n.t("Protegé tu acceso")}</strong><p>{i18n.t("Configurá MFA y guardá tus códigos de recuperación fuera de WallyBot.")}</p></div></li>
      <li><span>02</span><div><strong>{i18n.t("Conectá tu cuenta")}</strong><p>{i18n.t("Para Binance spot usa una clave API con consulta y trading spot únicamente, restringida a tu IP. Sin permisos de retiro ni transferencia. Las otras fuentes son de consulta.")}</p></div></li>
      <li><span>03</span><div><strong>{i18n.t("Revisá mercado e inteligencia")}</strong><p>{i18n.t("Confirmá calidad, liquidez y contexto antes de investigar una hipótesis.")}</p></div></li>
      <li><span>04</span><div><strong>{i18n.t("Configurá límites y analistas")}</strong><p>{i18n.t("Define tus máximos por operación, exposición y pérdida diaria. Activa LIVE con MFA y confirma cada propuesta. Codex y Claude analizan; PAPER es una prueba opcional.")}</p></div></li>
      <li><span>05</span><div><strong>{i18n.t("Vinculá alertas")}</strong><p>{i18n.t("Guardá el token de Telegram y enviá el código /start que te muestra WallyBot. El Chat ID se vincula solo.")}</p></div></li>
    </ol></article>

    <article className="panel docs-commands-panel"><div><p className="eyebrow">TELEGRAM</p><h2>{i18n.t("Comandos de tu bot")}</h2><p className="muted">{i18n.t("Escribí /help o /commands en el chat vinculado para ver esta lista desde Telegram. Las propuestas nuevas llegan agrupadas según la frecuencia que elegís; Telegram sólo avisa y nunca ejecuta.")}</p></div><div className="docs-command-list"><code>/status</code><span>{i18n.t("Estado y entorno")}</span><code>/breakers</code><span>{i18n.t("Controles activos")}</span><code>/portfolio</code><span>{i18n.t("Último resumen de equity")}</span><code>/proposals</code><span>{i18n.t("Ideas recientes; revisalas con MFA en WallyBot")}</span><code>/approve ID</code><span>{i18n.t("Abren la propuesta para revisión y confirmación con MFA en la web")}</span><code>/reject ID</code><span>{i18n.t("Abren la propuesta para revisión y confirmación con MFA en la web")}</span><code>/simulate ID</code><span>{i18n.t("Abren la propuesta para revisión y confirmación con MFA en la web")}</span><code>/withdrawal</code><span>{i18n.t("Resultado realizado, sólo como contexto; nunca retira fondos")}</span><code>/pause · /resume</code><span>{i18n.t("Solicitan confirmación por MFA en la web")}</span></div></article>

    <section className="docs-areas" aria-label={i18n.t("Áreas de WallyBot")}>{areas.map(([href, title, description], index) => <a className="docs-area-card" href={href} key={href}><span className="docs-area-number">{String(index + 1).padStart(2, "0")}</span><h3>{i18n.t(title)}</h3><p>{i18n.t(description)}</p><small>{i18n.t("Abrir sección")} →</small></a>)}</section>

    <article className="panel docs-safety-panel"><span className="docs-solid-lock">◆</span><div><p className="eyebrow">{i18n.t("LÍMITE DE SEGURIDAD")}</p><h2>{i18n.t("WallyBot no puede retirar ni transferir fondos.")}</h2><p>{i18n.t("LIVE permite compras y ventas spot aprobadas con dinero real. La IA no ejecuta órdenes ni recibe claves. No hay retiros, transferencias, deuda, apalancamiento ni semillas de wallet.")}</p></div><a className="button button-outline" href="/settings">{i18n.t("Ver configuración")}</a></article>
  </div>;
}
