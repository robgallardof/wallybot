"use client";
import i18n from "./lib/i18n";
import { useTranslation } from "react-i18next";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import { z } from "zod";
import { api, setCsrf } from "./lib/api-client";
import { meSchema } from "./lib/dto";
import { Auth } from "./components/Auth";
import { Dashboard } from "./components/Dashboard";

const client = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: true } },
});

function App() {
  useTranslation();
  const setup = useQuery({
    queryKey: ["setup"],
    queryFn: () =>
      api("/auth/setup-status", z.object({ setup_required: z.boolean() })),
  });
  const me = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const user = await api("/auth/me", meSchema);
      setCsrf(user.csrf);
      return user;
    },
    enabled: setup.data?.setup_required === false,
  });
  if (setup.isPending || (setup.data?.setup_required === false && me.isPending))
    return (
      <div className="loading">
        wallybot <span>{i18n.t("Preparando tu espacio…")}</span>
      </div>
    );
  if (setup.error)
    return (
      <div className="loading">
        <h1>{i18n.t("El sistema aún no está disponible")}</h1>
        <p>{i18n.t("Comprueba PostgreSQL y el servicio API.")}</p>
        <button onClick={() => void setup.refetch()}>
          {i18n.t("Reintentar")}
        </button>
      </div>
    );
  if (me.data)
    return (
      <Dashboard
        user={me.data}
        logout={() => {
          void api("/auth/logout", z.object({ ok: z.boolean() }), {})
            .then(() => {
              client.clear();
              window.location.assign("/login");
            })
            .catch(() =>
              window.alert(
                i18n.t("No se pudo cerrar la sesión. Vuelve a intentarlo."),
              ),
            );
        }}
      />
    );
  return (
    <Auth
      setup={setup.data?.setup_required ?? false}
      complete={() => {
        client.clear();
        window.location.assign("/dashboard");
      }}
    />
  );
}

export default function Application() {
  return (
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>
  );
}
