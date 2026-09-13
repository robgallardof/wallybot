import { useTranslation } from "react-i18next";
import { Activity } from "lucide-react";
import i18n from "../../lib/i18n";
import { eventLabel } from "../../lib/event-label";
import type { eventsSchema } from "../../lib/dto";
import type { z } from "zod";

export function EventList({
  events,
  detailed = false,
}: {
  events?: z.infer<typeof eventsSchema>;
  detailed?: boolean;
}) {
  useTranslation();
  if (!events)
    return (
      <p className="muted" role="status">
        {i18n.t("Cargando actividad…")}
      </p>
    );
  if (!events.length)
    return (
      <p className="muted">{i18n.t("Todavía no hay actividad registrada.")}</p>
    );
  return (
    <div className="event-list">
      {events.map((event) => (
        <div key={event.id} className="event-row">
          <span className="event-icon">
            <Activity size={15} />
          </span>
          <div>
            <strong>{eventLabel(event.event)}</strong>
            <small>{event.message}</small>
            {detailed && (
              <details className="event-details">
                <summary>{i18n.t("Ver detalles")}</summary>
                <dl>
                  <dt>{i18n.t("Identificador")}</dt>
                  <dd>
                    <code>{event.id}</code>
                  </dd>
                  <dt>{i18n.t("Código del evento")}</dt>
                  <dd>
                    <code>{event.event}</code>
                  </dd>
                  <dt>{i18n.t("Fecha y hora (UTC)")}</dt>
                  <dd>{new Date(event.timestamp * 1000).toISOString()}</dd>
                </dl>
              </details>
            )}
          </div>
          <time dateTime={new Date(event.timestamp * 1000).toISOString()}>
            {detailed
              ? new Intl.DateTimeFormat(i18n.resolvedLanguage, {
                  dateStyle: "medium",
                  timeStyle: "short",
                  timeZone: "UTC",
                }).format(new Date(event.timestamp * 1000))
              : new Date(event.timestamp * 1000).toLocaleTimeString(
                  i18n.resolvedLanguage,
                  {
                    timeZone: "UTC",
                    hour: "2-digit",
                    minute: "2-digit",
                  },
                )}{" "}
            UTC
          </time>
        </div>
      ))}
    </div>
  );
}
