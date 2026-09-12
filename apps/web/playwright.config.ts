import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45000,
  reporter: "list",
  use: { baseURL: "http://localhost:3334", trace: "off", screenshot: "off" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command:
      process.platform === "win32"
        ? "..\\..\\.venv\\Scripts\\python.exe ../../scripts/e2e_server.py"
        : "../../.venv/bin/python ../../scripts/e2e_server.py",
    url: "http://localhost:3334/health/ready",
    timeout: 120000,
    reuseExistingServer: false,
  },
});
