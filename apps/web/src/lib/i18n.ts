import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import es from "./locales/es.json";

let language = "es";
try {
  if (localStorage.getItem("wallybot.language") === "en") language = "en";
} catch {
  /* Language switching also works when storage is unavailable. */
}

void i18n.use(initReactI18next).init({
  resources: {
    en: {
      translation: {
        ...Object.fromEntries(Object.keys(es).map((key) => [key, key])),
        ...en,
      },
    },
    es: {
      translation: {
        ...Object.fromEntries(Object.keys(en).map((key) => [key, key])),
        ...es,
      },
    },
  },
  lng: language,
  fallbackLng: "es",
  supportedLngs: ["es", "en"],
  keySeparator: false,
  nsSeparator: false,
  interpolation: { escapeValue: false },
});
document.documentElement.lang = language;
i18n.on("languageChanged", (value) => {
  document.documentElement.lang = value;
  try {
    localStorage.setItem("wallybot.language", value);
  } catch {
    /* Optional persistence. */
  }
});
export default i18n;
