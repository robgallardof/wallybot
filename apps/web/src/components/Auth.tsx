import i18n from "../lib/i18n";
import { useTranslation } from "react-i18next";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowUpRight, ShieldCheck } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { api, setCsrf } from "../lib/api";
import { Button } from "./ui/button";
import { LanguageSelector } from "./LanguageSelector";
import { ThemeToggle } from "./ThemeToggle";

const fields = z.object({
  username: z.string().min(3, "Usa un usuario de al menos 3 caracteres."),
  password: z.string().min(1, "Introduce tu contraseña."),
  bootstrap_token: z.string().optional(),
  confirm_password: z.string().optional(),
});
type Fields = z.infer<typeof fields>;

export function Auth({
  setup,
  complete,
}: {
  setup: boolean;
  complete: () => void;
}) {
  useTranslation();
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
  const form = useForm<Fields>({ resolver: zodResolver(schema) });

  async function start(values: Fields) {
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

  return (
    <main className="auth-layout">
      <section className="auth-story">
        <a className="brand" href="/">
          wally<span>bot</span>
          <i />
        </a>
        <div>
          <span className="eyebrow">{i18n.t("TU CAPITAL. TUS REGLAS.")}</span>
          <h1>
            {i18n.t("La disciplina")}
            <br />
            {i18n.t("es el punto")}
            <br />
            {i18n.t("de partida.")}
          </h1>
          <p>
            {i18n.t(
              "Un espacio privado para observar los mercados, investigar ideas y medir cada decisión.",
            )}
          </p>
        </div>
        <small>
          <ShieldCheck size={16} />{" "}
          {i18n.t("Entorno PAPER · Sin operaciones reales")}
        </small>
      </section>
      <section className="auth-panel">
        <div className="auth-card">
          <div className="flex items-center justify-end gap-2 mb-5">
            <LanguageSelector />
            <ThemeToggle />
          </div>
          <span className="eyebrow">{i18n.t("WALLYBOT / ACCESO PRIVADO")}</span>
          <h2>
            {recovery.length
              ? i18n.t("Guarda tus códigos")
              : challenge
                ? i18n.t("Verifica tu identidad")
                : setup
                  ? i18n.t("Prepara tu espacio")
                  : i18n.t("Bienvenido de nuevo")}
          </h2>
          <p className="muted">
            {setup
              ? i18n.t(
                  "Configura tu cuenta de administrador y la verificación en dos pasos.",
                )
              : i18n.t("Accede a tu centro de control.")}
          </p>
          {error && (
            <p role="alert" className="error">
              {i18n.t(error)}
            </p>
          )}
          {recovery.length > 0 ? (
            <div>
              <p>
                {i18n.t(
                  "Estos códigos se muestran una sola vez. Guárdalos en tu gestor de contraseñas; cada uno permite un acceso si pierdes tu autenticador.",
                )}
              </p>
              <pre className="recovery">{recovery.join("\n")}</pre>
              <Button onClick={complete}>
                {i18n.t("Ya los guardé. Abrir panel")}
                <ArrowUpRight size={16} />
              </Button>
            </div>
          ) : challenge ? (
            <form onSubmit={verify}>
              {secret && (
                <div className="enrollment">
                  <p>
                    {i18n.t(
                      "Escanea este QR con tu aplicación de autenticación. Después, introduce el código de 6 dígitos que aparezca en la app.",
                    )}
                  </p>
                  <QRCodeSVG
                    value={enrollmentUri}
                    size={224}
                    marginSize={4}
                    level="M"
                    role="img"
                    title={i18n.t(
                      "Código QR para configurar WallyBot en tu autenticador",
                    )}
                    className="enrollment-qr"
                  />
                  <details>
                    <summary>
                      {i18n.t(
                        "¿No puedes escanearlo? Introduce la clave manualmente",
                      )}
                    </summary>
                    <p>
                      {i18n.t(
                        "Añade una cuenta llamada WallyBot con esta clave. Elige códigos basados en tiempo (TOTP), 6 dígitos y 30 segundos.",
                      )}
                    </p>
                    <code>{secret}</code>
                  </details>
                </div>
              )}
              <label>
                {i18n.t("Código de verificación")}
                <input
                  autoComplete="one-time-code"
                  autoFocus
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  required
                  maxLength={128}
                />
              </label>
              {!setup && (
                <small className="muted">
                  {i18n.t(
                    "También puedes usar un código de recuperación. Si acabas de usar un código TOTP, espera el siguiente.",
                  )}
                </small>
              )}
              <Button disabled={busy}>
                {busy ? i18n.t("Verificando…") : i18n.t("Verificar y entrar")}{" "}
                <ArrowUpRight size={16} />
              </Button>
            </form>
          ) : (
            <form onSubmit={form.handleSubmit(start)}>
              {setup && (
                <label>
                  {i18n.t("Token de configuración")}
                  <input
                    type="password"
                    autoComplete="off"
                    {...form.register("bootstrap_token")}
                    required
                    minLength={32}
                  />
                  <small className="muted">
                    {i18n.t(
                      "Disponible en el archivo local de configuración segura.",
                    )}
                  </small>
                </label>
              )}
              <label>
                {i18n.t("Usuario")}
                <input
                  autoComplete="username"
                  {...form.register("username")}
                  required
                  minLength={3}
                />
              </label>
              <label>
                {i18n.t("Contraseña")}
                <input
                  type="password"
                  autoComplete={setup ? "new-password" : "current-password"}
                  {...form.register("password")}
                  required
                  minLength={setup ? 12 : 1}
                />
              </label>
              {setup && (
                <label>
                  <span id="confirm-password-label">
                    {i18n.t("Confirmar contraseña")}
                  </span>
                  <input
                    type="password"
                    autoComplete="new-password"
                    {...form.register("confirm_password")}
                    aria-labelledby="confirm-password-label"
                    required
                    aria-invalid={Boolean(
                      form.formState.errors.confirm_password,
                    )}
                    aria-describedby={
                      form.formState.errors.confirm_password
                        ? "confirm-password-error"
                        : undefined
                    }
                  />
                  {form.formState.errors.confirm_password && (
                    <small id="confirm-password-error" role="alert">
                      {i18n.t(
                        form.formState.errors.confirm_password.message ??
                          "Las contraseñas no coinciden.",
                      )}
                    </small>
                  )}
                </label>
              )}
              {Object.entries(form.formState.errors)
                .filter(([field]) => field !== "confirm_password")
                .map(([, error], i) => (
                  <small role="alert" key={i}>
                    {i18n.t(
                      error.message ?? "No se pudo completar la solicitud",
                    )}
                  </small>
                ))}
              <Button disabled={busy}>
                {busy
                  ? i18n.t("Validando…")
                  : setup
                    ? i18n.t("Configurar autenticación")
                    : i18n.t("Continuar")}{" "}
                <ArrowUpRight size={16} />
              </Button>
            </form>
          )}
          <footer>
            <ShieldCheck size={15} />{" "}
            {i18n.t("Acceso protegido con contraseña y TOTP")}
          </footer>
        </div>
      </section>
    </main>
  );
}
