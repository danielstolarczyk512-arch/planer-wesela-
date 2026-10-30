// Nagrania ekranu aplikacji do filmu reklamowego (konto demo, fikcyjne dane, środowisko E2E).
// Uruchom z frontend/: node scripts/nagraj-ekran-film.mjs  (Vite na 5174, API E2E na 8011)
// Wynik: D:/film-studio/recordings_stol7/<przepływ>.webm — płynne kliknięcia, wskaźnik dotyku i realne działania w aplikacji.
import { chromium } from "@playwright/test";
import fs from "node:fs";

const BASE = "http://localhost:5174";
const OUT = "D:/film-studio/recordings_stol7";
const EMAIL = "demo@example.com", PASS = process.env.WP_SEED_PASSWORD ?? "Demo-Wesele-2027!";
fs.mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await chromium.launch();

const common = { viewport: { width: 390, height: 694 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "pl-PL", timezoneId: "Europe/Warsaw", colorScheme: "light" };

// logowanie bez nagrywania — osobna sesja dla każdego przepływu
let id = null;
async function freshState() {
  const lc = await browser.newContext(common);
  const lp = await lc.newPage();
  await lp.goto(BASE + "/logowanie");
  await lp.getByLabel("E-mail").fill(EMAIL);
  await lp.getByLabel("Hasło", { exact: true }).fill(PASS);
  await lp.getByRole("button", { name: "Zaloguj się" }).click();
  await lp.waitForURL((u) => !u.pathname.startsWith("/logowanie"));
  if (lp.url().includes("/powitanie")) await lp.goto(BASE + "/");
  await lp.waitForTimeout(1500);
  const m = lp.url().match(/\/w\/([^/?#]+)/);
  id = m ? m[1] : (await lp.locator('a[href^="/w/"]').first().getAttribute("href")).split("/")[2];
  const st = await lc.storageState();
  await lc.close();
  return st;
}

const CURSOR = `(() => {
  const d = document.createElement('div');
  d.style.cssText = 'position:fixed;z-index:2147483647;width:34px;height:34px;border-radius:50%;background:rgba(122,62,58,.35);border:3px solid rgba(122,62,58,.9);pointer-events:none;left:-60px;top:-60px;transition:transform .12s;transform:translate(-50%,-50%)';
  document.addEventListener('DOMContentLoaded', () => document.body.appendChild(d));
  addEventListener('mousemove', (e) => { d.style.left = e.clientX + 'px'; d.style.top = e.clientY + 'px'; });
  addEventListener('mousedown', () => { d.style.transform = 'translate(-50%,-50%) scale(.7)'; });
  addEventListener('mouseup', () => { d.style.transform = 'translate(-50%,-50%) scale(1)'; });
})();`;

async function flow(name, fn) {
  const st = await freshState();
  const ctx = await browser.newContext({ ...common, storageState: st, recordVideo: { dir: `${OUT}/_${name}`, size: { width: 780, height: 1388 } } });
  await ctx.addInitScript(CURSOR);
  const page = await ctx.newPage();
  let ok = true;
  try { await fn(page); } catch (e) { ok = false; console.log("BŁĄD", name, String(e).slice(0, 200)); await page.screenshot({ path: `${OUT}/_err_${name}.png` }); }
  await page.waitForTimeout(600);
  const v = page.video();
  await ctx.close();
  const p = await v.path();
  fs.copyFileSync(p, `${OUT}/${name}.webm`);
  console.log(ok ? "OK" : "CZĘŚCIOWO", name);
}

async function move(page, x, y) { await page.mouse.move(x, y, { steps: 14 }); }
async function tap(page, loc) {
  await loc.scrollIntoViewIfNeeded();
  const b = await loc.boundingBox();
  await move(page, b.x + b.width / 2, b.y + b.height / 2);
  await sleep(250);
  await page.mouse.down(); await sleep(90); await page.mouse.up();
  await sleep(900);
}
async function scroll(page, dy, ms = 1500) {
  const steps = 15;
  for (let i = 0; i < steps; i++) { await page.mouse.wheel(0, dy / steps); await sleep(ms / steps); }
}
const go = async (page, path) => { await page.goto(`${BASE}/w/${id}${path}`); await page.waitForLoadState("networkidle").catch(() => {}); await sleep(1200); };

const moved = [];
await flow("stol7v2", async (page) => {
  await go(page, "/stoly");
  await sleep(1800);                                   // problem: goście bez stołu
  for (const n of [7, 8]) {
    const chip = page.locator(".person-chip").first();
    moved.push((await chip.innerText()).trim());
    await tap(page, chip);
    await sleep(500);
    await tap(page, page.locator("[role=dialog]").getByRole("button", { name: new RegExp("Stół " + n) }));
    await sleep(1100);
    const card = page.locator('.seating-table[aria-label="Stół ' + n + '"]');
    await card.scrollIntoViewIfNeeded();
    await sleep(n === 7 ? 1600 : 2000);
  }
});
console.log("PRZENIESIENI:", JSON.stringify(moved));
// przywrócenie danych demo: ci sami goście z powrotem bez stołu
const st2 = await freshState();
const c2 = await browser.newContext({ ...common, storageState: st2 });
const p2 = await c2.newPage();
await p2.goto(`${BASE}/w/${id}/stoly`); await p2.waitForLoadState("networkidle").catch(() => {});
for (const name of moved) {
  const chip = p2.locator('.seating-table .person-chip', { hasText: name.split(String.fromCharCode(10))[0] }).first();
  if (await chip.count()) { await chip.click(); await sleep(600); await p2.locator("[role=dialog]").getByRole("button", { name: /Bez miejsca|Bez stołu|Zdejmij|Odepnij/ }).first().click().catch(() => {}); await sleep(900); }
}
await c2.close();
await browser.close();
console.log("GOTOWE");
