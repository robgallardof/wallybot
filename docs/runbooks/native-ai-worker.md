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

En la web, el operador habilita análisis con MFA y elige sus analistas. PAPER se habilita por
separado. Cada operación sigue requiriendo aprobación, vigencia y revalidación determinista.
Arrancar procesos no cambia esos ajustes. LIVE y retiros siguen sin habilitarse.
