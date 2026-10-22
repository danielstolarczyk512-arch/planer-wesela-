import { defineConfig, devices } from "@playwright/test";

/**
 * E2E na prawdziwym API w osobnym środowisku: `docker compose --profile e2e up -d`. Szerokości z GUI-SPEC:
 * 320, 390, 768, 1280 px; motyw jasny i ciemny przez prefers-color-scheme.
 */
const widths = [
  { name: "320", width: 320, height: 640 },
  { name: "390", width: 390, height: 844 },
  { name: "768", width: 768, height: 1024 },
  { name: "1280", width: 1280, height: 800 },
];

// E2E_PROD=1: build produkcyjny (vite preview) z nagłówkiem CSP jak w Caddy.
// E2E_BASE_URL: gotowe środowisko (np. staging za Caddy, https://localhost:9443) bez serwera Vite.
const prod = process.env.E2E_PROD === "1" || !!process.env.E2E_BASE_URL;
const external = process.env.E2E_BASE_URL;
// Osobne środowisko E2E (docker compose --profile e2e): API 8011 z bazą wedding_e2e i własne porty
// serwera WWW — testy nie dotykają bazy dev ani serwera Vite używanego na co dzień.
const e2eApi = process.env.E2E_API_URL ?? "http://127.0.0.1:8011";
const baseURL = external ?? (prod ? "http://localhost:4174" : "http://localhost:5174");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 2,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL,
    // Lokalny staging ma certyfikat wewnętrzny Caddy (localhost).
    ignoreHTTPSErrors: !!external,
    locale: "pl-PL",
    timezoneId: "Europe/Warsaw",
    trace: "retain-on-failure",
  },
  projects: widths.flatMap((w) =>
    (["light", "dark"] as const).map((scheme) => ({
      name: `${w.name}-${scheme}`,
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: w.width, height: w.height },
        colorScheme: scheme,
        hasTouch: w.width < 768,
      },
    })),
  ),
  webServer: external
    ? undefined
    : {
        command: prod ? "npm run build && npm run preview" : "npm run dev",
        env: { WP_API_URL: e2eApi, WP_WEB_PORT: "5174", WP_PREVIEW_PORT: "4174" },
        url: baseURL,
        reuseExistingServer: true,
        timeout: 180_000,
      },
});
