import { useTranslation } from "react-i18next";
import { Activity } from "lucide-react";
import i18n from "../../lib/i18n";
import type { eventsSchema } from "../../lib/dto";
import type { z } from "zod";

export function EventList({ events }: { events?: z.infer<typeof eventsSchema> }) {
  useTranslation();
  if (!events) return <p className="muted">{i18n.t("Cargando actividad…")}</p>;
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
            <strong>{event.event.replaceAll("_", " ")}</strong>
            <small>{event.message}</small>
          </div>
          <time>
            {new Date(event.timestamp * 1000).toLocaleTimeString(
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
