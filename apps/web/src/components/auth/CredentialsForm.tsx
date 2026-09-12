import type { UseFormReturn } from "react-hook-form";
import { ArrowUpRight } from "lucide-react";
import i18n from "../../lib/i18n";
import type { AuthFields } from "../../hooks/useAuthFlow";
import { Button } from "../ui/button";

export function CredentialsForm({
  setup,
  form,
  busy,
  onSubmit,
}: {
  setup: boolean;
  form: UseFormReturn<AuthFields>;
  busy: boolean;
  onSubmit: (values: AuthFields) => void;
}) {
  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
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
            {i18n.t("Disponible en el archivo local de configuración segura.")}
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
            aria-invalid={Boolean(form.formState.errors.confirm_password)}
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
            {i18n.t(error.message ?? "No se pudo completar la solicitud")}
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
  );
}
