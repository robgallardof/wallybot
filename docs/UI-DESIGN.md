# UI: neutral surfaces and accessible interaction

Updated 2026-09-12 at the user's request. Claude owns backend/connectivity work; this change is scoped to frontend presentation and interaction.

The interface uses neutral white/gray surfaces in light mode and graphite surfaces in dark mode. Blue indicates interaction; green/amber/red retain status meanings alongside text. A system font, larger operational labels, tabular numbers, visible keyboard focus, a skip link, selected navigation semantics and 44px controls support readability and navigation. The QR retains black/white contrast.

Design references: Apple's [Color](https://developer.apple.com/design/human-interface-guidelines/color), [Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode), [Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility) and [Typography](https://developer.apple.com/design/human-interface-guidelines/typography). This is a web interpretation of those principles, not an Apple component implementation or a claim of full accessibility certification.

Color tokens live in `apps/web/src/theme.css`; future screens should consume the same surface/text/action/status variables. Light action blue #0066cc against white has a calculated contrast ratio of 5.57:1. Keep status labels and icons when using color. Respect reduced-motion and increased-contrast preferences.

Verification: frontend lint and Next production build passed; 2 production browser tests passed covering registration, QR/manual enrollment, locale, theme persistence, dashboard interactions and CSP. Desktop light/dark and mobile light screenshots were visually inspected. Remaining work includes a complete assistive-technology audit, validation of future data tables, and reducing legacy declarations in style.css as components evolve.
