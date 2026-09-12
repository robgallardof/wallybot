import { ArrowUpRight } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import i18n from "../../lib/i18n";
import { Button } from "../ui/button";

export function MfaForm({
  setup,
  secret,
  enrollmentUri,
  code,
  setCode,
  busy,
  onSubmit,
}: {
  setup: boolean;
  secret: string;
  enrollmentUri: string;
  code: string;
  setCode: (value: string) => void;
  busy: boolean;
  onSubmit: (event: React.FormEvent) => void;
}) {
  return (
    <form onSubmit={onSubmit}>
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
              {i18n.t("¿No puedes escanearlo? Introduce la clave manualmente")}
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
  );
}
