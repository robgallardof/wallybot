import i18n from "./i18n";

const labels: Record<string, string> = {
  ADMIN_CREATED: "Administrador creado",
  SESSION_CREATED: "Sesión iniciada",
  SESSION_REVOKED: "Sesión cerrada",
  RECOVERY_CODE_USED: "Código de recuperación utilizado",
  BOT_PAUSED: "Instancia pausada",
  BOT_RESUMED: "Instancia reanudada",
};

export function eventLabel(code: string): string {
  return labels[code] ? i18n.t(labels[code]) : code.replaceAll("_", " ");
}
