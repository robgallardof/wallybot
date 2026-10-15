import i18n from "./i18n";

/** Locale-aware number with a sensible precision for prices, quantities and money. */
export function formatNumber(value: string | number | null | undefined, maxDigits = 8): string {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  const digits = Math.abs(number) >= 1000 ? 2 : Math.abs(number) >= 1 ? Math.min(4, maxDigits) : maxDigits;
  return new Intl.NumberFormat(i18n.resolvedLanguage, { maximumFractionDigits: digits }).format(number);
}

export function formatMoney(value: string | number | null | undefined, currency?: string | null): string {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  const text = new Intl.NumberFormat(i18n.resolvedLanguage, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(number);
  return currency ? `${text} ${currency}` : text;
}

export function formatPercent(ratio: number, digits = 1): string {
  return new Intl.NumberFormat(i18n.resolvedLanguage, {
    style: "percent",
    maximumFractionDigits: digits,
    signDisplay: "auto",
  }).format(ratio);
}

/** "en 12 min" / "hace 3 h" style relative time. */
export function formatRelative(iso: string, now = Date.now()): string {
  const seconds = Math.round((Date.parse(iso) - now) / 1000);
  const format = new Intl.RelativeTimeFormat(i18n.resolvedLanguage, { numeric: "auto" });
  const abs = Math.abs(seconds);
  if (abs < 60) return format.format(seconds, "second");
  if (abs < 3600) return format.format(Math.round(seconds / 60), "minute");
  if (abs < 86400) return format.format(Math.round(seconds / 3600), "hour");
  return format.format(Math.round(seconds / 86400), "day");
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat(i18n.resolvedLanguage, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(iso),
  );
}
