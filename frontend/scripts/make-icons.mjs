// Ikony PWA (PNG) z logo SVG — renderowane przeglądarką Playwright (bez dodatkowych zależności).
// Użycie: node scripts/make-icons.mjs   (wynik w public/icons/, commitowany do repozytorium)
import { readFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const BRAND = "#63364A";
const RINGS = "#F1E8EB";

// Pierścienie bez zaokrąglonego tła: tło dokłada strona (pełne dla „maskable” i Apple).
const rings = (scale) => `
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="100%" height="100%">
    <g transform="translate(16 16) scale(${scale}) translate(-16 -16)" fill="none" stroke="${RINGS}" stroke-width="2.2">
      <circle cx="13" cy="16" r="6"/><circle cx="19" cy="16" r="6"/>
    </g>
  </svg>`;

const variants = [
  // Zwykła ikona: zaokrąglony kwadrat z favicon.svg.
  { file: "icon-192.png", size: 192, html: readFileSync("public/favicon.svg", "utf8"), bg: "transparent" },
  { file: "icon-512.png", size: 512, html: readFileSync("public/favicon.svg", "utf8"), bg: "transparent" },
  // Maskable: pełne tło, znak w bezpiecznym kole (80%).
  { file: "icon-maskable-512.png", size: 512, html: rings(0.8), bg: BRAND },
  // Apple: pełne tło (iOS sam zaokrągla rogi).
  { file: "apple-touch-icon.png", size: 180, html: rings(0.95), bg: BRAND },
];

const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: 1 });
for (const v of variants) {
  await page.setViewportSize({ width: v.size, height: v.size });
  await page.setContent(
    `<html><body style="margin:0;background:${v.bg}"><div style="width:${v.size}px;height:${v.size}px">${v.html}</div></body></html>`,
  );
  await page.locator("svg").first().evaluate((el) => {
    el.setAttribute("width", "100%");
    el.setAttribute("height", "100%");
  });
  await page.screenshot({ path: `public/icons/${v.file}`, omitBackground: v.bg === "transparent" });
  console.log(`public/icons/${v.file}`);
}
await browser.close();
