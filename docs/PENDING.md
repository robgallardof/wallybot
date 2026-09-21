# WallyBot: implementación pendiente y criterios de entrega

Revisión del repositorio: **12 de septiembre de 2026**. Este documento compara la especificación original de 146 apartados con el código y las evidencias existentes. Es un backlog de producto, no una autorización para activar LIVE ni una afirmación de rentabilidad.

Las reglas definitivas siguen en [ARCHITECTURE](../ARCHITECTURE.md), [DATA](../DATA.md), [RISK](../RISK.md), [SECURITY](../SECURITY.md), [TESTING](../TESTING.md) y [DEPLOYMENT](../DEPLOYMENT.md). Las fases se conservan para mantener trazabilidad con el plan original.

## Estado real: módulos disponibles frente a producto integrado

**Coordinación, 12 de septiembre:** Claude trabaja conexiones/backend y Codex UI/UX. Este inventario refleja el inicio de la revisión; revalidar endpoints de mercado y fase 4 porque avanzan en paralelo. Codex entregó la paleta oscura del acceso y panel, persistencia de tema, controles táctiles de 44 px y QR con fondo blanco. Pasaron 2 pruebas de navegador sobre Next en producción, 10 pruebas de aislamiento del entorno web y la comprobación móvil del contenedor local (HTTP 200, sin desbordamiento ni errores de página). Esto no cierra automáticamente las casillas de aceptación más amplias.

La base autenticada existe y varias piezas cuantitativas están implementadas. **Todavía falta conectarlas como un producto que recolecta datos, muestra oportunidades, simula operaciones y reconcilia su contabilidad.** La etiqueta PAPER no significa que ya exista un simulador de trading completo.

| Área | Evidencia disponible al iniciar esta revisión | Límite actual |
| --- | --- | --- |
| Base y acceso | Setup, contraseña y confirmación, QR TOTP y clave manual, recuperación, sesiones, permisos, CSRF, eventos, procesos y Docker | Administración de usuarios, reemplazo de MFA y validación del despliegue final pendientes |
| Frontend | `apps/web/package.json` ya usa Next.js; existen App Router, React, formularios, Zod, i18next, tema y componentes UI | No se debe repetir la migración desde Vite; falta verificar toda la entrega actual y actualizar documentación que aún dice Vite |
| Datos de mercado | FakeExchange, REST público Kraken, filtros, calidad, snapshots en Redis, escritura Parquet, features y scanner | Son capacidades reutilizables; el scheduler inspeccionado solo programa mantenimiento y no existe aún un recorrido de mercado visible en la UI |
| Cuantitativo | Regímenes, estrategia de tendencia, consenso, asignación y evaluador determinista de riesgo | Implementaciones iniciales; faltan controles financieros completos, persistencia y composición de extremo a extremo |
| API y dashboard | Salud, control, eventos y autenticación | `/api/dashboard` todavía devuelve `trading_available=False`, `equity=None` y posiciones vacías; no hay que confundir esto con un portafolio conectado |
| Persistencia | Migración `0001_foundation` para identidad, control, eventos y mantenimiento | No hay aún esquema financiero operativo completo de órdenes, fills, reservas, ledger y conciliaciones |
| Pruebas | [Registro existente](stats/testing.md): 168 pruebas en la revisión previa de fases 2–3 | Este inventario no vuelve a ejecutar esas pruebas; el número no prueba cobertura financiera completa ni CI remoto verde |

Las entregas documentadas en [PHASE_2](PHASE_2.md) y [PHASE_3](PHASE_3.md) son avances reales. Sus etiquetas de fase completa describen cortes acotados: **no cierran todos los requisitos del producto original**, especialmente integración, riesgo avanzado y operación continua.

## Prioridad inmediata

| Prioridad | Trabajo | Criterio para considerarlo terminado |
| --- | --- | --- |
| P0 | Conectar datos → calidad → scanner → API → pantalla de mercados | Sin credenciales privadas, se ven origen, hora, frescura, criterios y motivos de exclusión; fallos del proveedor se muestran como fallo, nunca como cotizaciones válidas |
| P0 | Cerrar los controles que faltan antes de ejecutar incluso PAPER | Cantidad limitada por stop, efectivo, costes, reservas, liquidez y concentración; datos o configuración incompletos impiden aumentar exposición |
| P0 | Entregar una operación PAPER de extremo a extremo | Decisión y aprobación persistidas → intención única → simulador → fill → asientos balanceados → posición visible y conciliada |
| P0 | Probar reinicios, duplicados y resultados ambiguos | Repetir solicitudes o reiniciar procesos no duplica efecto económico; estados ambiguos conservan reservas y bloquean nuevas entradas hasta resolución |
| P1 | Cerrar streaming y almacenamiento histórico consultable | Reconexión y gaps probados, manifiestos verificables y lectura reproducible sin datos futuros |
| P1 | Completar UI y observabilidad con datos reales | Tablas, filtros, detalle y errores conectados a capacidades entregadas, con pruebas desktop/móvil e idiomas |
| P1 | Recuperación, seguridad y despliegue de producción | Restauración ensayada, HTTPS y cookies verificados, monitorización útil y límites de recursos medidos |
| P2 | Investigación, IA y reportes | Trabajan sobre evidencia reproducible y presupuestos; ninguna recomendación puede saltarse riesgo ni promoverse sola |

## Fase 1: cerrar la base y la experiencia Next.js

- [ ] Verificar build Next, proxy al backend, rutas directas, recarga, sesión y expiración detrás del gateway. Mantener un único origen y puerto 3333.
- [ ] Verificar Docker y desarrollo híbrido con Next; eliminar referencias operativas obsoletas a Vite y documentar la decisión de migración.
- [ ] Completar accesibilidad de formularios, navegación por teclado, estados de carga/error, contraste y tamaños móviles; conservar ES/EN y preferencias.
- [ ] Incorporar administración autorizada de usuarios, sesiones activas, cambio de contraseña y sustitución de TOTP con revocación y auditoría.
- [ ] Definir recuperación local auditada si se pierden todos los factores; no reabrir bootstrap como atajo.
- [ ] Incorporar configuración protegida versionada, validación y trazabilidad de cambios; MFA reciente cuando corresponda.
- [ ] Ejecutar CI en el repositorio remoto y registrar resultados de la revisión exacta entregada.
- [ ] Verificar Fedora/Cloudflare reales: origen, HTTPS, cookies, NTP, recursos y único puerto público previsto.

**Aceptación:** registro y acceso completos por navegador, rutas protegidas también en API, recuperación comprobada, build reproducible y despliegue ensayado. La migración de framework se marca verificada solo después de estas comprobaciones, no por instalar Next.

## Fase 2: datos y scanner como función de la aplicación

- [ ] Crear la composición y programación efectiva de la recolección; establecer cadencias, concurrencia acotada, cancelación, timeouts, reintentos y backoff.
- [ ] Pasar siempre por calidad antes de features y ranking; aplicar una política explícita a cada WARNING y conservar evidencia de fallos.
- [ ] Persistir ejecuciones del scanner y su configuración para explicar después qué se seleccionó o rechazó.
- [ ] Publicar API autenticada de mercados y detalle de instrumento; mostrar datos públicos Kraken sin pedir claves de trading.
- [ ] Implementar tabla de mercados con filtros, ranking, precio, volumen, spread, momentum, calidad y fecha; presentar métricas no disponibles como tales.
- [ ] Completar detalle de activo con velas, volumen e indicadores; añadir libro/trades cuando existan contratos y datos adecuados.
- [ ] Comparar WebSocket nativo Kraken y CCXT Pro conforme a [ADR-004](adr/004-exchange-adapters.md); registrar evidencia y elección.
- [ ] Implementar streaming normalizado, recuperación desde snapshot, secuencias, reconexión y bloqueo por desincronización o staleness.
- [ ] Ampliar caché únicamente según consumidores reales: velas, calidad y rankings; un hit nunca certifica frescura.
- [ ] Completar cuarentena, cuotas, retención, catálogo histórico y lectura de manifiestos; probar recuperación de publicación parcial y correcciones.
- [ ] Añadir features que necesiten las estrategias reales —volatilidad, ATR, volumen, correlación— con fórmulas versionadas y referencias numéricas.
- [ ] Unificar metadatos de instrumentos, reglas del mercado y normalización de identificadores sin romper la identidad por venue.

**Aceptación:** pipeline repetible con FakeExchange y fixtures Kraken, pruebas de fallo y reconexión, ausencia de lookahead y mercados visibles en UI. La recolección externa real es una comprobación adicional; las pruebas obligatorias no dependen de disponibilidad de Kraken.

## Fase 3: completar la política cuantitativa y de riesgo

- [ ] Componer features, régimen, estrategia, consenso, asignación y riesgo; guardar tanto decisiones rechazadas como aprobadas con entradas/versiones.
- [ ] Ampliar regímenes con evidencia de volatilidad, amplitud y condiciones anormales; el clasificador inicial de momentum no cubre toda la taxonomía original.
- [ ] Incorporar las demás estrategias solicitadas cuando exista hipótesis y datos: breakout, pullback, reversión, rotación y variantes de volumen/volatilidad.
- [ ] Nueva idea de estrategia propuesta por el usuario (2026-09-20, sin implementar): DCA condicionado por régimen para renta variable (VIX, Fear & Greed Index) sobre SMH/NVDA con inyección de reserva si VIX>25 o RSI_Stocks<35, más una rama cripto (Fear→compra spot BTC, si no→limit orders escalonados -5%/-10%). Requiere decisiones de scope antes de construirse: (1) `MarketType` hoy solo tiene `SPOT` cripto vía Kraken -- no existe integración de renta variable ni de VIX/Fear&Greed como fuente de datos; (2) encaja como un nuevo `Strategy` (`wallybot/domain/strategy.py`) consumido por `RegimeClassification`, no como cambio al motor de riesgo/breakers. No iniciar sin decisión explícita del usuario sobre el proveedor de datos de renta variable/VIX.
- [ ] Implementar tamaño por distancia al stop y presupuesto de riesgo, costes, capacidad de efectivo, reservas, impacto y límites de liquidez.
- [ ] Enlazar evaluación con intención exacta, cuenta, entorno, digest, versiones y caducidad; persistir aprobación y reserva atómicamente.
- [ ] Calcular equity, pérdidas diaria/semanal y high-water mark ajustados por flujos externos; conservarlos tras reinicios.
- [ ] Completar concentración por activo entre venues, clusters, volatilidad y correlación; configuración requerida ausente debe fallar de forma cerrada.
- [ ] Soportar reducciones y cierres sin vender más de lo poseído; el allocator inicial no implementa todavía el flujo SELL.
- [x] Implementar breakers persistentes, motivo y rearme autorizado; no reiniciarlos silenciosamente al cambiar de día. (2026-09-20: `wallybot/domain/breaker.py`, `BreakerRepository`, migración `0029_breakers`, `run_decision_tick` evalúa y traba cada breaker por tick, `POST /api/risk/breakers/{type}/clear` exige Admin+MFA reciente, UI en RiskPage.)
- [ ] Separar pausa de entradas, cancelación de órdenes, cierre de posiciones y emergencia; reflejar resultados reales y acciones pendientes.
- [ ] Exponer límites, consumo, reservas, pérdidas, incumplimientos y razones en la pantalla de riesgo.
- [ ] Alcanzar y demostrar el objetivo de cobertura de ramas de riesgo de [TESTING](../TESTING.md), incluyendo concurrencia, parciales y límites exactos.

**Aceptación:** propiedades financieras verificadas con Decimal y UTC; ninguna aprobación excede capacidad conservadora ni puede reutilizarse para otra intención. Un booleano de conciliación recibido como argumento no sustituye el mecanismo de conciliación.

## Fase 4: replay, ejecución PAPER, ledger y recuperación

- [ ] Implementar reloj de replay y flujo determinista de eventos; misma entrada, versiones y semilla deben producir el mismo resultado.
- [ ] Añadir cuentas PAPER, efectivo inicial explícito, órdenes, fills, reservas y posiciones con migraciones y permisos mínimos.
- [ ] Implementar la máquina de estados de órdenes y persistir transiciones; cubrir parciales, cancelación concurrente, rechazo, timeout y UNKNOWN.
- [ ] Extender el exchange simulado con saldos, ejecución, comisiones, spread, slippage, latencia y fallos configurables.
- [ ] Implementar idempotencia por cuenta/entorno y payload; reservar capacidad bajo bloqueo de cuenta para impedir aprobaciones concurrentes incompatibles.
- [ ] Revalidar aprobación, expiración, política y controles antes de ejecutar; registrar SUBMITTING antes de la llamada externa.
- [ ] Incorporar ledger inmutable con igualdad de débitos/créditos por activo en la transacción, fills deduplicados y correcciones por reverso.
- [ ] Implementar lotes FIFO, comisiones en moneda nativa, PnL realizado/no realizado y proyecciones reconstruibles.
- [ ] Crear outbox e inbox transaccionales, reintentos acotados y recuperación de leases; Redis solo acelera notificaciones.
- [ ] Conciliar órdenes, fills, posiciones y saldos con cobertura completa; conservar discrepancias y evitar que una consulta fallida parezca una cuenta vacía.
- [ ] Incorporar recuperación al arrancar y después de fallos; UNKNOWN no libera reservas por simple timeout.
- [ ] Entregar páginas de órdenes, operaciones, posiciones, portafolio y detalle de decisión con trazabilidad completa.
- [ ] Entregar modo demo opcional y separado, claramente rotulado, sin claves privadas y sin métricas inventadas en cuentas reales.

**Aceptación:** prueba E2E de una operación PAPER completa; repetir o interrumpir cada frontera crítica no duplica órdenes ni fills; ledger balanceado y posición reconstruible. No existe ruta hacia un adaptador LIVE.

## Fase 5: datasets, backtests y evaluación

- [ ] Consultar Parquet con DuckDB usando manifiestos inmutables, hashes, límites de recursos y versiones de esquema.
- [ ] Registrar dataset, código, dependencias, configuración, semilla y divisiones temporales de cada experimento.
- [ ] Implementar backtesting con modelo de fills y costes explícito; compartir reglas verificables con PAPER.
- [ ] Implementar walk-forward, Monte Carlo y bootstrapping, con muestra e incertidumbre reportadas.
- [ ] Controlar leakage y sesgos de selección/supervivencia; documentar límites de historia y activos deslistados.
- [ ] Calcular métricas de estrategia/portafolio, atribución por activo/régimen/bucket y concentración de beneficios.
- [ ] Comparar BTC, ETH, efectivo y portafolio pasivo sobre ventanas y supuestos equivalentes.
- [ ] Crear registro de estrategias y ciclo DRAFT → BACKTESTED → VALIDATED → PAPER → CANDIDATE → LIVE → RETIRED con promociones humanas auditadas.
- [ ] Crear evaluación contrafactual a horizontes predeclarados y rotular resultados hipotéticos.
- [ ] Entregar UI de backtests, experimentos, comparaciones y artefactos descargables.

**Aceptación:** un experimento puede reproducirse desde sus artefactos; costes no se contabilizan dos veces, particiones de entrenamiento/prueba permanecen separadas y no se promueve por beneficio retrospectivo solamente.

## Fase 6: IA opcional, calibración y costes

- [ ] Implementar puerto AIProvider y adaptadores OpenAI/Anthropic con esquemas estrictos, límites y trazabilidad.
- [ ] Validar salida, símbolos, razones y caducidad; contenido del proveedor se trata como datos no confiables.
- [ ] Definir routing, timeouts, fallback y presupuestos por ejecución/día; registrar modelo, tokens, latencia y coste.
- [ ] Aplicar HOLD a estrategias que requieren IA si falta una respuesta válida; mantener independientes las que no la requieren.
- [ ] Implementar calibración, resultados posteriores, comparación con/sin IA y consenso opcional.
- [ ] Entregar UI de decisiones IA y contabilidad de costes, sin permitir ejecución directa desde recomendaciones.

**Aceptación:** pruebas de JSON inválido, inyección de instrucciones, timeout y agotamiento del presupuesto; el veto determinista de riesgo siempre prevalece. No hace falta instalar todos los proveedores propuestos para cumplir un contrato neutral.

## Fase 7: agentes de investigación aislados

- [ ] Convertir el research worker actual en ejecutor de experimentos con cola, cuotas, cancelación y artefactos.
- [ ] Proporcionar vistas/exportaciones saneadas y lectura analítica limitada; separar claves, escritura y red de producción.
- [ ] Integrar agentes con herramientas autorizadas para pruebas, análisis, candidatos y reportes; código generado requiere revisión.
- [ ] Añadir identidad de servicio y protección de replay si se introduce un endpoint de agente.
- [ ] Implementar propuestas de cambios/promoción con revisión humana y trazabilidad, sin autoaprobación.
- [ ] Entregar UI de trabajos, historial, resultados, consumo y fallos.

**Aceptación:** pruebas negativas demuestran que investigación no obtiene credenciales de trading, no modifica límites ni envía órdenes y no agota recursos del proceso operativo.

## Fase 8: Telegram, notificaciones y reportes

- [ ] Integrar notificaciones por severidad, agrupación, deduplicación y límites para evitar spam.
- [ ] Implementar comandos de consulta y operación con IDs numéricos autorizados y permisos por comando.
- [ ] Confirmar acciones sensibles con tokens expiran/anti-replay y MFA web cuando corresponda.
- [ ] Generar reportes diarios/semanales con rendimiento neto, costes, benchmarks, riesgos y problemas de servicio.
- [ ] Manejar fallos de entrega sin alterar verdad financiera; reportar ambigüedad de envío.

**Aceptación:** usuarios no autorizados y replays no producen efectos; reportes corresponden al ledger y ventanas UTC. Configurar una integración no autoriza enviar mensajes durante su desarrollo.

## Fase 9: preparación LIVE, solamente tras los gates

- [ ] Implementar y probar contrato del gateway privado Kraken, capacidades, precisión, tipos soportados y reconciliación por client ID.
- [ ] Validar permisos de claves trade-only, sin retiros; fallar activación si no hay evidencia suficiente.
- [ ] Exigir capacidad de build/entorno, estrategia promovida, límites válidos, reconciliación reciente, TOTP y confirmación de cuenta.
- [ ] Implementar lease LIVE revocable: un reinicio exige conciliación y rearme del operador.
- [ ] Completar pruebas de fallos, simulación prolongada, monitoreo, backups y manual operativo antes de una prueba con capital pequeño.
- [ ] Mostrar permanentemente entorno y dinero real; separar datos y relaciones PAPER/LIVE en DB.

**Aceptación:** evidencia documentada de todos los gates de [RISK](../RISK.md) y [SECURITY](../SECURITY.md), más autorización humana específica. No se implementa funcionalidad de retiros autónomos.

## Fase 10: expansión condicionada a evidencia

- [ ] Adaptadores adicionales Binance/Coinbase y observación entre exchanges con pruebas de contrato.
- [ ] Metadata de mercado mediante proveedores intercambiables, con procedencia y valores desconocidos explícitos.
- [ ] Radar especulativo, datos DEX/on-chain y TokenRiskAnalyzer: liquidez, concentración, autoridades, restricciones, impuestos y honeypot cuando haya datos.
- [ ] Noticias, sentimiento y derivados solo como datos; no habilitar apalancamiento por incorporar un feed.
- [ ] Investigación de arbitraje sin asumir ejecución LIVE autorizada.
- [ ] Optimización robusta, clusters y modelos ML con evaluación fuera de muestra, interpretación y control del sobreajuste.
- [ ] Evaluar pyramiding, cosecha de ganancias, reinversión y Kelly fraccional como experimentos; nunca relajar límites automáticamente ni usar Kelly completo.

**Aceptación:** cada ampliación justifica sus datos y coste, conserva contratos y controles, y muestra una mejora evaluable frente a una base simple.

## Pendientes transversales que no deben perderse

| Área | Trabajo y aceptación |
| --- | --- |
| Observabilidad | Perfil Prometheus/Grafana, OpenTelemetry y métricas de datos, colas, riesgo, UNKNOWN, conciliación, costes y recursos; etiquetas sin IDs ilimitados y alertas ensayadas |
| Eventos y logs | Búsqueda, filtros, paginación y seguimiento en vivo autenticado; revocación de streams y redacción; auditoría de cambios en la misma transacción |
| Seguridad | Rotación cifrada de secretos de proveedores y claves de respaldo, permisos mínimos, exportación de auditoría protegida y escaneos actualizados; nunca exponer secretos en herramientas o fixtures |
| Backups | Copia fuera del host, custodia separada de la clave, restauración periódica y cobertura de datasets irreproducibles; definir RPO/RTO y verificar disco/retención |
| Analítica de costes | Separar fees, slippage atribuido, IA, proveedores e infraestructura; rendimientos ajustados por flujos externos sin doble descuento |
| Exportación | CSV/JSON de operaciones, comisiones, moneda y PnL con permisos y pruebas de exactitud; sin reglas fiscales jurisdiccionales dentro del motor |
| Configuración | Versiones, validación y flags experimentales OFF; modificaciones sensibles auditadas y sin reinicios que restablezcan límites |
| Documentación | Actualizar estados obsoletos; añadir TRADING, STRATEGIES, AI, RESEARCH, BACKTESTING y guías de operación/desastre junto a sus implementaciones |
| Herramientas del repositorio | Recuperar `.ai/HANDOFF.md` y coherencia del contexto; verificar disponibilidad real de Graphify/Serena antes de afirmar indexado actualizado |

## Definición de terminado para cada entrega

Una entrega necesita implementación, tipos, validación, manejo de errores, pruebas relevantes, logging/métricas y documentación. Si tiene UI, necesita navegación, accesibilidad, idiomas y estado vacío/error; si mueve estado financiero, necesita concurrencia, idempotencia, recuperación y contabilidad comprobadas.

Registrar siempre fecha, revisión y comandos/resultados reales. La presencia de un archivo, un protocolo, una prueba unitaria aislada o una página que dice «próximamente» no completa una capacidad de producto. No se asigna un porcentaje global porque el esfuerzo restante y los riesgos de las fases financieras son muy distintos de los de la base.

**Orden de entrega recomendado:** mercado visible y calidad → decisión persistida → PAPER con ledger y recuperación → evaluación reproducible → IA/investigación → reportes → gates LIVE → expansión.


### Avance: inspección de actividad (12 de septiembre)

Entregado: búsqueda, filtro por tipo, orden, detalle con ID/código/fecha UTC, actualización manual y estados vacíos/error en ES/EN. Probado en navegador de producción y móvil. Se aplica a los últimos 100 eventos; quedan pendientes paginación del historial en servidor y seguimiento en vivo. No se modificó el backend de Claude.
