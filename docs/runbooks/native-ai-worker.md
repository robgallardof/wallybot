# Analista local de WallyBot en Windows

El análisis usa las CLI locales autenticadas de Codex y Claude. El proceso nativo complementa
los servicios Docker; no se ejecuta dentro del contenedor ni se inicia por activar PAPER.

Desde la raíz del proyecto:

```powershell
./scripts/start_wallybot.ps1
```

Esto espera a que los servicios Docker estén saludables y arranca el analista en segundo plano.
Para arrancar sólo el analista, usar `./scripts/start_ai_worker.ps1`. El lanzador evita duplicar
el proceso que él mismo inició. Repetir el comando después de reiniciar Windows. El PID y los
logs están en `logs/ai_worker/` (ignorados por Git); no publicar esos archivos.

El cargador consume en tiempo de ejecución la credencial dedicada de analista, sin imprimirla:
`WALLY_DATABASE_URL` tiene prioridad; en su ausencia usa el archivo indicado por
`WALLY_AI_DATABASE_URL_FILE`, cuyo valor por defecto es `.secrets/ai_database_url`. El hostname
interno `postgres` se traduce a `127.0.0.1:5433` para este proceso nativo. Si se cambió el puerto
publicado, configurar `WALLY_AI_DATABASE_PORT`. No copiar credenciales al frontend ni al prompt.

La migración `0041_ai_worker_isolation` elimina los permisos heredados de órdenes/ledger del
rol de analista. Permite registrar únicamente su propio heartbeat mediante una función acotada.
Sistema muestra el heartbeat cada diez segundos y marca al analista como no disponible cuando
el análisis está habilitado pero el proceso no responde. El heartbeat acredita que el proceso
está vivo; HOLD o ausencia de propuestas no equivalen a un fallo.

Para comprobar explícitamente ambas CLI sin acceder a cartera ni persistir propuestas:

```powershell
uv run python scripts/check_ai_analysts.py
```

Esta comprobación hace una llamada real a cada CLI y pide únicamente HOLD. Las llamadas del
analista corren en un directorio temporal y reciben un entorno acotado sin credenciales WALLY.
Codex ignora configuración de usuario, reglas y herramientas de shell/apps; Claude recibe una
lista vacía de herramientas. Las credenciales propias de las CLI siguen bajo su gestión local.

## Disponibilidad de Codex y Claude

Con el análisis activo, el analista registra en cada ciclo si cada CLI respondió (migración
`0045_ai_analyst_status`, mediante una función acotada; el rol de analista no puede escribir la
tabla directamente). Si en un ciclo no se consultó a ningún analista, repite una comprobación HOLD
como máximo una vez por hora. **Configuración → Análisis de IA** muestra para cada uno
«Disponible», «No disponible» o «Sin comprobar todavía», con la hora de la comprobación.

Si uno aparece como no disponible, inicia sesión en su CLI desde una terminal de esta misma
cuenta de Windows y espera al siguiente ciclo (no hace falta reiniciar WallyBot):

```powershell
claude auth login     # comprobar: claude auth status
codex login           # comprobar: codex login status
```

WallyBot nunca desactiva un analista ni la coincidencia por su cuenta. Mientras se exija
coincidencia y uno no esté disponible, no se crean propuestas. Si prefieres usar sólo el
disponible, desmarca tú ese analista **y** «Exigir coincidencia entre ambos» y guarda; el servidor
rechaza la coincidencia estricta con un solo analista en lugar de debilitarla en silencio.

El ciclo pide 30 velas horarias cerradas (mínimo 20 para el filtro de universo). Kraken excluye
la vela en curso; con una ventana exacta de 20 horas sólo llegaban 19 y ningún instrumento era
elegible, por lo que hasta el 2026-10-12 los analistas nunca fueron consultados. El log del
proceso incluye ahora `counts.instruments_evaluated`, `proposals_received` y
`proposals_persisted` en `AI_WORKER_TICK_COMPLETED`, y `AI_ANALYST_UNAVAILABLE_<CLI>` cuando una
CLI no responde.

En la web, el operador habilita análisis con MFA y elige sus analistas. PAPER se habilita por
separado. Cada operación sigue requiriendo aprobación, vigencia y revalidación determinista.
Arrancar procesos no cambia esos ajustes. LIVE y retiros siguen sin habilitarse.
