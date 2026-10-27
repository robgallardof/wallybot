import { z } from "./validation";

let csrf = "";
const MFA_RECENCY_ERROR = "Sign in again with MFA to confirm this action";

type MfaRequest = { resolve: () => void; reject: (reason: Error) => void };
let pendingMfaRequest: Promise<void> | undefined;

function requestMfaConfirmation(): Promise<void> {
  if (pendingMfaRequest) return pendingMfaRequest;
  pendingMfaRequest = new Promise<void>((resolve, reject) => {
    window.dispatchEvent(
      new CustomEvent<MfaRequest>("wallybot:mfa-required", { detail: { resolve, reject } }),
    );
  }).finally(() => {
    pendingMfaRequest = undefined;
  });
  return pendingMfaRequest;
}
export function setCsrf(value: string) {
  csrf = value;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export async function api<T>(
  path: string,
  schema: z.ZodType<T>,
  body?: unknown,
  method?: "GET" | "POST" | "DELETE",
  retryAfterMfa = true,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: method ?? (body === undefined ? "GET" : "POST"),
    credentials: "same-origin",
    headers:
      body === undefined
        ? {}
        : { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const result: unknown = await response.json();
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/auth/"))
      window.location.assign("/login");
    const error = z.object({ detail: z.string() }).safeParse(result);
    if (
      retryAfterMfa &&
      response.status === 403 &&
      error.success &&
      error.data.detail === MFA_RECENCY_ERROR
    ) {
      await requestMfaConfirmation();
      return api(path, schema, body, method, false);
    }
    throw new ApiError(
      error.success ? error.data.detail : "No se pudo completar la solicitud",
      response.status,
    );
  }
  return schema.parse(result);
}
