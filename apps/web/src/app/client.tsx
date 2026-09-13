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
export default Application;
