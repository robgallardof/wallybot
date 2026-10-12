# ADR-017: IA genera propuestas; el operador aprueba cada operación

Status: accepted, 2026-09-23.

## Context

El producto buscado es un gestor de cartera: analiza periódicamente contexto de mercado, cartera,
wallets y señales públicas para sugerir BUY, HOLD, SELL/REDUCE o una recomendación de retiro. No
es un agente de transferencias ni una máquina de órdenes sin supervisión.

ADR-016 introdujo una ruta que convertía una propuesta de IA directamente en una orden PAPER y
eludía los controles de mandato y riesgo. Ese comportamiento contradice las garantías de
`AGENTS.md`, `SECURITY.md`, ADR-007 y el flujo de aprobación que el operador describió para
Telegram.

## Decision

- La IA produce una propuesta estructurada, fechada, explicable y con caducidad.
- Los analistas configurados reciben el mismo contexto inmutable. Cuando el operador activa
  consenso estricto, una ausencia, HOLD o desacuerdo material entre Codex y Claude falla cerrado:
  no se persiste una propuesta.
- WallyBot envía un resumen de propuestas relevantes por Telegram conforme a una cadencia
  configurable, y alerta ante cambios importantes sin bombardear al usuario.
- El operador aprueba o rechaza cada propuesta desde una superficie autenticada. La aprobación es
  de un único uso y expira; antes de una orden se revalida mandato, límites, datos y caducidad.
- La distribución CORE/GROWTH/SPECULATIVE, fuentes permitidas, cadencia y umbrales son por usuario
  y se versionan/auditan. El ejemplo 70/20/10 es un valor inicial configurable, no una regla
  oculta.
- Señales de copy trading son evidencia con procedencia, no órdenes. Un retiro es únicamente una
  recomendación visible/auditable para que el operador actúe fuera de WallyBot.
- No se permite una ruta que conecte una salida de IA directamente con `ExecutionService`.

## Consequences

Se reemplaza la excepción de ejecución directa de ADR-016. El worker de IA puede recopilar
contexto y persistir propuestas, pero no presentar una orden para ejecución hasta que exista una
aprobación humana válida y se cumplan los controles deterministas. Esto conserva PAPER como
simulación verificable y deja LIVE sujeto a sus gates separados.

PAPER permanece desactivado por defecto. El análisis, el consenso y las notificaciones no cambian
el modo de la instancia ni habilitan simulación por efecto secundario.

## Implementación (2026-09-27)

`POST /api/proposals/{id}/approve` confirma primero la aprobación de un solo uso y rechaza con 409
una propuesta caducada. Si la instancia está en OBSERVE queda `OBSERVE_ONLY` sin orden. En PAPER,
`execute_approved_proposal` revalida con datos frescos y el mismo asignador/motor de riesgo, y
solo entonces envía una orden MARKET a la cuenta `paper-ai:<usuario>` mediante su propio
`FakeExchange` (`idempotency_key = proposal:<id>`). El resultado (`FILLED`, `BLOCKED`, `EXPIRED`,
`FAILED`…) y sus motivos se guardan en `trade_proposals` (migración `0040`) y se auditan.

## Operación local y seguimiento (2026-10-08)

El proceso nativo carga su conexión dedicada sin exponerla a las CLI y registra un heartbeat
acotado en PostgreSQL. La migración 0041 retira del rol `wally_ai` los permisos históricos de
órdenes, fills y ledger; la ruta API aprobada sigue siendo el único ejecutor PAPER.

Las CLI trabajan en un directorio temporal, sin variables WALLY ni herramientas de shell/apps;
se comprobó su respuesta real con una solicitud HOLD que no persiste propuestas. Arrancar el
proceso no modifica los controles de análisis/PAPER del operador.

Telegram puede abrir una propuesta propia mediante /approve, /reject o /simulate, pero el comando
y el enlace sólo navegan. La acción sigue ocurriendo exclusivamente en la web autenticada con
MFA, caducidad, uso único y revalidación. El seguimiento de cartera y stop/objetivo es de lectura;
un nivel alcanzado no origina una venta automática. Ver el mandato para las reglas de valoración.
