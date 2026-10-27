import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "../lib/validation";
import i18n from "../lib/i18n";
import { api, setCsrf } from "../lib/api-client";

const fields = z.object({
  username: z.string().min(3, "Usa un usuario de al menos 3 caracteres."),
  password: z.string().min(1, "Introduce tu contraseña."),
  bootstrap_token: z.string().optional(),
  confirm_password: z.string().optional(),
});
export type AuthFields = z.infer<typeof fields>;

export function useAuthFlow({
  setup,
  complete,
}: {
  setup: boolean;
  complete: () => void;
}) {
  const [challenge, setChallenge] = useState("");
  const [secret, setSecret] = useState("");
  const [enrollmentUri, setEnrollmentUri] = useState("");
  const [bootstrap, setBootstrap] = useState("");
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const schema = fields.superRefine((values, context) => {
    if (setup && values.password !== values.confirm_password) {
      context.addIssue({
        code: "custom",
        path: ["confirm_password"],
        message: "Las contraseñas no coinciden.",
      });
    }
  });
  const form = useForm<AuthFields>({ resolver: zodResolver(schema) });

  async function start(values: AuthFields) {
    setError("");
    setBusy(true);
    try {
      if (setup) {
        if (values.password.length < 12)
          throw new Error("Usa una contraseña de al menos 12 caracteres.");
        const result = await api(
          "/auth/setup/start",
          z.object({
            challenge: z.string(),
            secret: z.string(),
            uri: z.string(),
          }),
          {
            username: values.username,
            password: values.password,
            bootstrap_token: values.bootstrap_token,
          },
        );
        setBootstrap(values.bootstrap_token ?? "");
        setSecret(result.secret);
        setEnrollmentUri(result.uri);
        setChallenge(result.challenge);
      } else {
        const result = await api(
          "/auth/login",
          z.object({ challenge: z.string() }),
          { username: values.username, password: values.password },
        );
        setChallenge(result.challenge);
      }
      form.reset();
    } catch (e) {
      setError(e instanceof Error ? e.message : i18n.t("Error de conexión"));
    } finally {
      setBusy(false);
    }
  }

  async function verify(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (setup) {
        const result = await api(
          "/auth/setup/finish",
          z.object({ recovery_codes: z.array(z.string()), csrf: z.string() }),
          { bootstrap_token: bootstrap, challenge, code },
        );
        setCsrf(result.csrf);
        setRecovery(result.recovery_codes);
        setSecret("");
        setEnrollmentUri("");
        setBootstrap("");
      } else {
        const result = await api("/auth/mfa", z.object({ csrf: z.string() }), {
          challenge,
          code,
        });
        setCsrf(result.csrf);
        complete();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : i18n.t("Error de conexión"));
    } finally {
      setBusy(false);
      setCode("");
    }
  }

  return {
    form,
    start,
    verify,
    challenge,
    secret,
    enrollmentUri,
    code,
    setCode,
    recovery,
    error,
    busy,
  };
}
