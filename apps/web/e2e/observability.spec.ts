import { expect, test, type Page } from "@playwright/test";

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

async function shell(page: Page) {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const responses: Record<string, unknown> = {
      "/api/auth/setup-status": { setup_required: false },
      "/api/auth/me": {
        username: "ui-fixture",
        role: "VIEWER",
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
      "/api/system": system,
      "/api/events": [],
      "/api/intelligence/smart-money": { rows: [] },
      "/api/intelligence/whale-flow": { rows: [] },
      "/api/intelligence/token-risk": { rows: [] },
      "/api/intelligence/provider-reliability": { rows: [] },
      "/api/intelligence/price-consensus": { rows: [] },
      "/api/backtests": { rows: [] },
    };
    if (!(path in responses))
      throw new Error(`Unexpected API request: ${path}`);
    await route.fulfill({ json: responses[path] });
  });
}

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
  expect((await page.goto("/markets"))?.status()).toBe(200);
  await expect(page.getByRole("status")).toContainText("Cargando mercados");
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
  const detail = page.getByText("View reasons", { exact: true });
  await detail.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByText("QUALITY_FAILURE", { exact: true }),
  ).toBeVisible();
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
  await expect(page.getByRole("main").getByRole("alert")).toContainText("may be outdated");
  await expect(page.getByRole("table")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Could not load markets");
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
  await expect(
    page.locator(".service-row").filter({ hasText: "Exchange" }),
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
  await page.reload();
  await expect(page.locator(".system-panel [role=alert]")).toContainText(
    "Could not check the system",
  );
  failed = false;
  empty = true;
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByText("No process statuses received.")).toBeVisible();
});

test("activity empty/error states and translated search preserve original event codes", async ({
  page,
}) => {
  await shell(page);
  let state: "empty" | "error" | "data" = "empty";
  await page.route("**/api/events", (route) =>
    route.fulfill(
      state === "error"
        ? { status: 503, json: { detail: "fixture unavailable" } }
        : {
            json:
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
  await page.route("**/api/intelligence/provider-reliability", async (route) => {
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
  });
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
  await page.getByLabel("Hasta").fill("2026-01-02T00:00");
  await page
    .getByRole("button", { name: "Ejecutar backtest", exact: true })
    .click();
  const resultPanel = page.getByRole("status").filter({ hasText: "XBT/USD · 1h" });
  await expect(resultPanel).toBeVisible();
  await expect(resultPanel).toContainText("10500.00");

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
