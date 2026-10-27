/** Shared validation setup for the application's strict, nonce-based CSP. */
import { z } from "zod";

// Zod's JIT probe itself triggers a browser CSP violation, even when caught.
// Use its documented interpreter mode instead of enabling unsafe-eval.
z.config({ jitless: true });

export { z };
