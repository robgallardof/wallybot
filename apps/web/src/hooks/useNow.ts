import { useEffect, useState } from "react";

/** Ticks every 30 s so countdowns and expiry states stay current without a refetch. Reading the
 * clock through state keeps renders pure (react-hooks/purity forbids Date.now() during render). */
export function useNow(intervalMs = 30000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs]);
  return now;
}
