# WallyBot: tu gestor de cartera asistido

Actualización 2026-10-12: el objetivo solicitado es operar con dinero real. La implementación
LIVE de Kraken spot, con conexión/límites configurados en la UI, MFA y aprobación por operación,
está definida en [ADR-018](adr/018-real-spot-objective.md) y la [guía de activación](runbooks/real-spot-trading.md).
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
| Fuentes permitidas | Kraken, Bitso, wallet pública, broker | Dónde puede observar datos y preparar propuestas. |
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

El bot responde en español o inglés según el idioma de Telegram. La conversación objetivo es:
`/proposals`, `/portfolio`, `/withdrawal`, `/status`, `/breakers`, `/pause`, `/resume` y `/help`. `/proposals`
es de solo lectura y muestra las últimas ideas de tu cuenta. Las decisiones de simular, aprobar o
rechazar se confirman desde WallyBot con MFA; Telegram nunca ejecuta una operación. Cada respuesta
explica importe, precio, riesgo, vigencia y resultado. Si una propuesta aprobada produjo una
simulación PAPER, `/proposals` muestra ese resultado; si la instancia está en OBSERVE, muestra que
no se creó una orden. Ningún
comando acepta una dirección de wallet, banco o destinatario; `/withdrawal` sólo muestra una
recomendación para que la ejecutes fuera de WallyBot.

`/approve ID`, `/reject ID` y `/simulate ID` abren la propuesta propia en la web para revisión.
El enlace sólo navega: ni el comando ni abrirlo consumen una aprobación. La web sigue exigiendo
una acción explícita, sesión autorizada, MFA y vigencia. No se emiten enlaces de aprobación o
simulación para propuestas caducadas; rechazarlas para archivarlas sigue disponible.

`/withdrawal` sólo revisa el resultado realizado confirmado de la cuenta de IA y lo presenta como
contexto para una decisión externa. No acepta una wallet o cuenta bancaria, no crea una orden, no
genera una confirmación y no puede retirar ni transferir fondos.

Cuando el análisis está activado, el intervalo de digest de Configuración determina cuándo se
recibe un resumen de **propuestas nuevas pendientes**. Cada aviso reúne como máximo cinco ideas y
repite que la revisión se hace en la web con MFA. No hay botones, comandos ni respuestas de
Telegram que puedan aprobar, ejecutar, transferir o cambiar esa frecuencia.

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
