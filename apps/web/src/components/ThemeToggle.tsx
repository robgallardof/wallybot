"use client";

import { useSyncExternalStore } from "react";
import { useTheme } from "next-themes";
import { FaMoon, FaSun } from "react-icons/fa6";
import { useTranslation } from "react-i18next";

const subscribeNoop = () => () => {};

export function ThemeToggle() {
  const { t } = useTranslation();
  const { resolvedTheme, setTheme } = useTheme();
  // next-themes only knows the resolved theme after mount, to avoid a server/client mismatch.
  // useSyncExternalStore reports false while server rendering/hydrating and true afterwards.
  const mounted = useSyncExternalStore(
    subscribeNoop,
    () => true,
    () => false,
  );
  if (!mounted) return <span className="theme-toggle" aria-hidden />;
  const dark = resolvedTheme === "dark";
  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={dark ? t("Cambiar a modo claro") : t("Cambiar a modo oscuro")}
      title={dark ? t("Cambiar a modo claro") : t("Cambiar a modo oscuro")}
      onClick={() => setTheme(dark ? "light" : "dark")}
    >
      {dark ? <FaSun size={15} /> : <FaMoon size={15} />}
    </button>
  );
}
