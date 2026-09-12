import { useTranslation } from "react-i18next";
import i18n from "../../../lib/i18n";
import type { eventsSchema } from "../../../lib/dto";
import type { UseQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import { EventList } from "../EventList";

export function EventsPage({
  events,
}: {
  events: UseQueryResult<z.infer<typeof eventsSchema>>;
}) {
  useTranslation();
  return (
    <article className="panel wide-panel">
      <div className="panel-heading">
        <h2>{i18n.t("Registro de actividad")}</h2>
        <span className="subtle-pill">{i18n.t("ÚLTIMOS 100 EVENTOS")}</span>
      </div>
      <EventList events={events.data} />
    </article>
  );
}
