import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { eventPageSchema } from "../../../lib/dto";
import type { InfiniteData, UseInfiniteQueryResult } from "@tanstack/react-query";
import type { z } from "zod";
import { EventList } from "../EventList";
import { eventLabel } from "../../../lib/event-label";

export function EventsPage({
  feed,
}: {
  feed: UseInfiniteQueryResult<InfiniteData<z.infer<typeof eventPageSchema>>, Error>;
}) {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [type, setType] = useState("all");
  const [order, setOrder] = useState("newest");
  // Flattened across every page fetched so far via "load more" (cursor pagination, oldest page
  // last) -- search/filter/sort below still run client-side, but now over the whole loaded
  // window instead of a fixed 100-row snapshot.
  const rows = feed.data?.pages.flatMap((page) => page.rows) ?? [];
  const types = [
    ...new Set([
      ...rows.map((event) => event.event),
      ...(type === "all" ? [] : [type]),
    ]),
  ].sort();
  const query = search.trim().toLocaleLowerCase();
  const visible = rows
    .filter(
      (event) =>
        (type === "all" || event.event === type) &&
        `${eventLabel(event.event)} ${event.event} ${event.message} ${event.id}`
          .toLocaleLowerCase()
          .includes(query),
    )
    .sort((a, b) =>
      order === "newest"
        ? b.timestamp - a.timestamp
        : a.timestamp - b.timestamp,
    );
  function reset() {
    setSearch("");
    setType("all");
    setOrder("newest");
  }

  return (
    <article className="panel wide-panel activity-panel">
      <div className="panel-heading">
        <div>
          <h2>{t("Registro de actividad")}</h2>
          <p>
            {t(
              "Busca y revisa el historial de eventos. Los filtros se aplican a los eventos cargados; usa «Cargar más eventos» para traer eventos anteriores.",
            )}
          </p>
        </div>
        <button
          className="button button-outline"
          onClick={() => void feed.refetch()}
          disabled={feed.isFetching}
        >
          {feed.isFetching ? t("Actualizando…") : t("Actualizar")}
        </button>
      </div>
      <div
        className="activity-filters"
        role="search"
        aria-label={t("Filtrar actividad")}
      >
        <label>
          {t("Buscar eventos")}
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t("Código, mensaje o identificador")}
          />
        </label>
        <label>
          {t("Tipo de evento")}
          <select
            value={type}
            onChange={(event) => setType(event.target.value)}
          >
            <option value="all">{t("Todos los tipos")}</option>
            {types.map((value) => (
              <option key={value} value={value}>
                {eventLabel(value)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("Orden")}
          <select
            value={order}
            onChange={(event) => setOrder(event.target.value)}
          >
            <option value="newest">{t("Más recientes primero")}</option>
            <option value="oldest">{t("Más antiguos primero")}</option>
          </select>
        </label>
      </div>
      {feed.isError && (
        <p className="error" role="alert">
          {feed.data
            ? t(
                "No se pudo actualizar la actividad. Se conserva la última consulta; puede estar desactualizada.",
              )
            : t("No se pudo cargar la actividad. Intenta actualizar de nuevo.")}
        </p>
      )}
      {feed.isPending ? (
        <p className="muted" role="status">
          {t("Cargando actividad…")}
        </p>
      ) : (
        feed.data && (
          <>
            <p className="activity-count" role="status">
              {t("{{shown}} de {{total}} eventos", {
                shown: visible.length,
                total: rows.length,
              })}
            </p>
            {visible.length ? (
              <EventList events={visible} detailed />
            ) : rows.length ? (
              <div className="activity-empty">
                <h3>{t("No hay eventos que coincidan")}</h3>
                <p className="muted">
                  {t("Prueba otra búsqueda o elimina los filtros.")}
                </p>
                <button className="button button-outline" onClick={reset}>
                  {t("Limpiar filtros")}
                </button>
              </div>
            ) : (
              <p className="muted">
                {t("Todavía no hay actividad registrada.")}
              </p>
            )}
            {feed.hasNextPage && (
              <div className="activity-load-more">
                <button
                  className="button button-outline"
                  onClick={() => void feed.fetchNextPage()}
                  disabled={feed.isFetchingNextPage}
                >
                  {feed.isFetchingNextPage
                    ? t("Cargando más…")
                    : t("Cargar más eventos")}
                </button>
              </div>
            )}
          </>
        )
      )}
    </article>
  );
}
