import i18n from "../lib/i18n";
import { useTranslation } from "react-i18next";
import { ShieldCheck } from "lucide-react";
import { useAuthFlow } from "../hooks/useAuthFlow";
import { LanguageSelector } from "./LanguageSelector";
import { ThemeToggle } from "./ThemeToggle";
import { CredentialsForm } from "./auth/CredentialsForm";
import { MfaForm } from "./auth/MfaForm";
import { RecoveryCodes } from "./auth/RecoveryCodes";

export function Auth({
  setup,
  complete,
}: {
  setup: boolean;
  complete: () => void;
}) {
  useTranslation();
  const {
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
  } = useAuthFlow({ setup, complete });

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
            <RecoveryCodes recovery={recovery} complete={complete} />
          ) : challenge ? (
            <MfaForm
              setup={setup}
              secret={secret}
              enrollmentUri={enrollmentUri}
              code={code}
              setCode={setCode}
              busy={busy}
              onSubmit={verify}
            />
          ) : (
            <CredentialsForm
              setup={setup}
              form={form}
              busy={busy}
              onSubmit={start}
            />
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
