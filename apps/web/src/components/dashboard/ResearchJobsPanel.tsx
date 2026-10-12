import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import i18n from "../../lib/i18n";
import type { researchJobListSchema, researchJobSchema } from "../../lib/dto";
import type { CreateResearchJobInput } from "../../hooks/useResearchJobsData";
import { ApiError } from "../../lib/api-client";
import { Button } from "../ui/button";

const ACTIVE_STATUSES = new Set(["PENDING", "RUNNING"]);

const STATUS_LABELS: Record<string, string> = {
  PENDING: "Pendiente",
  RUNNING: "En curso",
  CANCELLED: "Cancelado",
  COMPLETED: "Completado",
  FAILED: "Fallido",
};

export function ResearchJobsPanel({
  jobs,
  create,
  cancel,
  role,
}: {
  jobs: UseQueryResult<z.infer<typeof researchJobListSchema>>;
  create: UseMutationResult<
    z.infer<typeof researchJobSchema>,
    Error,
    CreateResearchJobInput
  >;
  cancel: UseMutationResult<z.infer<typeof researchJobSchema>, Error, string>;
  role: string;
}) {
  useTranslation();
  const [experimentId, setExperimentId] = useState("");
  const [purpose, setPurpose] = useState("");
  const rows = jobs.data?.rows ?? [];

  function submit(event: React.FormEvent) {
    event.preventDefault();
    create.mutate(
      { experiment_id: experimentId.trim(), purpose: purpose.trim() },
      { onSuccess: () => setPurpose("") },
    );
  }

  const date = (value: number) =>
    new Date(value * 1000).toLocaleString(i18n.resolvedLanguage);

  return (
    <article className="panel wide-panel">
      <div className="panel-heading">
        <h2>{i18n.t("Trabajos de investigación")}</h2>
      </div>
      <p className="muted">
        {i18n.t(
          "Reejecuta un experimento existente de forma aislada, sin acceso a claves ni límites de ejecución. Pegá el identificador de un experimento del historial de abajo.",
        )}
      </p>
      {role === "ADMIN" && (
        <form className="backtest-form" onSubmit={submit}>
          <label>
            {i18n.t("Identificador del experimento")}
            <input
              value={experimentId}
              onChange={(event) => setExperimentId(event.target.value)}
              placeholder="exp-..."
              required
              maxLength={100}
              pattern=".*\S.*"
            />
          </label>
          <label>
            {i18n.t("Propósito")}
            <input
              value={purpose}
              onChange={(event) => setPurpose(event.target.value)}
              placeholder={i18n.t("Ej: verificar sensibilidad a slippage")}
              required
              maxLength={256}
              pattern=".*\S.*"
            />
          </label>
          <button
            className="button button-primary"
            type="submit"
            disabled={create.isPending}
          >
            {i18n.t(create.isPending ? "Enviando…" : "Enviar a investigación")}
          </button>
        </form>
      )}
      {create.isError && (
        <p role="alert" className="error">
          {create.error instanceof ApiError
            ? create.error.message
            : i18n.t("No se pudo crear el trabajo de investigación.")}
        </p>
      )}
      {jobs.isPending && <p className="muted">{i18n.t("Cargando…")}</p>}
      {jobs.isError && (
        <p className="error" role="alert">
          {i18n.t("No se pudieron cargar los trabajos de investigación.")}
        </p>
      )}
      {jobs.data && rows.length === 0 && (
        <p className="muted">
          {i18n.t("Todavía no se envió ningún trabajo de investigación.")}
        </p>
      )}
      {rows.length > 0 && (
        <div className="markets-table-wrap">
          <table className="markets-table">
            <thead>
              <tr>
                <th>{i18n.t("Experimento")}</th>
                <th>{i18n.t("Propósito")}</th>
                <th>{i18n.t("Estado")}</th>
                <th>{i18n.t("Intentos")}</th>
                <th>{i18n.t("Resultado")}</th>
                <th>{i18n.t("Solicitado")}</th>
                {role === "ADMIN" && <th>{i18n.t("Acción")}</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <code>{row.experiment_id}</code>
                  </td>
                  <td>{row.purpose}</td>
                  <td>{i18n.t(STATUS_LABELS[row.status] ?? row.status)}</td>
                  <td>{row.attempts}</td>
                  <td>
                    {row.artifact_uri ? (
                      <a
                        href={`/api/backtests/export?format=json&experiment_id=${encodeURIComponent(row.artifact_uri)}`}
                        download
                      >
                        {i18n.t("Descargar resultado")}
                      </a>
                    ) : row.error ? (
                      row.error
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>{date(row.created_at)}</td>
                  {role === "ADMIN" && (
                    <td>
                      {ACTIVE_STATUSES.has(row.status) && (
                        <Button
                          disabled={cancel.isPending}
                          onClick={() => cancel.mutate(row.id)}
                        >
                          {i18n.t("Cancelar")}
                        </Button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {cancel.isError && (
        <p role="alert" className="error">
          {i18n.t(cancel.error.message)}
        </p>
      )}
    </article>
  );
}
