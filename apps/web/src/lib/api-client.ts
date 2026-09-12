import { z } from "zod";

let csrf = "";
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
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST",
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
    throw new ApiError(
      error.success ? error.data.detail : "No se pudo completar la solicitud",
      response.status,
    );
  }
  return schema.parse(result);
}
