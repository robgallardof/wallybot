"use client";

import dynamic from "next/dynamic";

// Authentication state and language preference belong only to this browser.
const Application = dynamic(() => import("../Application"), {
  ssr: false,
  loading: () => (
    <div className="loading" aria-label="WallyBot">
      wallybot
    </div>
  ),
});
// Installable web app: the service worker never caches API data (see public/sw.js).
if (typeof window !== "undefined" && "serviceWorker" in navigator && window.isSecureContext) {
  navigator.serviceWorker.register("/sw.js").catch(() => {
    /* The app keeps working without offline support. */
  });
}
export default Application;
