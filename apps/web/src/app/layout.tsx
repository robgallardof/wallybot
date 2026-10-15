import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import { ThemeProvider } from "next-themes";
import "../style.css";
import "../theme.css";
import "../workspace.css";
import "../polish.css";

export const metadata: Metadata = {
  title: "WallyBot",
  description: "Private portfolio and research workspace",
  robots: { index: false, follow: false },
  applicationName: "WallyBot",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "WallyBot", statusBarStyle: "black-translucent" },
  icons: {
    icon: [{ url: "/icons/icon.svg", type: "image/svg+xml" }, { url: "/icons/icon-192.png", sizes: "192x192" }],
    apple: "/icons/apple-touch-icon.png",
  },
};
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f5f7" },
    { media: "(prefers-color-scheme: dark)", color: "#111113" },
  ],
};
// Per-request rendering is required for the CSP nonce.
export const dynamic = "force-dynamic";

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // next-themes injects its anti-flash script via dangerouslySetInnerHTML, which
  // Next.js's automatic CSP nonce propagation does not cover — it needs the nonce explicitly.
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  return (
    <html lang="es" suppressHydrationWarning>
      <body>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          enableColorScheme={false}
          nonce={nonce}
        >
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
