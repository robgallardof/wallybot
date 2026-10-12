import { expect, test, type Page } from "@playwright/test";

test("intelligence index supports keyboard jumps, return links, locale and query failure", async ({ page }) => {
  await shell(page);
  let failed = false;
  await page.route("**/api/intelligence/entity-graph", (route) => route.fulfill(failed
    ? { status: 503, json: { detail: "fixture unavailable" } }
    : { json: { rows: [] } }));
  await page.goto("/intelligence");
  const index = page.getByRole("navigation", { name: "Explorar inteligencia" });
  await expect(index.getByRole("link")).toHaveCount(8);
  await expect(index.getByRole("link").last()).toContainText("0 registros");
  const link = index.getByRole("link", { name: /Grafo de correlación/ });
  await link.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#signal-entities$/);
  await expect(page.locator("#signal-entities")).toBeFocused();
  await page.locator("#signal-entities").getByRole("link", { name: "Volver a las señales" }).click();
  await expect(index).toBeFocused();
  await page.getByLabel("Idioma").selectOption("en");
  await expect(page.getByRole("navigation", { name: "Explore intelligence" })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.screenshot({ path: "test-results/intelligence-index-mobile.png", fullPage: true });
  failed = true;
  await page.locator("#signal-entities").getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByRole("navigation", { name: "Explore intelligence" }).getByRole("link").last()).toContainText("Query failed");
});

test("experiment history search, filters, keyboard details and stale data", async ({
  page,
}) => {
  await shell(page);
  const row = {
    experiment_id: "older-exp",
    strategy_id: "trend_following",
    instrument_venue: "kraken",
    instrument_base: "XBT",
    instrument_quote: "USD",
    timeframe: "1h",
    window_start: "2026-01-01T00:00:00Z",
    window_end: "2026-01-02T00:00:00Z",
    trade_count: 0,
    starting_equity: "9007199254740993.125",
    final_equity: "9007199254740993.125",
    total_return_pct: "0",
    max_drawdown_pct: "0",
    win_rate: null,
    created_at: "2026-01-03T00:00:00Z",
  };
  let failed = false;
  await page.route("**/api/backtests", (route) =>
    route.fulfill(
      failed
        ? { status: 503, json: { detail: "fixture unavailable" } }
        : {
            json: {
              rows: [
                row,
                {
                  ...row,
                  experiment_id: "newer-exp",
                  instrument_base: "ETH",
                  timeframe: "1d",
                  created_at: "2026-01-04T00:00:00Z",
                },
              ],
            },
          },
    ),
  );
  await page.goto("/research");
  const history = page.locator(".backtest-history");
  await expect(history.getByRole("status")).toHaveText("2 de 2 experimentos");
  await expect(history.locator("tbody tr").first()).toContainText("ETH/USD");
  await page.getByLabel("Orden del historial").selectOption("oldest");
  await expect(history.locator("tbody tr").first()).toContainText("XBT/USD");
  await page.getByLabel("Buscar experimentos").fill("missing");
  await expect(
    history.getByRole("heading", { name: "No hay experimentos que coincidan" }),
  ).toBeVisible();
  await history.getByRole("button", { name: "Limpiar filtros" }).click();
  await page.getByLabel("Marco temporal del historial").selectOption("1h");
  await expect(history.locator("tbody tr")).toHaveCount(1);
  const details = history.getByText("Ver detalles", { exact: true });
  await details.focus();
  await page.keyboard.press("Enter");
  await expect(history.locator("details")).toHaveAttribute("open", "");
  await expect(
    history.getByText("No disponible", { exact: true }),
  ).toBeVisible();
  await expect(history.locator("details")).toContainText(
    "9007199254740993.125 USD",
  );
  await expect(history.locator("details time").first()).toHaveAttribute(
    "datetime",
    row.window_start,
  );
  await page.getByLabel("Idioma").selectOption("en");
  await expect(history.getByText("Analyzed period (UTC)")).toBeVisible();
  await expect(history.getByRole("status")).toHaveText("1 of 2 experiments");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Switch to dark mode" }).click();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.screenshot({
    path: "test-results/backtest-history-mobile-dark.png",
    fullPage: true,
  });
  failed = true;
  await history.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(history.getByRole("alert")).toContainText("may be outdated");
  await expect(history.locator("tbody tr")).toHaveCount(1);
});

const snapshot = {
  as_of: "2026-09-13T12:00:00Z",
  rows: [
    {
      id: "BTC/USD",
      venue: "kraken",
      base: "BTC",
      quote: "USD",
      bid: "60000.10",
      ask: "60001.20",
      spread_ratio: "0.000018",
      quality_status: "PASS",
      quality_reasons: [],
      eligible: true,
      rejection_reasons: [],
      score: "0.85",
      rank: 1,
    },
    {
      id: "ETH/USD",
      venue: "kraken",
      base: "ETH",
      quote: "USD",
      bid: "2000.10",
      ask: "2001.20",
      spread_ratio: "0.00055",
      quality_status: "FAILURE",
      quality_reasons: ["STALE_QUOTE"],
      eligible: false,
      rejection_reasons: ["QUALITY_FAILURE"],
      score: null,
      rank: null,
    },
  ],
};
const system = {
  api: "HEALTHY",
  database: "HEALTHY",
  redis: "UNAVAILABLE",
  services: { worker: { status: "STALE", age_seconds: 42 } },
  exchange: "HEALTHY",
  ai: "DISABLED",
  telegram: "DISABLED",
  live_available: false,
};

async function shell(page: Page, role: "ADMIN" | "VIEWER" = "VIEWER") {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const responses: Record<string, unknown> = {
      "/api/auth/setup-status": { setup_required: false },
      "/api/auth/me": {
        username: "ui-fixture",
        role,
        csrf: "synthetic-ui-only",
      },
      "/api/dashboard": {
        environment: "PAPER",
        status: "RUNNING",
        trading_available: false,
        equity: null,
        exchange: "NOT_CONFIGURED",
        positions: [],
        phase: 1,
      },
      "/api/portfolio": {
        environment: "PAPER",
        connection_count: 0,
        balances: [],
        activity: [],
        performance: [],
        proposal_history: [],
        orders: [],
      },
      "/api/portfolio/ai": {
        environment: "PAPER",
        connection_count: 0,
        balances: [],
        activity: [],
        performance: [],
        proposal_history: [],
        orders: [],
      },
      "/api/ai-autonomy/control": {
        status: "DISABLED",
        target_core_pct: "0.70",
        target_growth_pct: "0.20",
        target_speculative_pct: "0.10",
        digest_interval_hours: 6,
        codex_enabled: true,
        claude_enabled: true,
        require_consensus: true,
      },
      "/api/system": system,
      "/api/events": { rows: [], next_before: null },
      "/api/connections": { rows: [] },
      "/api/live": { capable: true, configured: false, enabled: false, state: "NOT_CONFIGURED", reason: "", version: null, connection_id: null, max_order_usd: null, max_daily_loss_usd: null, max_total_usd: null, slippage_pct: null, equity_usd: null, as_of: null, balances: [], orders: [] },
      "/api/intelligence/smart-money": { rows: [] },
      "/api/intelligence/whale-flow": { rows: [] },
      "/api/intelligence/token-risk": { rows: [] },
      "/api/intelligence/provider-reliability": { rows: [] },
      "/api/intelligence/price-consensus": { rows: [] },
      "/api/intelligence/wallet-activity": { rows: [] },
      "/api/intelligence/entity-graph": { rows: [] },
      "/api/backtests": { rows: [] },
      "/api/research/jobs": { rows: [] },
      "/api/proposals": { rows: [] },
      "/api/telegram": {
        has_bot_token: false,
        chat_id: null,
        enabled: false,
        pairing_status: "NEEDS_TOKEN",
        pairing_code: null,
      },
      "/api/telegram/confirmations": { rows: [] },
      "/api/auth/confirm-mfa": { ok: true },
      "/api/auth/sessions": { rows: [] },
    };
    if (!(path in responses))
      throw new Error(`Unexpected API request: ${path}`);
    await route.fulfill({ json: responses[path] });
  });
}

test("settings and first-steps pages keep actions aligned on desktop and mobile", async ({ page }) => {
  await shell(page, "ADMIN");
  await page.route("**/api/auth/sessions**", async (route) => {
    if (route.request().method() === "DELETE") {
      await route.fulfill({ json: { ok: true } });
      return;
    }
    await route.fulfill({
      json: {
        rows: [
          {
            session_id: "current-session",
            created_at: "2026-01-01T00:00:00Z",
            last_seen: "2026-01-01T00:05:00Z",
            expires_at: "2026-01-01T12:00:00Z",
            is_current: true,
          },
        ],
      },
    });
  });
  await page.route("**/api/auth/password", (route) => route.fulfill({ json: { ok: true } }));
  await page.route("**/api/auth/totp/replace/start", (route) =>
    route.fulfill({
      json: {
        challenge: "synthetic-challenge",
        secret: "SYNTHETICSECRET",
        uri: "otpauth://totp/WallyBot?secret=SYNTHETICSECRET",
      },
    }),
  );
  await page.route("**/api/auth/totp/replace/finish", (route) =>
    route.fulfill({ json: { ok: true } }),
  );
  let aiAutonomyEnabled = false;
  await page.route("**/api/ai-autonomy/control", async (route) => {
    if (route.request().method() === "POST") aiAutonomyEnabled = true;
    await route.fulfill({
      json: {
        status: aiAutonomyEnabled ? "ENABLED" : "DISABLED",
        target_core_pct: "0.70",
        target_growth_pct: "0.20",
        target_speculative_pct: "0.10",
        digest_interval_hours: 6,
        codex_enabled: true,
        claude_enabled: true,
        require_consensus: true,
      },
    });
  });
  await page.goto("/settings");
  // shell()'s mocked /api/dashboard always returns environment: "PAPER" -- assert the settled
  // PAPER-state text, not the pre-fetch OBSERVE default. Asserting the default was a race: the
  // dashboard query resolves asynchronously, and `toBeVisible()` succeeds on first match rather
  // than a settled one, so it could "pass" by catching the transient pre-hydration render.
  await expect(page.getByRole("heading", { name: "Simulación PAPER activada" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Desactivar simulación (volver a OBSERVE)" }),
  ).toBeVisible();
  // AI analysis (proposals only, never auto-executes -- ADR-017) is a toggle fully separate
  // from the PAPER on/off switch above.
  await expect(
    page.getByRole("heading", { name: "Análisis de IA desactivado" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Activar análisis de IA" }).click();
  await expect(
    page.getByRole("heading", { name: "Análisis de IA activado" }),
  ).toBeVisible();
  await expect(page.getByLabel("Token del bot")).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar y vincular bot" })).toBeVisible();
  await page.getByLabel("Código de autenticación").fill("123456");
  await page.getByRole("button", { name: "Confirmar", exact: true }).click();
  await expect(
    page.getByText("Identidad confirmada. Ya podés repetir la acción que había fallado."),
  ).toBeVisible();

  await page.getByLabel("Contraseña actual").fill("correct-horse-battery-staple");
  await page.getByLabel("Contraseña nueva").fill("a-new-long-password");
  await page.getByRole("button", { name: "Cambiar contraseña" }).click();
  await expect(page.getByText("Contraseña actualizada.")).toBeVisible();

  await page.getByRole("button", { name: "Reemplazar autenticador" }).click();
  await expect(page.getByRole("img", { name: /código qr/i })).toBeVisible();
  await page.getByText("¿No puedes escanearlo?").click();
  await expect(page.getByText("SYNTHETICSECRET")).toBeVisible();
  await page.getByLabel("Código de verificación").fill("123456");
  await page.getByRole("button", { name: "Verificar y entrar" }).click();
  await expect(page.getByRole("button", { name: "Reemplazar autenticador" })).toBeVisible();

  const sessionRow = page.getByRole("row").filter({ hasText: "Esta sesión" });
  await expect(sessionRow).toBeVisible();
  await sessionRow.getByRole("button", { name: "Cerrar sesión" }).click();

  await page.setViewportSize({ width: 390, height: 844 });
  const navigation = page.locator("#control-navigation");
  await expect(navigation).toBeHidden();
  await page.getByRole("button", { name: "Abrir navegación" }).click();
  await expect(navigation).toBeVisible();
  await expect(navigation.getByRole("button", { name: "Mercados" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);

  await page.goto("/docs");
  await expect(
    page.getByRole("heading", { name: "Cómo funciona realmente WallyBot" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: /Mercados/ })).toBeVisible();
  await expect(page.getByText("WallyBot no puede retirar ni transferir fondos.")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test("markets direct route, loading, filters, keyboard details, locales and stale/empty states", async ({
  page,
}) => {
  await shell(page);
  let reply: "ok" | "error" | "empty" = "ok";
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/markets", async (route) => {
    await gate;
    await route.fulfill(
      reply === "error"
        ? { status: 503, json: { detail: "fixture unavailable" } }
        : { json: reply === "empty" ? { ...snapshot, rows: [] } : snapshot },
    );
  });
  await page.route("**/api/markets/**", (route) =>
    route.fulfill({
      json: {
        ...snapshot.rows[0],
        as_of: snapshot.as_of,
        candles: [
          {
            open_time: "2026-01-01T00:00:00Z",
            close_time: "2026-01-01T01:00:00Z",
            open: "100",
            high: "106",
            low: "98",
            close: "104",
            volume: "123.45",
          },
        ],
      },
    }),
  );
  expect((await page.goto("/markets"))?.status()).toBe(200);
  // MarketsPage's own PageSkeleton uses the "Cargando mercados…" label (not the generic
  // "Cargando contenido" default) -- asserting the generic label only "passed" before by
  // catching a transient pre-hydration frame, the same race class already fixed once in this
  // suite for Settings; assert the real, stable loading state the gated /api/markets route
  // actually produces instead.
  await expect(page.locator(".page-skeleton")).toBeVisible();
  release();
  await expect(page.getByRole("table").getByRole("row")).toHaveCount(3);
  await page.getByLabel("Idioma").selectOption("en");
  await expect(page.getByLabel("Search markets")).toBeVisible();
  await page.getByLabel("Search markets").fill("missing");
  await expect(page.getByText("No markets match the filters.")).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await page
    .getByLabel("Eligibility", { exact: true })
    .selectOption("excluded");
  await expect(page.getByRole("table").getByRole("row")).toHaveCount(2);
  await page.getByRole("button", { name: "View detail" }).first().click();
  await expect(page.getByRole("img", { name: "Recent candles" })).toBeVisible();
  await expect(page.getByText("123.45", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await page.getByLabel("Quality", { exact: true }).selectOption("PASS");
  await expect(page.getByRole("table").getByRole("row")).toHaveCount(2);
  await page.getByRole("button", { name: "Clear filters" }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Switch to dark mode" }).click();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.getByRole("region", { name: "Discovered markets" }).focus();
  await expect(
    page.getByRole("region", { name: "Discovered markets" }),
  ).toBeFocused();
  await page.screenshot({
    path: "test-results/markets-mobile-dark.png",
    fullPage: true,
  });
  reply = "error";
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "may be outdated",
  );
  await expect(page.getByRole("table")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "Could not load markets",
  );
  reply = "empty";
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByText("No instruments were discovered.")).toBeVisible();
});

test("system reports API status, refresh failures, empty processes and mobile layout", async ({
  page,
}) => {
  await shell(page);
  let failed = false;
  let empty = false;
  await page.route("**/api/system", (route) =>
    route.fulfill(
      failed
        ? { status: 503, json: { detail: "fixture unavailable" } }
        : { json: { ...system, services: empty ? {} : system.services } },
    ),
  );
  await page.goto("/system");
  await page.getByLabel("Idioma").selectOption("en");
  await expect(
    page.getByRole("heading", { name: "Essential connections" }),
  ).toBeVisible();
  await expect(page.getByText("Last heartbeat 42 s ago")).toBeVisible();
  const summary = page.getByRole("region", {
    name: "Service summary",
    exact: true,
  });
  await expect(summary.locator("dd")).toHaveText(["4", "2", "2"]);
  await expect(
    page.locator(".service-row").filter({ hasText: "Market data" }),
  ).toContainText("Available");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.screenshot({
    path: "test-results/system-mobile.png",
    fullPage: true,
  });
  failed = true;
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.locator(".system-panel [role=alert]")).toContainText(
    "last successful check",
  );
  await expect(
    page.getByRole("heading", { name: "Summary from the last check" }),
  ).toBeVisible();
  await page.reload();
  await expect(page.locator(".system-panel [role=alert]")).toContainText(
    "Could not check the system",
  );
  failed = false;
  empty = true;
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByText("No process statuses received.")).toBeVisible();
  await expect(summary.locator("dd")).toHaveText(["3", "2", "1"]);
});

test("activity empty/error states and translated search preserve original event codes", async ({
  page,
}) => {
  await shell(page);
  let state: "empty" | "error" | "data" = "empty";
  await page.route("**/api/events**", (route) =>
    route.fulfill(
      state === "error"
        ? { status: 503, json: { detail: "fixture unavailable" } }
        : {
            json: {
              rows:
                state === "empty"
                  ? []
                  : [
                      {
                        id: "fixture-event-1",
                        timestamp: 1789300800,
                        event: "BOT_PAUSED",
                        message: "Original audit message",
                      },
                    ],
              next_before: null,
            },
          },
    ),
  );
  await page.goto("/events");
  await page.getByLabel("Idioma").selectOption("en");
  await expect(
    page.getByText("No activity has been recorded yet."),
  ).toBeVisible();
  state = "error";
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.locator(".activity-panel [role=alert]")).toContainText(
    "may be outdated",
  );
  state = "data";
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await page.getByLabel("Search events").fill("Instance paused");
  await expect(page.locator(".event-row")).toHaveCount(1);
  await page.getByText("View details", { exact: true }).click();
  await expect(page.locator(".event-details")).toContainText("BOT_PAUSED");
  await page.getByLabel("Language").selectOption("es");
  await page.getByLabel("Buscar eventos").fill("Instancia pausada");
  await expect(page.locator(".event-row strong")).toHaveText(
    "Instancia pausada",
  );
});

test("smart money direct route, loading, empty and populated states", async ({
  page,
}) => {
  await shell(page);
  let reply: "ok" | "error" | "empty" = "empty";
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const scored = {
    rows: [
      {
        wallet_id: "solana:abc123",
        status: "SCORED",
        score: "72.5",
        trade_count: 6,
        win_rate: "0.83",
        realized_pnl_usd: "450",
        computed_at: "2026-01-10T00:00:00Z",
        reasons: ["win_rate=0.83 over 6 completed trades"],
      },
      {
        wallet_id: "solana:thin",
        status: "INSUFFICIENT_DATA",
        score: null,
        trade_count: 2,
        win_rate: null,
        realized_pnl_usd: null,
        computed_at: "2026-01-10T00:00:00Z",
        reasons: ["only 2 completed round trip(s), need at least 5"],
      },
    ],
  };
  await page.route("**/api/intelligence/smart-money", async (route) => {
    await gate;
    await route.fulfill(
      reply === "error"
        ? { status: 503, json: { detail: "fixture unavailable" } }
        : { json: reply === "empty" ? { rows: [] } : scored },
    );
  });
  expect((await page.goto("/intelligence"))?.status()).toBe(200);
  await expect(
    page.getByText("Cargando puntajes de Smart Money"),
  ).toBeVisible();
  release();
  const smartMoneyPanel = page.locator("article.panel", {
    hasText: "Wallets Smart Money",
  });
  await expect(
    page.getByText("No hay wallets monitoreadas con puntaje todavía."),
  ).toBeVisible();
  reply = "ok";
  await smartMoneyPanel
    .getByRole("button", { name: "Actualizar", exact: true })
    .click();
  await expect(smartMoneyPanel.getByRole("row")).toHaveCount(3);
  await expect(page.getByText("solana:abc123")).toBeVisible();
  await expect(page.getByText("Datos insuficientes")).toBeVisible();
  reply = "error";
  await smartMoneyPanel
    .getByRole("button", { name: "Actualizar", exact: true })
    .click();
  await expect(smartMoneyPanel.getByRole("alert")).toContainText(
    "No se pudo actualizar",
  );
  await expect(smartMoneyPanel.getByRole("table")).toBeVisible();
});

test("whale flow and token risk sections render populated and empty states", async ({
  page,
}) => {
  await shell(page);
  await page.route("**/api/intelligence/whale-flow", async (route) => {
    await route.fulfill({
      json: {
        rows: [
          {
            wallet_id: "solana:whale-1",
            chain: "solana",
            token: "BONK",
            action: "TRANSFER",
            amount: "1000000",
            value_usd: "500000",
            threshold_usd: "100000",
            occurred_at: "2026-01-10T00:00:00Z",
            reasons: ["value_usd 500000 meets threshold 100000"],
          },
        ],
      },
    });
  });
  await page.route("**/api/intelligence/token-risk", async (route) => {
    await route.fulfill({ json: { rows: [] } });
  });
  expect((await page.goto("/intelligence"))?.status()).toBe(200);
  const whaleFlowPanel = page.locator("article.panel", {
    hasText: "Transferencias de ballenas",
  });
  await expect(whaleFlowPanel.getByText("solana:whale-1")).toBeVisible();
  await expect(whaleFlowPanel.getByText("BONK")).toBeVisible();
  const tokenRiskPanel = page.locator("article.panel", {
    hasText: "Riesgo de tokens",
  });
  await expect(
    tokenRiskPanel.getByText("No hay tokens evaluados todavía."),
  ).toBeVisible();
});

test("provider reliability and price consensus sections render populated and empty states", async ({
  page,
}) => {
  await shell(page);
  await page.route(
    "**/api/intelligence/provider-reliability",
    async (route) => {
      await route.fulfill({
        json: {
          rows: [
            {
              provider: "kraken",
              status: "HEALTHY",
              call_count: 100,
              error_rate: "0.01",
              average_latency_ms: "120",
              seconds_since_last_success: "5",
              computed_at: "2026-01-10T00:00:00Z",
              reasons: ["error_rate=0.01 below threshold"],
            },
          ],
        },
      });
    },
  );
  await page.route("**/api/intelligence/price-consensus", async (route) => {
    await route.fulfill({ json: { rows: [] } });
  });
  expect((await page.goto("/intelligence"))?.status()).toBe(200);
  const providerPanel = page.locator("article.panel", {
    hasText: "Confiabilidad de proveedores",
  });
  await expect(providerPanel.getByText("kraken")).toBeVisible();
  await expect(providerPanel.getByText("Saludable")).toBeVisible();
  const priceConsensusPanel = page.locator("article.panel", {
    hasText: "Consenso de precios",
  });
  await expect(
    priceConsensusPanel.getByText("No hay consensos calculados todavía."),
  ).toBeVisible();
});

test("wallet activity and entity graph sections render populated and empty states", async ({
  page,
}) => {
  await shell(page);
  await page.route("**/api/intelligence/wallet-activity", async (route) => {
    await route.fulfill({
      json: {
        rows: [
          {
            wallet_id: "solana:abc123",
            chain: "solana",
            token: "SOL",
            action: "SWAP",
            amount: "1",
            value_usd: "150",
            price: "150",
            occurred_at: "2026-01-10T00:00:00Z",
            attribution_source: "helius",
            attribution_confidence: "0.9",
          },
        ],
      },
    });
  });
  await page.route("**/api/intelligence/entity-graph", async (route) => {
    await route.fulfill({ json: { rows: [] } });
  });
  expect((await page.goto("/intelligence"))?.status()).toBe(200);
  const walletActivityPanel = page.locator("article.panel", {
    hasText: "Actividad de wallets",
  });
  await expect(walletActivityPanel.getByText("solana:abc123")).toBeVisible();
  await expect(
    walletActivityPanel.getByText("SOL", { exact: true }),
  ).toBeVisible();
  const entityGraphPanel = page.locator("article.panel", {
    hasText: "Grafo de correlación de entidades",
  });
  await expect(
    entityGraphPanel.getByText("No hay relaciones registradas todavía."),
  ).toBeVisible();
});

test("backtests page runs a backtest, refreshes history and surfaces a 422 as an alert", async ({
  page,
}) => {
  await shell(page);
  let historyRows: unknown[] = [];
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let runReply: "ok" | "error" = "ok";
  let submissions = 0;
  const runResult = {
    experiment_id: "exp-fixture-1",
    instrument_venue: "kraken",
    instrument_base: "XBT",
    instrument_quote: "USD",
    timeframe: "1h",
    trade_count: 2,
    starting_equity: "10000",
    final_equity: "10500",
    total_return_pct: "0.05",
    max_drawdown_pct: "0.02",
    win_rate: "0.5",
    created_at: "2026-01-10T00:00:00Z",
    bootstrap: null,
    walk_forward: null,
  };
  await page.route("**/api/backtests", async (route) => {
    if (route.request().method() === "GET") {
      await gate;
      await route.fulfill({ json: { rows: historyRows } });
      return;
    }
    if (runReply === "error") {
      await route.fulfill({
        status: 422,
        json: { detail: "need at least 5 candles, got 0" },
      });
      return;
    }
    submissions += 1;
    expect(route.request().postDataJSON()).toMatchObject({
      allocation_pct: "0.1",
      fee_rate: "0.001",
      slippage_pct: "0.0005",
    });
    expect(route.request().postDataJSON().window_start).toMatch(/Z$/);
    historyRows = [
      {
        experiment_id: runResult.experiment_id,
        strategy_id: "trend_following",
        instrument_venue: runResult.instrument_venue,
        instrument_base: runResult.instrument_base,
        instrument_quote: runResult.instrument_quote,
        timeframe: runResult.timeframe,
        window_start: "2026-01-01T00:00:00Z",
        window_end: "2026-01-02T00:00:00Z",
        trade_count: runResult.trade_count,
        starting_equity: runResult.starting_equity,
        final_equity: runResult.final_equity,
        total_return_pct: runResult.total_return_pct,
        max_drawdown_pct: runResult.max_drawdown_pct,
        win_rate: runResult.win_rate,
        created_at: runResult.created_at,
      },
    ];
    await route.fulfill({ json: runResult });
  });

  expect((await page.goto("/research"))?.status()).toBe(200);
  await expect(page.getByText("Cargando historial de backtests")).toBeVisible();
  release();
  await expect(
    page.getByText("Todavía no se ejecutó ningún backtest."),
  ).toBeVisible();

  await page.getByLabel("Desde").fill("2026-01-01T00:00");
  await page.getByLabel("Hasta").fill("2025-12-31T00:00");
  await page
    .getByRole("button", { name: "Ejecutar backtest", exact: true })
    .click();
  await expect(page.locator("#backtest-date-error")).toHaveText(
    "La fecha final debe ser posterior a la fecha inicial.",
  );
  expect(submissions).toBe(0);
  await page.getByLabel("Idioma").selectOption("en");
  await expect(page.locator("#backtest-date-error")).toHaveText(
    "The end date must be after the start date.",
  );
  await expect(page.getByLabel("Allocation (fraction)")).toHaveValue("0.1");
  await page.getByLabel("Language").selectOption("es");
  await page.getByLabel("Hasta").fill("2026-01-02T00:00");
  await page
    .getByRole("button", { name: "Ejecutar backtest", exact: true })
    .click();
  const resultPanel = page
    .getByRole("status")
    .filter({ hasText: "XBT/USD · 1h" });
  await expect(resultPanel).toBeVisible();
  await expect(resultPanel).toContainText("10500.00");
  expect(submissions).toBe(1);

  const historyTable = page.getByRole("region", {
    name: "Historial de experimentos",
  });
  await expect(historyTable.getByRole("row")).toHaveCount(2);
  await expect(historyTable.getByText("XBT/USD")).toBeVisible();

  runReply = "error";
  const runPanel = page.locator("article.panel", {
    hasText: "Ejecutar un backtest",
  });
  await runPanel
    .getByRole("button", { name: "Ejecutar backtest", exact: true })
    .click();
  await expect(runPanel.getByRole("alert")).toContainText(
    "need at least 5 candles",
  );
});

test("research jobs panel creates, lists and cancels a job", async ({ page }) => {
  await shell(page, "ADMIN");
  let jobs: Array<Record<string, unknown>> = [];
  await page.route("**/api/research/jobs", async (route) => {
    const method = route.request().method();
    if (method === "GET") {
      await route.fulfill({ json: { rows: jobs } });
      return;
    }
    if (method === "POST") {
      const job = {
        id: "job-1",
        experiment_id: "exp-42",
        purpose: "check drift",
        status: "PENDING",
        attempts: 0,
        cancel_requested: false,
        artifact_uri: null,
        error: null,
        created_at: 1758400000,
        claimed_at: null,
        completed_at: null,
      };
      jobs = [job];
      await route.fulfill({ json: job });
      return;
    }
    throw new Error(`Unexpected method for /api/research/jobs: ${method}`);
  });
  await page.route("**/api/research/jobs/job-1", async (route) => {
    const cancelled = {
      id: "job-1",
      experiment_id: "exp-42",
      purpose: "check drift",
      status: "CANCELLED",
      attempts: 0,
      cancel_requested: true,
      artifact_uri: null,
      error: null,
      created_at: 1758400000,
      claimed_at: null,
      completed_at: 1758400100,
    };
    jobs = [cancelled];
    await route.fulfill({ json: cancelled });
  });

  await page.goto("/research");
  const panel = page.locator("article.panel", {
    hasText: "Trabajos de investigación",
  });
  await expect(
    panel.getByText("Todavía no se envió ningún trabajo de investigación."),
  ).toBeVisible();

  await panel.getByLabel("Identificador del experimento").fill("exp-42");
  await panel.getByLabel("Propósito").fill("check drift");
  await panel
    .getByRole("button", { name: "Enviar a investigación" })
    .click();

  const row = panel.getByRole("row", { name: /exp-42/ });
  await expect(row).toContainText("Pendiente");
  await row.getByRole("button", { name: "Cancelar" }).click();
  await expect(row).toContainText("Cancelado");
  await expect(row.getByRole("button", { name: "Cancelar" })).toHaveCount(0);
});

test("proposals enforce expiry and show the recorded PAPER approval outcome", async ({ page }) => {
  await shell(page, "ADMIN");
  const now = Date.now();
  const proposal = {
    proposal_id: "current-proposal", venue: "kraken", base: "BTC", quote: "USD",
    direction: "LONG", confidence: "0.80", suggested_allocation_pct: "0.05",
    entry_price: "60000", stop_price: "57000", take_profit_price: "66000",
    reasons: ["Validated market context"], risks: ["Market volatility"], model_id: "consensus",
    as_of: new Date(now).toISOString(), expires_at: new Date(now + 3600000).toISOString(),
    decision_status: "PENDING", decided_at: null, simulation: null,
    execution: null as null | { status: string; client_order_id: string; reasons: string[] },
  };
  const expired = { ...proposal, proposal_id: "expired-proposal", expires_at: new Date(now - 60000).toISOString() };
  let approvalRequests = 0;
  await page.route("**/api/proposals", (route) => route.fulfill({ json: { rows: [proposal, expired] } }));
  await page.route("**/api/proposals/current-proposal/approve", async (route) => {
    approvalRequests += 1;
    expect(route.request().method()).toBe("POST");
    proposal.decision_status = "APPROVED";
    proposal.execution = { status: "FILLED", client_order_id: "paper-order", reasons: [] };
    await route.fulfill({ json: { proposal_id: proposal.proposal_id, status: "APPROVED", execution_status: "FILLED" } });
  });
  await page.goto("/intelligence?proposal=current-proposal&decision=approve#proposals");
  const current = page.locator("details").filter({ has: page.getByText("current-proposal", { exact: true }) });
  const stale = page.locator("details").filter({ has: page.getByText("expired-proposal", { exact: true }) });
  await expect(current).toHaveAttribute("open", "");
  expect(approvalRequests).toBe(0);
  await stale.locator("summary").click();
  await expect(stale.getByRole("button", { name: "Aprobar", exact: true })).toHaveCount(0);
  await expect(stale.getByRole("button", { name: "Simular", exact: true })).toHaveCount(0);
  await expect(stale.getByRole("button", { name: "Rechazar", exact: true })).toBeVisible();
  await expect(current.getByRole("button", { name: "Simular", exact: true })).toBeVisible();
  await current.getByRole("button", { name: "Aprobar", exact: true }).click();
  await expect(current.getByRole("status")).toContainText("Orden PAPER ejecutada");
  expect(approvalRequests).toBe(1);
  await expect(current.getByRole("button", { name: "Aprobar", exact: true })).toHaveCount(0);
});

test("LIVE proposals require explicit money confirmation and bind the limits version", async ({ page }) => {
  await shell(page, "ADMIN");
  await page.route("**/api/dashboard", route => route.fulfill({ json: { environment: "LIVE", status: "RUNNING", trading_available: true, equity: null, exchange: "KRAKEN_SPOT_REAL", positions: [], phase: 1 } }));
  await page.route("**/api/live", route => route.fulfill({ json: { capable: true, configured: true, enabled: true, state: "READY", reason: "", version: 7, connection_id: "00000000-0000-0000-0000-000000000007", max_order_usd: "25", max_daily_loss_usd: "5", max_total_usd: "100", slippage_pct: "0.005", equity_usd: "1000", as_of: new Date().toISOString(), balances: [], orders: [] } }));
  const now = Date.now();
  await page.route("**/api/proposals", route => route.fulfill({ json: { rows: [{ proposal_id: "live-proposal", venue: "kraken", base: "XBT", quote: "USD", direction: "LONG", confidence: "0.8", suggested_allocation_pct: "0.05", entry_price: "60000", stop_price: "57000", take_profit_price: "66000", reasons: ["Market context"], risks: ["Price risk"], model_id: "consensus", as_of: new Date(now).toISOString(), expires_at: new Date(now + 3600000).toISOString(), decision_status: "PENDING", decided_at: null, simulation: null, execution: null }] } }));
  let approvals = 0;
  await page.route("**/api/proposals/live-proposal/approve", async route => {
    approvals += 1;
    expect(route.request().postDataJSON()).toEqual({ environment: "LIVE", live_version: 7 });
    await route.fulfill({ json: { proposal_id: "live-proposal", status: "APPROVED", execution_status: "FILLED" } });
  });
  await page.goto("/intelligence?proposal=live-proposal#proposals");
  const action = page.getByRole("button", { name: "Aprobar operación real", exact: true });
  await expect(action).toBeDisabled();
  expect(approvals).toBe(0);
  await page.getByLabel("Confirmo esta operación con dinero real").check();
  await expect(action).toBeEnabled();
  await action.click();
  expect(approvals).toBe(1);
  await expect(action).toBeDisabled();
});

test("real account activation requires a connection, explicit limits and LIVE text", async ({ page }) => {
  await shell(page, "ADMIN");
  await page.route("**/api/connections", route => route.fulfill({ json: { rows: [{ id: "00000000-0000-0000-0000-000000000007", provider: "KRAKEN", label: "Cuenta Kraken", mode: "TRADE_ONLY", status: "HEALTHY", has_credentials: true, created_at: 1 }] } }));
  let submitted = 0;
  await page.route("**/api/live/control", async route => {
    const body = route.request().postDataJSON();
    expect(body).toMatchObject({ enabled: true, confirmation: "LIVE", max_order_usd: "25", max_daily_loss_usd: "5", max_total_usd: "100", slippage_pct: "0.005" });
    submitted += 1;
    await route.fulfill({ status: 409, json: { detail: "Exchange balances require reconciliation" } });
  });
  await page.goto("/settings");
  const panel = page.locator("article").filter({ has: page.getByRole("heading", { name: "Operaciones con dinero real", exact: true }) });
  const activate = panel.getByRole("button", { name: "Verificar cuenta y activar LIVE", exact: true });
  await expect(activate).toBeDisabled();
  await panel.getByLabel("Cuenta real", { exact: true }).selectOption("00000000-0000-0000-0000-000000000007");
  await panel.getByLabel("Máximo por operación (USD)", { exact: true }).fill("25");
  await panel.getByLabel("Pérdida diaria máxima (USD)", { exact: true }).fill("5");
  await panel.getByLabel("Exposición total máxima (USD)", { exact: true }).fill("100");
  await panel.getByLabel("Cambio de precio máximo (%)", { exact: true }).fill("0.5");
  await panel.getByLabel("Escribe LIVE para activar dinero real", { exact: true }).fill("LIVE");
  await activate.click();
  await expect(panel.getByRole("alert")).toContainText("Exchange balances require reconciliation");
  expect(submitted).toBe(1);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test("portfolio page shows the main account and the fully separate AI account", async ({
  page,
}) => {
  await shell(page, "ADMIN");
  let mainFunded = false;
  let aiFunded = false;
  const emptyView = {
    environment: "PAPER",
    connection_count: 0,
    balances: [] as Array<Record<string, unknown>>,
    activity: [],
    performance: [],
    proposal_history: [],
    orders: [],
  };
  await page.route("**/api/portfolio", async (route) => {
    if (route.request().method() === "POST") mainFunded = true;
    await route.fulfill({
      json: mainFunded
        ? { ...emptyView, balances: [{ currency: "USD", purpose: "CASH", amount: "10000" }] }
        : emptyView,
    });
  });
  await page.route("**/api/portfolio/ai/fund", async (route) => {
    aiFunded = true;
    await route.fulfill({
      json: { ...emptyView, balances: [{ currency: "USD", purpose: "CASH", amount: "5000" }] },
    });
  });
  await page.route("**/api/portfolio/ai", async (route) => {
    await route.fulfill({
      json: aiFunded
        ? { ...emptyView, balances: [{ currency: "USD", purpose: "CASH", amount: "5000" }] }
        : emptyView,
    });
  });
  await page.goto("/portfolio");
  await expect(page.getByRole("heading", { name: "Aún no hay saldos registrados" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Cuenta PAPER de IA" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "La cuenta de IA todavía no tiene saldo" }),
  ).toBeVisible();

  // Funding the AI account must never affect the main account, and vice versa -- they are fully
  // separate ledgers (.ai/DECISIONS.md, 2026-09-23).
  await page.getByRole("button", { name: "Fondear cuenta de IA" }).click();
  await expect(page.getByRole("row", { name: /USD Efectivo/ })).toContainText("5000");
  await expect(page.getByRole("heading", { name: "Aún no hay saldos registrados" })).toBeVisible();
});

test("AI position monitoring shows quote provenance, PnL and review levels on mobile", async ({ page }) => {
  await shell(page, "ADMIN");
  await page.route("**/api/portfolio/ai", route => route.fulfill({ json: {
    environment: "PAPER", connection_count: 0,
    balances: [{ currency: "BTC", purpose: "POSITION", amount: "0.005" }],
    activity: [], performance: [], orders: [],
    proposal_history: [{
      proposal_id: "tracked-proposal", base: "BTC", quote: "USD", direction: "BUY",
      filled_quantity: "0.005", filled_price: "50000", filled_at: "2026-10-08T00:00:00Z",
      held_for_seconds: 3600, stop_price: "48000", take_profit_price: "54000", execution_status: "FILLED",
      remaining_quantity: "0.005", realized_pnl: "0", current_price: "55000",
      quote_at: new Date().toISOString(), quote_source: "kraken", unrealized_pnl: "24.75",
      closed_at: null, monitoring_status: "TARGET_REACHED",
    }],
  } }));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/portfolio");
  const row = page.getByRole("row").filter({ hasText: "tracked-proposal" });
  await expect(row).toContainText("Objetivo alcanzado: revisar");
  await expect(row).toContainText("kraken");
  await expect(row).toContainText("24,75 USD");
  await expect(page.getByText(/Stop y objetivo son avisos de revisión/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
