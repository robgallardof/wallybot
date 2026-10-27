<a id="top"></a>

<div align="center">

<p>
  <a href="README.md"><img alt="Español" src="https://img.shields.io/badge/Idioma-Español-c60b1e?style=for-the-badge"></a>
  <a href="README.en.md"><img alt="English" src="https://img.shields.io/badge/Language-English-1f6feb?style=for-the-badge"></a>
</p>

<h1><img src="assets/readme-builder/icons/bot.svg" width="20" height="20" alt="" /> WallyBot</h1>

<h3>Tu centro autoalojado de análisis, cartera y trading con IA</h3>

<p><b>Datos de mercado · Propuestas explicadas · Tu aprobación · Controles de riesgo</b></p>

<p>
  <a href="https://github.com/robgallardof/wallybot/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/robgallardof/wallybot/ci.yml?branch=main&label=CI&logo=githubactions&logoColor=white"></a>
  <a href="https://github.com/robgallardof/wallybot/commits/main"><img alt="Último commit" src="https://img.shields.io/github/last-commit/robgallardof/wallybot?label=%C3%BAltimo%20commit&logo=git&logoColor=white"></a>
  <img alt="Tamaño" src="https://img.shields.io/github/repo-size/robgallardof/wallybot?label=tama%C3%B1o">
  <img alt="Lenguaje principal" src="https://img.shields.io/github/languages/top/robgallardof/wallybot">
  <a href="https://github.com/robgallardof/wallybot/stargazers"><img alt="Estrellas" src="https://img.shields.io/github/stars/robgallardof/wallybot?style=flat&logo=github"></a>
</p>

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white">
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white">
  <img alt="React" src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white">
  <img alt="Redis" src="https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white">
  <img alt="Kraken" src="https://img.shields.io/badge/Kraken-Spot-5741D9?logo=kraken&logoColor=white">
  <img alt="Binance" src="https://img.shields.io/badge/Binance-Spot-F0B90B?logo=binance&logoColor=black">
  <img alt="Pruebas" src="https://img.shields.io/badge/pruebas-971%20backend%20%C2%B7%2019%20navegador-2ea44f">
</p>

<p>
  <a href="#-inicio-rápido"><b>Inicio rápido</b></a> ·
  <a href="#-configura-tu-cuenta-real"><b>Trading real</b></a> ·
  <a href="#-cómo-funciona"><b>Arquitectura</b></a> ·
  <a href="#-documentación"><b>Documentación</b></a>
</p>

</div>

---

WallyBot reúne mercados, análisis asistido por IA, seguimiento de cartera y ejecución controlada en una aplicación que alojas tú. Los analistas preparan propuestas **BUY, HOLD, SELL o REDUCE** con explicación y vencimiento. **Tú decides qué aprobar**; los controles deterministas vuelven a comprobar cada operación antes de enviarla al exchange.

> [!IMPORTANT]
> **Trading real disponible: Kraken spot (USD, BTC/XBT, ETH) o Binance spot (USDT, BTC, ETH).** Cada operación requiere la aprobación del administrador con MFA. La IA nunca ejecuta órdenes, y no existen retiros, transferencias ni apalancamiento.

<a id="-configura-tu-cuenta-real"></a>

## <img src="assets/readme-builder/icons/lock.svg" width="20" height="20" alt="" /> Configura tu cuenta real

| Paso | Dónde | Qué hacer |
| :---: | --- | --- |
| **1** | Kraken o Binance | Crea una clave API **exclusiva para WallyBot**. **Kraken:** consultar fondos, órdenes abiertas/cerradas, crear/modificar y cancelar/cerrar órdenes; sin depósitos, retiros, transferencias ni earn. **Binance:** «System generated», solo *Enable Reading* y *Enable Spot & Margin Trading*, restringida a la IP pública de tu PC; sin retiros, transferencias, margen ni futuros, y sin pagar comisiones con BNB. |
| **2** | **Conexiones** | Elige BINANCE, marca trading spot real, y pega la clave y la clave privada. Si algo falla, el mensaje explica qué corregir. Vincular no envía órdenes. |
| **3** | **Configuración → Análisis de IA** | Comprueba que Codex y Claude aparezcan como «Disponible». |
| **4** | **Configuración → Operaciones con dinero real** | Indica máximo por operación, exposición total y pérdida diaria (USDT en Binance) y la variación de precio (0,01–2 %). Escribe `LIVE` y confirma con MFA. |
| **5** | **Portafolio** | Revisa la «Cuenta real Binance»: saldos verificados, órdenes y cantidades ejecutadas. En Binance los importes van en USDT. |
| **6** | **Inteligencia → Propuestas** | Revisa cada propuesta, confirma «dinero real» y aprueba. Cada aprobación es individual y de un solo uso. |

> [!TIP]
> Si un analista aparece como **No disponible**, ejecuta `claude auth login` o `codex login` en una terminal de esta PC. WallyBot nunca desactiva un analista ni la exigencia de coincidencia por su cuenta: si prefieres usar solo uno, desmárcalo tú junto con «Exigir coincidencia».

> [!CAUTION]
> Las claves se introducen en tu instalación y se guardan cifradas. **Nunca compartas claves API ni frases semilla por chat ni en el repositorio.**

Más detalle en la [guía completa de trading real](docs/runbooks/real-spot-trading.md): permisos, errores frecuentes, recuperación y causas de bloqueo.

<a id="-qué-puedes-hacer"></a>

## <img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> Qué puedes hacer

<table>
  <tr>
    <td width="50%" valign="top">
      <h4><img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> Mercados</h4>
      Cotizaciones públicas de Binance con validación de origen, antigüedad y diferencial.
    </td>
    <td width="50%" valign="top">
      <h4><img src="assets/readme-builder/icons/cpu.svg" width="20" height="20" alt="" /> Analistas IA</h4>
      Codex y Claude locales, consenso configurable y disponibilidad visible por analista.
    </td>
  </tr>
  <tr>
    <td valign="top">
      <h4><img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> Propuestas</h4>
      Explicación, riesgos, vencimiento, aprobación con MFA, rechazo y simulación.
    </td>
    <td valign="top">
      <h4><img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> Cuenta real</h4>
      Credenciales cifradas, saldos verificados y órdenes spot IOC en Kraken o Binance.
    </td>
  </tr>
  <tr>
    <td valign="top">
      <h4><img src="assets/readme-builder/icons/shield.svg" width="20" height="20" alt="" /> Riesgo</h4>
      Límites por operación, exposición y pérdida diaria; conciliación y bloqueo ante discrepancias.
    </td>
    <td valign="top">
      <h4><img src="assets/readme-builder/icons/chart.svg" width="20" height="20" alt="" /> Cartera</h4>
      Seguimiento real, contabilidad FIFO y resultados de operaciones simuladas.
    </td>
  </tr>
  <tr>
    <td valign="top">
      <h4><img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> Telegram</h4>
      Resúmenes y enlaces de revisión vinculados al propietario; nunca ejecutan nada.
    </td>
    <td valign="top">
      <h4><img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> Investigación</h4>
      Backtests y procesos de investigación aislados de la ejecución.
    </td>
  </tr>
  <tr>
    <td valign="top">
      <h4><img src="assets/readme-builder/icons/settings.svg" width="20" height="20" alt="" /> Operación</h4>
      Auditoría, heartbeats de servicios, copias cifradas y recuperación verificada.
    </td>
    <td valign="top">
      <h4><img src="assets/readme-builder/icons/globe.svg" width="20" height="20" alt="" /> Interfaz</h4>
      Español e inglés, tema claro/oscuro y diseño adaptable a móvil.
    </td>
  </tr>
</table>

<a id="-inicio-rápido"></a>

## <img src="assets/readme-builder/icons/rocket.svg" width="20" height="20" alt="" /> Inicio rápido

Necesitas **Docker con Compose** y **Python 3.12+**. Para desarrollo y analistas locales: **uv**, **Node.js 22+**, **pnpm 10.11** y las CLI de IA que quieras usar.

```sh
git clone https://github.com/robgallardof/wallybot.git
cd wallybot
python scripts/bootstrap.py
docker compose up -d --build
```

1. Abre **[localhost:3333/setup](http://localhost:3333/setup)**.
2. Consulta el token generado en `.secrets/bootstrap_token` directamente en tu equipo.
3. Crea tu administrador, vincula tu autenticador y guarda los códigos de recuperación.
4. Entra al panel y configura tus conexiones y preferencias.

No hay cuenta predeterminada. El inicializador conserva los secretos y la configuración existentes, y el sistema arranca en **OBSERVE** hasta que actives funciones desde la interfaz.

<details>
<summary><b><img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> Windows: servicios + analista nativo</b></summary>

<br>

Después de preparar las dependencias y las CLI locales:

```powershell
./scripts/start_wallybot.ps1
```

Inicia los servicios Docker y el analista nativo. Consulta la [guía del analista local](docs/runbooks/native-ai-worker.md). La instalación estándar escucha en `127.0.0.1:3333`; para acceso remoto usa la [guía de despliegue con HTTPS](DEPLOYMENT.md).

</details>

<a id="-alcance-actual"></a>

## <img src="assets/readme-builder/icons/target.svg" width="20" height="20" alt="" /> Alcance actual

- La ejecución real admite **Kraken spot USD/BTC/ETH** y **Binance spot USDT/BTC/ETH** con órdenes límite IOC y aprobación por operación. El analista estudia el mercado del exchange de tu cuenta real.
- Stops y objetivos son **avisos de revisión**; no generan órdenes protectoras automáticas.
- Cambios externos en la cuenta que no cuadren con la contabilidad **bloquean** la ejecución hasta revisarlos. El coste histórico de posiciones importadas no se inventa.
- Las pruebas locales no sustituyen una validación con una cuenta financiada ni demuestran rentabilidad.

Restricciones y evolución prevista: [RISK.md](RISK.md), [mandato del producto](docs/PRODUCT-MANDATE.md) y [trabajo pendiente](docs/PENDING.md).

<a id="-cómo-funciona"></a>

## <img src="assets/readme-builder/icons/globe.svg" width="20" height="20" alt="" /> Cómo funciona

<details>
<summary>Diagrama técnico</summary>

```mermaid
flowchart LR
    M[Mercados y contexto] --> A[Analistas IA]
    A --> P[Propuesta explicada]
    P --> U[Tu revisión y MFA]
    U --> R[Mandato y riesgo determinista]
    R --> K[Kraken o Binance spot]
    R --> S[Simulación]
    K --> C[Conciliación y cartera]
    S --> C
    C --> D[Panel y auditoría]
```

</details>

**La IA propone; la aprobación autenticada y los controles de riesgo autorizan.** Los procesos de investigación y los analistas no tienen acceso a las credenciales de trading. Telegram lleva a la revisión web: un enlace o comando nunca envía una operación.

| Capa | Tecnología | Ubicación |
| --- | --- | --- |
| <img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> Interfaz | Next.js, React, TypeScript | `apps/web` |
| <img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> API | FastAPI, Pydantic | `apps/api` |
| ⏱️ Procesos | Worker, scheduler, investigación | `apps/` |
| <img src="assets/readme-builder/icons/cpu.svg" width="20" height="20" alt="" /> Analistas locales | CLI de Codex / Claude | `apps/ai_worker` |
| <img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> Núcleo | Dominio, aplicación, infraestructura | `wallybot/` |
| <img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> Persistencia | PostgreSQL, SQLAlchemy async, Alembic | `migrations/` |
| <img src="assets/readme-builder/icons/repeat.svg" width="20" height="20" alt="" /> Coordinación | Redis; bloqueos y nonces persistentes | — |

<a id="-copias-de-seguridad"></a>

## <img src="assets/readme-builder/icons/database.svg" width="20" height="20" alt="" /> Copias de seguridad

```sh
uv run python scripts/backup.py create
uv run python scripts/backup.py verify
```

Las copias se cifran en `backups/` (excluido del repositorio) y `verify` las restaura en un PostgreSQL aislado. Guarda la clave de respaldo fuera del equipo y sigue la [guía de recuperación](docs/runbooks/recovery.md).

<a id="️-desarrollo-y-verificación"></a>

## <img src="assets/readme-builder/icons/settings.svg" width="20" height="20" alt="" /> Desarrollo y verificación

<details>
<summary><b>Entorno híbrido de desarrollo</b></summary>

<br>

```sh
uv sync --frozen
pnpm --dir apps/web install --frozen-lockfile
uv run python scripts/dev.py
```

Detén antes la aplicación Docker completa para evitar conflictos de puerto. El modo híbrido mantiene la infraestructura en Docker y ejecuta los procesos de aplicación en el equipo.

</details>

<details>
<summary><b>Pruebas, tipos y lint</b></summary>

<br>

```sh
uv run pytest tests/unit tests/property tests/contract tests/integration
uv run ruff check apps wallybot migrations scripts tests
uv run pyright wallybot apps/api apps/worker apps/scheduler apps/research_worker apps/ai_worker
pnpm --dir apps/web exec playwright install chromium
WALLY_E2E_PRODUCTION=1 pnpm --dir apps/web test:e2e
```

Las pruebas de integración requieren Docker. En Windows, si el cliente no detecta Docker Desktop, configura `DOCKER_HOST=npipe:////./pipe/dockerDesktopLinuxEngine` en la terminal de pruebas.

</details>

> [!NOTE]
> **Verificación local del 12 de octubre de 2026:** 971 pruebas de backend (PostgreSQL/Redis reales y desechables) y 19 pruebas de navegador en modo producción aprobadas; comprobación de tipos sin errores. Las pruebas del exchange usan respuestas controladas. Consulta [la evidencia y sus límites](docs/stats/testing.md).

<a id="-documentación"></a>

## <img src="assets/readme-builder/icons/book.svg" width="20" height="20" alt="" /> Documentación

| Guía | Contenido |
| --- | --- |
| <img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> [Trading real](docs/runbooks/real-spot-trading.md) | Kraken, Binance, límites, aprobación, errores y conciliación |
| <img src="assets/readme-builder/icons/cpu.svg" width="20" height="20" alt="" /> [Analistas locales](docs/runbooks/native-ai-worker.md) | CLI, disponibilidad, arranque y diagnóstico |
| <img src="assets/readme-builder/icons/target.svg" width="20" height="20" alt="" /> [Mandato del producto](docs/PRODUCT-MANDATE.md) | Objetivos, asignación y decisiones del operador |
| <img src="assets/readme-builder/icons/layers.svg" width="20" height="20" alt="" /> [Arquitectura](ARCHITECTURE.md) | Límites entre procesos y contratos |
| <img src="assets/readme-builder/icons/lock.svg" width="20" height="20" alt="" /> [Seguridad](SECURITY.md) | Autenticación, permisos y aislamiento de secretos |
| <img src="assets/readme-builder/icons/shield.svg" width="20" height="20" alt="" /> [Riesgo](RISK.md) | Controles de capital y ejecución |
| <img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> [Datos](DATA.md) | Contabilidad, consistencia y calidad |
| <img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> [Despliegue](DEPLOYMENT.md) | Instalación, operación y acceso remoto |
| <img src="assets/readme-builder/icons/check.svg" width="20" height="20" alt="" /> [Pruebas](TESTING.md) | Invariantes y criterios de aceptación |
| <img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> [Decisiones](docs/adr/README.md) | Motivos y alcance de las decisiones técnicas |
| <img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> [Diagramas](docs/diagrams/README.md) | Flujos de datos, órdenes y recuperación |

---

<div align="center">

<b>Análisis con contexto. Decisiones bajo tu control.</b>

<sub>Hecho para autoalojarse · Sin retiros · Sin órdenes directas de la IA</sub>

<br><br>

<a href="#top">⬆️ Volver arriba</a>

</div>

<p align="center"><a href="#top">Volver al inicio</a></p>

<!-- readme-builder:signature:start -->
<p align="center"><a href="https://github.com/robgallardof"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/readme/brand/signature-es-dark.svg" /><img src="assets/readme/brand/signature-es-light.svg" alt="WallyBot / Roberto Gallardo" width="360" /></picture></a></p>
<!-- readme-builder:signature:end -->
