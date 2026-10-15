# ADR-021: decisiones privadas en Telegram y fichas explicadas

Estado: aceptado por petición explícita del operador, 2026-10-15. Implementación local;
despliegue y verificación con PostgreSQL/Redis pendientes del acceso a Docker.

El operador solicita aprobar sin MFA por operación, comprender el porqué, importe, vigencia,
horizonte y riesgos, y recibir primero las propuestas mejor situadas. Sustituye el requisito
TOTP por decisión de Telegram de ADR-017; no cambia activación LIVE, límites ni controles de riesgo.

Se autoriza al remitente cuyo ID coincide con el chat privado vinculado. Los grupos y otros
remitentes no pueden decidir. La función interna vuelve a exigir ADMIN; `record_decision`
conserva propietario, caducidad, uso único, enlace a cuenta/modo/versión y revalidación antes de
ejecutar. El registro de auditoría identifica `TELEGRAM_PRIVATE_CHAT` o `WEB`. Controlar la
cuenta privada vinculada implica poder aprobar: es la frontera de autorización elegida.

Las fichas reutilizan los campos persistidos, sin nuevas predicciones ni dependencias. Una
notificación por ficha evita perder información por el límite de Telegram. Los callbacks
incluyen ID, modo y versión de límites visibles; cambiar configuración invalida una aprobación
desde el botón antiguo. Los comandos escritos vinculan la configuración actual. La respuesta
muestra el estado de ejecución y su motivo, aunque la aprobación no haya creado una orden.

El orden es una comparación de escenarios brutos: beneficio hasta objetivo dividido por caída
hasta stop, luego potencial hasta objetivo y confianza declarada como desempate. Pendientes
vigentes preceden al historial; niveles ausentes y reducciones no tienen rendimiento comparable.
No se convierte confianza en probabilidad ni se estima rendimiento esperado. Se muestran hasta
cinco entre las 100 propuestas recientes. No se anualiza ni se presume ejecución al stop.

LOW exige distancia al stop ≤2% y asignación ≤5%; MEDIUM exige ≤5% y ≤10%; el resto es HIGH,
incluido stop no comparable. Es una clasificación orientativa de la propuesta, no un modelo de
riesgo completo del activo. Las reglas no influyen en autorización ni tamaño de ejecución.

Importes sólo con valoración LIVE propia READY, timestamps entre ahora y 60 segundos atrás,
moneda y proveedor coincidentes: mínimo de asignación × equity, efectivo y límite por orden.
Se etiquetan antes de comisiones/otros límites y sujetos a recálculo. Sin evidencia se conserva
el porcentaje y se informa importe no disponible; no se calcula un depósito a partir de un
saldo desconocido. Stop/objetivo son referencias de seguimiento, no órdenes automáticas.

El prompt de análisis solicita español claro, evidencia para activo/momento/asignación/plazos y
condiciones concretas de invalidación. El parser conserva esas condiciones y el consenso combina
razones y condiciones de ambos analistas, antes de la etiqueta de consenso. La versión por defecto
del prompt pasa a `v2-es`; las propuestas históricas no se reescriben.
