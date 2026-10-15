# WallyBot: tu gestor de cartera asistido

Actualización 2026-10-12: el objetivo solicitado es operar con dinero real. La implementación
LIVE de Binance spot (BTC/USDT y ETH/USDT), con conexión/límites configurados en la UI, MFA y aprobación por operación,
está definida en [ADR-019](adr/019-binance-spot-venue.md), que amplía [ADR-018](adr/018-real-spot-objective.md) y la [guía de activación](runbooks/real-spot-trading.md).
Esto reemplaza las limitaciones PAPER de la implementación anterior descrita más abajo.

Estado: dirección de producto aprobada. Esta guía explica el producto en lenguaje normal; no es
una promesa de rentabilidad ni una autorización para mover fondos sin tu visto bueno.

## La idea en una frase

Conectás las fuentes que ya usás, definís cómo querés repartir tu cartera y WallyBot analiza el
mercado periódicamente. La IA puede recomendar **comprar, mantener, vender/reducir o retirar**;
las compras y ventas se convierten en propuestas auditables y sólo siguen adelante tras tu
autorización. Un retiro nunca es ejecutado por WallyBot: es una recomendación para que vos lo
hagas desde tu banco, broker o wallet.

## Lo que configurás

Cada usuario tiene su propio espacio, conexiones, cartera, preferencias de notificación y
mandato. Desde Configuración podrá elegir, por ejemplo:

| Ajuste | Ejemplo | Qué significa |
| --- | --- | --- |
| Distribución | 70 / 20 / 10 | 70% CORE (más estable), 20% GROWTH (riesgo medio), 10% SPECULATIVE (alto riesgo). Debe sumar 100%. |
| Frecuencia | cada 6 horas | Cada cuánto se revisa mercado, cartera y contexto. No implica mensajes cada vez. |
| Avisos | resumen diario + cambios importantes | Telegram recibe un digest de propuestas nuevas —como máximo cinco por envío— y sólo alertas excepcionales. |
| Fuentes permitidas | Binance, Bitso, wallet pública, broker | Dónde puede observar datos y preparar propuestas. |
| Analistas | Codex + Claude, con consenso estricto | Ambos reciben el mismo contexto; si difieren, WallyBot no crea una propuesta. |
| Aprobación | siempre antes de operar | La IA nunca salta tu aprobación para una orden. |

**CORE** / *base estable*: activos que elegiste como de largo plazo, por ejemplo BTC.
**GROWTH** / *crecimiento*: activos o ETFs con más variación, pero una tesis documentada.
**SPECULATIVE** / *especulativo*: tokens pequeños o nuevas oportunidades; la parte acotada de
mayor riesgo. “Shitcoin” en la interfaz se explicará como activo especulativo, no como garantía.

## Qué analiza WallyBot

El contexto de cada ciclo conserva la fecha y las fuentes: precios y volumen, calidad del dato,
posición actual, compras/ventas anteriores, ganancias, límites del mandato, señales on-chain,
actividad pública de entidades vigiladas, riesgo de token y fiabilidad del proveedor. Las fuentes
de internet o redes son indicios: jamás instrucciones que el modelo pueda ejecutar.

Una propuesta siempre dice qué planea hacer, por qué, importe, activo, horizonte, riesgos,
caducidad y qué información la invalidaría. La UI conserva la bitácora y los resultados posteriores
para poder revisar si la recomendación fue buena o mala.

Una recomendación de **vender o reducir** sólo puede referirse a un activo spot que ya figura en
tu cartera. WallyBot la limita a esa posición: no abre cortos, no usa deuda ni apalancamiento y no
puede transferir ni retirar los activos.

## Comité de análisis local

Codex y Claude se pueden habilitar por separado desde Configuración. WallyBot invoca únicamente
los clientes locales ya autenticados del operador; no pide, almacena ni entrega claves de wallet a
ningún analista. Con **exigir coincidencia** activado —el valor recomendado— ambos deben devolver
una propuesta compatible para el mismo contexto y con precios próximos. Si uno mantiene, falla o
discrepa de forma material —incluyendo que uno quiera comprar y el otro vender— WallyBot conserva
HOLD y no crea una propuesta operativa.

La simulación también empieza desactivada. Sólo aparece al cambiar explícitamente el modo de la
instancia a PAPER en Configuración; aun así no interactúa con un exchange ni mueve dinero.

## Flujo de una decisión

```text
Fuentes conectadas → contexto con fecha → análisis IA/reglas → propuesta
                                                     ↓
                                Telegram: aviso y contexto (sólo lectura)
                                                     ↓
                     WallyBot web + MFA: revisar, aprobar o rechazar
                                                     ↓
                              bitácora y cartera visibles; PAPER sólo si lo activás
```

Una aprobación expira. Si cambió el precio, el contexto o la propuesta caducó, WallyBot pide una
nueva decisión en lugar de reutilizar un “sí” viejo. La cancelación siempre está disponible.

## Trazabilidad en el portafolio

Cuando una propuesta aprobada supera la revalidación y se llena en PAPER, la actividad del
portafolio conserva el identificador de la propuesta que la originó. Así podés volver desde cada
compra o reducción a su razonamiento, riesgos, fecha y resultado registrado. El P&L realizado se
calcula con lotes FIFO sobre fills confirmados; WallyBot no inventa valor no realizado si no tiene
una cotización verificable.

El seguimiento de propuestas muestra la entrada realmente llenada, cantidad, tiempo transcurrido,
stop y objetivo que fueron registrados al decidir. Son niveles de referencia, no órdenes activas
ni instrucciones de transferencia; una propuesta no habilita que WallyBot retire o mueva fondos.

El seguimiento atribuye cierres parciales FIFO a cada entrada, conserva sus comisiones y detiene
el tiempo de tenencia al cerrarse. Muestra cantidad abierta y P&L realizado. Para posiciones
abiertas, el valor no realizado usa el bid del mismo instrumento/proveedor, con antigüedad máxima
de 60 segundos, sin fecha futura y spread máximo de 5%; son criterios de visualización, no una
autorización de ejecución. Precio, fuente y fecha quedan visibles. Un fallo de cotización conserva
la bitácora y muestra valor no disponible, nunca cero inventado. El valor estimado no descuenta
una comisión futura. Los resultados por entrada y salida son perspectivas de la misma operación:
no se suman; el total de cuenta permanece en el cálculo FIFO agregado.

Al alcanzar el stop u objetivo se muestra un aviso de revisión. No se genera una venta automática.
Una reducción requiere una nueva propuesta aprobada con MFA y los mismos controles de riesgo.

## Conversación con tu bot de Telegram

Actualización 2026-10-15, por petición explícita del operador: `/approve ID`, `/reject ID`
y los botones Aprobar/Rechazar deciden desde el chat **privado vinculado**, sin solicitar MFA
por operación. Se exige coincidencia entre el remitente y el ID del chat privado autorizado;
los grupos, mensajes reenviados a otros chats y usuarios ajenos no pueden aprobar. La web,
activación LIVE, cambios de límites y reanudación conservan sus requisitos de autenticación/MFA.
La decisión queda auditada con el canal y usa los mismos controles deterministas de ejecución.
Una propuesta caducada o ya decidida no se puede aprobar. Los botones muestran el entorno y
quedan ligados a ese modo y versión de límites; si cambian, se pide consultar `/proposals` de nuevo.

`/proposals` (también `/proposal`) muestra hasta cinco fichas completas, ordenadas entre las
100 propuestas más recientes del operador: primero pendientes vigentes, después por relación
beneficio/riesgo hasta los niveles propuestos, potencial bruto y confianza del analista como
desempate. No es una predicción de rentabilidad ni una probabilidad de éxito. Las propuestas sin
stop/objetivo comparable y las reducciones no compiten como rendimientos calculables.

Cada ficha explica activo, entorno, estado, asignación, importe orientativo cuando hay valoración
verificada, razones, riesgos, condiciones de invalidación, entrada, stop, objetivo, escenarios
brutos, horizonte de tenencia y fecha/hora exacta de caducidad en UTC. El horizonte de tenencia
es distinto del plazo para aprobar. Los avisos de nuevas propuestas usan las mismas fichas y
clasificación. `LOW`, `MEDIUM` y `HIGH` son etiquetas orientativas por stop/asignación, no una
calificación de seguridad del activo. Véase [criterios y ejemplo](TELEGRAM-PROPOSALS.md).

El importe sólo se calcula con evidencia LIVE de la cuenta propia, READY, de hasta 60 segundos,
con proveedor/moneda coincidentes. Es el menor entre la asignación sugerida sobre el valor de
cartera, el efectivo observado y el límite por orden, antes de comisiones y demás controles.
PAPER/OBSERVE o evidencia ausente/antigua muestran porcentaje e importe no disponible; no se
inventa un saldo ni una recomendación de depósito. Si el efectivo no alcanza, se muestra el faltante para esa asignación con tope, antes de costes;
puedes utilizar el importe menor. El motor vuelve a calcular el importe final.

`/simulate ID` abre la revisión web; no aprueba ni ejecuta por sí mismo. `/status`, `/breakers`,
`/portfolio`, `/withdrawal` y `/help` conservan su función. `/init` solicita análisis inicial;
no garantiza que se genere una propuesta si falta consenso o evidencia. `/withdrawal` sólo
informa: ningún comando acepta destinatarios ni puede retirar o transferir fondos.

## Estrategia de ejemplo: DCA condicionado

La siguiente lógica es una hipótesis configurable, no una regla universal ni una orden automática:

```text
SI VIX < 20 y Fear & Greed no es “codicia extrema”
  → proponer DCA en acciones/ETFs seleccionados, como SMH o NVDA
SI VIX > 25 o RSI de acciones < 35
  → proponer DCA + reservar hasta 10% de efectivo, sujeto a tu mandato
SI sentimiento cripto = FEAR
  → proponer compra spot de BTC
SI NO
  → proponer límites de compra a -5% y -10%
Registrar la propuesta, tu decisión y el resultado.
```

**DCA** (*dollar-cost averaging*): invertir una cantidad periódica en vez de intentar adivinar un
único precio perfecto. **VIX**: indicador de volatilidad esperada de acciones estadounidenses.
**RSI**: indicador de fuerza reciente del precio; no predice el futuro. **Spot**: comprar el activo
sin deuda ni apalancamiento. **Orden límite**: compra sólo si el precio llega al nivel indicado.
**Reserva**: efectivo que se conserva para oportunidades o protección, no dinero perdido.

Las acciones y ETFs necesitan un proveedor/broker compatible, datos de mercado y calendario de
mercado; no se inventan cotizaciones ni se asume que el mercado está abierto.

## Copy trading y señales públicas

WallyBot puede registrar una señal pública, por ejemplo que una wallet etiquetada o una entidad
relevante compró un activo. Eso no es por sí solo una razón para copiarla: la propuesta muestra
procedencia, fecha, liquidez, concentración y riesgo del token. El resultado es una **propuesta de
copia**, que pasa por tu distribución y aprobación como cualquier otra. WallyBot no sigue cuentas
privadas ni promete que un actor famoso sea una fuente fiable.

## Palabras que vas a ver

| Español | English | En palabras simples |
| --- | --- | --- |
| Broker | Broker | Empresa o app que permite comprar/vender acciones o ETFs. |
| Exchange | Exchange | App para comprar/vender criptoactivos. |
| Wallet | Wallet | Dirección/cuenta donde se ven o guardan criptoactivos. WallyBot sólo acepta dirección pública; nunca semilla ni clave privada. |
| Mantener | Hold | No comprar ni vender por ahora. |
| Reducir | Reduce | Vender una parte de una posición, no necesariamente toda. |
| Ganancia/pérdida | P&L | Diferencia entre lo invertido y el valor o venta posterior. |
| PAPER | Paper | Simulación con datos de mercado; no mueve dinero externo. |

## Límites que no se negocian

- No hay retirada, transferencia, destinatario, banco, dirección de envío ni clave privada en
  WallyBot.
- Las credenciales se almacenan cifradas y sólo se aceptan con permisos mínimos; permisos de
  retiro deben estar desactivados en el proveedor.
- La IA propone y explica; no tiene herramientas de transferencia ni una ruta que convierta una
  recomendación directamente en una orden. La autorización humana y los controles de mandato
  preceden a cualquier operación PAPER.
- LIVE exige conexión verificada, límites, conciliación, MFA y confirmación explícita. PAPER no
  representa dinero real. La IA sigue sin aprobar ni ejecutar operaciones.


## Informes de Telegram

Los informes programados diarios y semanales se muestran en español y resuelven el modo actual
OBSERVE/PAPER/LIVE y la cuenta propia del operador. En LIVE usan la conexión real seleccionada,
con moneda explícita (USDT en Binance), comisiones del mismo modo/moneda y fecha de valoración.
La conciliación sólo se describe como verificada si la cuenta real está READY con una valoración
reciente; la ausencia de un bloqueo no demuestra conciliación. La variación del valor se distingue
de una rentabilidad ajustada por movimientos de fondos. Las referencias de mercado incluyen BTC, ETH, efectivo nominal sin intereses y una cartera
hipotética BTC/ETH 50/50 sin rebalanceo. Usan cierres horarios exactos de un mismo exchange y
moneda, con sus fechas visibles; no interpolan precios ni mezclan USD/USDT. Son variaciones
brutas, sin comisiones, deslizamiento, intereses ni conversión, y no se presentan como
rentabilidad neta de la cuenta ni como clasificación frente a ella. Si aún no cerró una hora del
periodo nuevo se usa el periodo anterior completo, mostrando sus fechas propias. Un cierre
faltante/inválido deja la referencia no disponible y bloquea la mezcla que depende de él. El informe no concede aprobación ni crea órdenes.
