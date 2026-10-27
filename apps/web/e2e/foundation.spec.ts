import { createHmac } from "node:crypto";
import { expect, test } from "@playwright/test";

function totp(secret: string): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const bits = [...secret]
    .map((char) => alphabet.indexOf(char).toString(2).padStart(5, "0"))
    .join("");
  const bytes = bits.match(/.{8}/g)!.map((byte) => Number.parseInt(byte, 2));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const hash = createHmac("sha1", Buffer.from(bytes)).update(counter).digest();
  const offset = hash[19] & 15;
  return ((hash.readUInt32BE(offset) & 0x7fffffff) % 1000000)
    .toString()
    .padStart(6, "0");
}

test("setup, MFA, dashboard, controls, activity, logout and recovery login", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const policyViolations: string[] = [];
  await page.exposeFunction("recordPolicyViolation", (directive: string) => {
    policyViolations.push(directive);
  });
  await page.addInitScript(() => {
    document.addEventListener("securitypolicyviolation", (event) => {
      const report = (
        window as unknown as {
          recordPolicyViolation: (directive: string) => void;
        }
      ).recordPolicyViolation;
      report(
        `${event.effectiveDirective}: ${event.blockedURI} at ${event.sourceFile}:${event.lineNumber}`,
      );
    });
  });
  await page.goto("/setup");
  await page.getByRole("button", { name: "Cambiar a modo oscuro" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await expect(page.locator(".auth-panel")).toHaveCSS(
    "background-color",
    "rgb(28, 28, 31)",
  );
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Cambiar a modo claro" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/setup-dark.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Cambiar a modo claro" }).click();
  await page.getByLabel("Idioma").selectOption("en");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(
    page.getByRole("heading", { name: "Set up your workspace" }),
  ).toBeVisible();
  await page.getByLabel("Language").selectOption("es");
  await page
    .getByLabel("Token de configuración")
    .fill("browser-test-only-bootstrap-token-0001");
  await page.getByLabel("Usuario", { exact: true }).fill("browser-admin");
  await page
    .getByLabel("Contraseña", { exact: true })
    .fill("browser-only-long-password");
  let setupRequests = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/auth/setup/start")) {
      setupRequests += 1;
      expect(request.postDataJSON()).not.toHaveProperty("confirm_password");
    }
  });
  await page
    .getByLabel("Confirmar contraseña", { exact: true })
    .fill("different-password");
  await page.getByRole("button", { name: "Configurar autenticación" }).click();
  await expect(page.getByText("Las contraseñas no coinciden.")).toBeVisible();
  expect(setupRequests).toBe(0);
  await page.getByLabel("Idioma").selectOption("en");
  await expect(page.getByText("Passwords do not match.")).toBeVisible();
  await page.getByLabel("Language").selectOption("es");
  await page
    .getByLabel("Confirmar contraseña", { exact: true })
    .fill("browser-only-long-password");
  await page.getByRole("button", { name: "Configurar autenticación" }).click();
  await expect(
    page.getByRole("img", {
      name: "Código QR para configurar WallyBot en tu autenticador",
    }),
  ).toBeVisible();
  await expect(page.locator(".enrollment code")).toBeHidden();
  await page
    .getByText("¿No puedes escanearlo? Introduce la clave manualmente")
    .click();
  await expect(page.locator(".enrollment code")).toBeVisible();
  const secret = await page.locator(".enrollment code").textContent();
  await page.getByLabel("Código de verificación").fill(totp(secret!));
  await page.getByRole("button", { name: "Verificar y entrar" }).click();
  await expect(
    page.getByRole("heading", { name: "Guarda tus códigos" }),
  ).toBeVisible();
  const recovery = (await page.locator(".recovery").textContent())!.split(
    "\n",
  )[0];
  await page
    .getByRole("button", { name: "Ya los guardé. Abrir panel" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Una visión clara." }),
  ).toBeVisible();
  await expect(
    page.getByText("Sin resultados ficticios. Sin rentabilidad supuesta."),
  ).toBeVisible();
  await page.getByLabel("Idioma").selectOption("en");
  await expect(
    page.getByRole("heading", { name: "A clear view." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "System", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Services and dependencies" }),
  ).toBeVisible();
  await page.getByLabel("Language").selectOption("es");
  await page.getByRole("button", { name: "Resumen", exact: true }).click();
  await page.screenshot({
    path: "test-results/dashboard-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Cambiar a modo oscuro" }).click();
  await expect(page.locator(".metric").first()).toHaveCSS(
    "background-color",
    "rgb(28, 28, 31)",
  );
  await page.screenshot({
    path: "test-results/dashboard-dark.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Cambiar a modo claro" }).click();
  await page.getByRole("button", { name: "Riesgo", exact: true }).click();
  await page
    .getByRole("button", { name: "Pausar instancia", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Instancia pausada" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Instancia pausada" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Reanudar instancia", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Instancia en preparación" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Actividad", exact: true }).click();
  await expect(
    page.locator(".event-row strong").filter({ hasText: "Instancia pausada" }),
  ).toBeVisible();
  await page.getByLabel("Buscar eventos").fill("no-such-event-12345");
  await expect(
    page.getByRole("heading", { name: "No hay eventos que coincidan" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Limpiar filtros" }).click();
  await page.getByLabel("Tipo de evento").selectOption("BOT_PAUSED");
  await expect(page.locator(".activity-panel .event-row")).toHaveCount(1);
  await page.getByText("Ver detalles", { exact: true }).click();
  await expect(
    page.getByText("Código del evento", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".event-details code").last()).toHaveText(
    "BOT_PAUSED",
  );
  await page.getByLabel("Idioma").selectOption("en");
  await expect(page.getByText("View details", { exact: true })).toBeVisible();
  await page.getByLabel("Language").selectOption("es");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.screenshot({
    path: "test-results/activity-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.getByRole("button", { name: "Sistema", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Servicios y dependencias" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Configuración", exact: true }).click();
  const modeSwitch = page.getByRole("group", { name: "Modo de operación" });
  const modeOption = (mode: string) =>
    modeSwitch.getByRole("button", { name: new RegExp(`^${mode}\\b`) });
  await expect(modeOption("OBSERVE")).toHaveAttribute("aria-pressed", "true");
  await expect(modeOption("PAPER")).toHaveAttribute("aria-pressed", "false");
  await modeOption("PAPER").click();
  await expect(modeOption("PAPER")).toHaveAttribute("aria-pressed", "true");
  await expect(modeOption("OBSERVE")).toHaveAttribute("aria-pressed", "false");
  await expect(page.locator(".paper-pill")).toHaveText("PAPER");
  await page.reload();
  await expect(modeOption("PAPER")).toHaveAttribute("aria-pressed", "true");
  await modeOption("OBSERVE").click();
  await expect(modeOption("OBSERVE")).toHaveAttribute("aria-pressed", "true");
  await expect(modeOption("PAPER")).toHaveAttribute("aria-pressed", "false");
  await expect(page.locator(".paper-pill")).toHaveText("OBSERVE");
  await page.getByRole("button", { name: "Documentación", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Cómo funciona realmente WallyBot" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Comandos de tu bot" })).toBeVisible();
  await expect(page.getByText("/proposals", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Abrir navegación" }).click();
  await page.getByRole("button", { name: "Resumen", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Una visión clara." }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.screenshot({
    path: "test-results/dashboard-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1280, height: 720 });
  await page
    .getByRole("button", { name: "Cerrar sesión", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Bienvenido de nuevo" }),
  ).toBeVisible();
  await page.getByLabel("Usuario", { exact: true }).fill("browser-admin");
  await page
    .getByLabel("Contraseña", { exact: true })
    .fill("browser-only-long-password");
  await page.getByRole("button", { name: "Continuar", exact: true }).click();
  await page.getByLabel("Código de verificación").fill(recovery);
  await page.getByRole("button", { name: "Verificar y entrar" }).click();
  await expect(
    page.getByRole("heading", { name: "Una visión clara." }),
  ).toBeVisible();
  expect(errors).toEqual([]);
  if (process.env.WALLY_E2E_PRODUCTION === "1")
    expect(policyViolations).toEqual([]);
});

test("production HTML uses a fresh nonce and known Next routes", async ({
  request,
}) => {
  test.skip(
    process.env.WALLY_E2E_PRODUCTION !== "1",
    "Production-only security check",
  );
  const first = await request.get("/setup");
  const second = await request.get("/setup");
  expect(first.status()).toBe(200);
  const policy = first.headers()["content-security-policy"];
  expect(policy).toContain("'strict-dynamic'");
  expect(policy).not.toContain("'unsafe-eval'");
  expect(policy).not.toContain("'unsafe-inline'");
  const nonce = /'nonce-([^']+)'/.exec(policy)?.[1];
  expect(nonce).toBeTruthy();
  expect(second.headers()["content-security-policy"]).not.toBe(policy);
  expect(await first.text()).toContain(`nonce="${nonce}"`);
  expect((await request.get("/not-a-wallybot-page")).status()).toBe(404);
});
