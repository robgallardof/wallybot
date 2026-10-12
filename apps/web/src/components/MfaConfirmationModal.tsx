import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { FaKey, FaXmark } from "react-icons/fa6";
import { z } from "zod";
import { api } from "../lib/api-client";
import i18n from "../lib/i18n";

type MfaRequest = { resolve: () => void; reject: (reason: Error) => void };

export function MfaConfirmationModal() {
  useTranslation();
  const [request, setRequest] = useState<MfaRequest | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    function show(event: Event) {
      setRequest((event as CustomEvent<MfaRequest>).detail);
      setCode("");
      setError("");
    }
    window.addEventListener("wallybot:mfa-required", show);
    return () => window.removeEventListener("wallybot:mfa-required", show);
  }, []);

  function close() {
    request?.reject(new Error("Acción cancelada"));
    setRequest(null);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!request || code.trim().length !== 6) return;
    setPending(true);
    setError("");
    try {
      await api("/auth/confirm-mfa", z.object({ ok: z.boolean() }), { code: code.trim() });
      request.resolve();
      setRequest(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : i18n.t("No se pudo confirmar tu identidad."));
    } finally {
      setPending(false);
    }
  }

  if (!request) return null;
  return (
    <div className="mfa-modal-backdrop" role="presentation">
      <section
        aria-describedby="mfa-confirmation-description"
        aria-labelledby="mfa-confirmation-title"
        aria-modal="true"
        className="mfa-modal"
        role="dialog"
      >
        <button aria-label={i18n.t("Cerrar")} className="mfa-modal-close" onClick={close}>
          <FaXmark size={17} />
        </button>
        <span className="mfa-modal-icon"><FaKey size={18} /></span>
        <h2 id="mfa-confirmation-title">{i18n.t("Confirmá tu identidad")}</h2>
        <p className="muted" id="mfa-confirmation-description">
          {i18n.t("Ingresá el código de tu autenticador para continuar. La acción se realizará automáticamente después de confirmarlo.")}
        </p>
        <form onSubmit={submit}>
          <label>
            {i18n.t("Código de autenticación")}
            <input
              autoComplete="one-time-code"
              autoFocus
              inputMode="numeric"
              maxLength={6}
              onChange={(event) => setCode(event.target.value)}
              placeholder="000000"
              value={code}
            />
          </label>
          {error && <p className="error" role="alert">{i18n.t(error)}</p>}
          <button className="button button-primary" disabled={pending || code.trim().length !== 6}>
            {i18n.t(pending ? "Confirmando…" : "Continuar")}
          </button>
        </form>
      </section>
    </div>
  );
}
