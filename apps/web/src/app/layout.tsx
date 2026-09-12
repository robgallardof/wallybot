import type { Metadata } from "next";
import { headers } from "next/headers";
import { ThemeProvider } from "next-themes";
import "../style.css";

export const metadata: Metadata = {
  title: "WallyBot",
  description: "Private portfolio and research workspace",
  robots: { index: false, follow: false },
};
// Per-request rendering is required for the CSP nonce.
export const dynamic = "force-dynamic";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // next-themes injects its anti-flash script via dangerouslySetInnerHTML, which
  // Next.js's automatic CSP nonce propagation does not cover — it needs the nonce explicitly.
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  return (
    <html lang="es" suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem nonce={nonce}>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
