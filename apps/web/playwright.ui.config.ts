import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

// Only specs that intercept every API request may run without a backend.
export default defineConfig({
  ...base,
  testMatch: "observability.spec.ts",
  webServer: {
    command:
      process.platform === "win32"
        ? "..\\..\\.venv\\Scripts\\python.exe ../../scripts/ui_test_server.py"
        : "../../.venv/bin/python ../../scripts/ui_test_server.py",
    url: "http://localhost:3334/login",
    timeout: 120000,
    reuseExistingServer: false,
  },
});
