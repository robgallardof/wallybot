# Entender y decidir una propuesta de Telegram

Escribe `/proposals` o `/proposal`. Recibirás hasta cinco fichas, primero las pendientes vigentes,
ordenadas por beneficio/riesgo y después por potencial bruto hasta objetivo. El primer puesto
es el mejor según esos niveles de referencia; no significa que sea quien más vaya a ganar.

Cada ficha explica por qué se propone, qué podría salir mal, qué la invalidaría, cuánto asignar,
su horizonte de tenencia y hasta qué fecha/hora puedes aprobar. Los importes monetarios necesitan
una valoración LIVE reciente de tu cuenta en la misma moneda; si falta, se indica expresamente.
El efectivo y límite por orden pueden reducir la cantidad sugerida; al ejecutar se comprueban
también comisiones, exposición y demás límites.

Ejemplo ficticio, sin relación con una propuesta ni saldo reales:

```text
#1 · BTC/USDT
COMPRAR BTC/USDT · binance · LIVE
Riesgo: MEDIUM
Asignación sugerida: 5% del valor de cartera
Importe orientativo: 40 USDT; objetivo de asignación 50; efectivo observado 200
Por qué: volumen y tendencia respaldan el movimiento
Riesgos: caída del mercado; ruptura falsa
Se invalida si: pierde el soporte descrito por los analistas
Entrada de referencia: 100 USDT
Stop: 96 USDT; caída hasta stop 4%
Objetivo: 110 USDT; potencial bruto hasta objetivo 10%
Beneficio/riesgo: 2.5:1
Escenario bruto con 40 USDT: +4 / -1.60 USDT, antes de costes
Horizonte previsto: 24 horas
Aprobar antes de: fecha y hora exactas en UTC
[Aprobar · LIVE] [Rechazar · LIVE]
```

LOW: stop a ≤2% de la entrada y asignación ≤5%. MEDIUM: stop a ≤5% y asignación ≤10%.
El resto se clasifica HIGH; faltan niveles comparables también implica HIGH. Es una orientación
por distancia al stop y asignación; LOW no significa que una inversión sea segura. El stop no
garantiza limitar pérdidas ni genera una venta automática. El objetivo tampoco garantiza beneficio.

Pulsa **Aprobar** o escribe `/approve ID` en tu chat privado vinculado, sin MFA por operación.
**Rechazar** o `/reject ID` descarta esa propuesta. Un botón de otra configuración solicita
consultar `/proposals` de nuevo. Cada propuesta puede decidirse una sola vez; aprobarla caducada
se rechaza. Una aprobación puede quedar bloqueada por saldo, datos o límites: la respuesta
incluye el resultado y el motivo. En OBSERVE no se crea una orden; PAPER simula y LIVE utiliza
dinero real sólo si previamente activaste ese modo y supera la revalidación.
