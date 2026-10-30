// Ostre nagranie planera stołów do reklamy (konto demo, środowisko E2E, fikcyjne dane).
// Zamiast recordVideo używa CDP screencast przy deviceScaleFactor 2.77 (klatki 1080x1921), więc tekst jest ostry.
// Uruchom z frontend/: node scripts/nagraj-stol7v3.mjs   Wynik: D:/film-studio/recordings_stol7/v3/ (klatki + frames.txt)
import { chromium } from "@playwright/test";
import fs from "node:fs";

const BASE = "http://localhost:5174";
const OUT = "D:/film-studio/recordings_stol7/v3";
const EMAIL = "demo@example.com", PASS = process.env.WP_SEED_PASSWORD ?? "Demo-Wesele-2027!";
fs.rmSync(OUT, { recursive: true, force: true }); fs.mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await chromium.launch();
const common = { viewport: { width: 390, height: 694 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "pl-PL", timezoneId: "Europe/Warsaw", colorScheme: "light" };

let id = null;
async function freshState() {
  const lc = await browser.newContext(common); const lp = await lc.newPage();
  await lp.goto(BASE + "/logowanie");
  await lp.getByLabel("E-mail").fill(EMAIL); await lp.getByLabel("Hasło", { exact: true }).fill(PASS);
  await lp.getByRole("button", { name: "Zaloguj się" }).click();
  await lp.waitForURL((u) => !u.pathname.startsWith("/logowanie"));
  await lp.goto(BASE + "/"); await lp.waitForTimeout(2000);
  const m = lp.url().match(/\/w\/([^/?#]+)/);
  id = m ? m[1] : (await lp.locator('a[href^="/w/"]').first().getAttribute("href")).split("/")[2];
  const st = await lc.storageState(); await lc.close(); return st;
}
const CURSOR = `(() => {
  const d = document.createElement('div');
  d.style.cssText = 'position:fixed;z-index:2147483647;width:34px;height:34px;border-radius:50%;background:rgba(122,62,58,.35);border:3px solid rgba(122,62,58,.9);pointer-events:none;left:-60px;top:-60px;transform:translate(-50%,-50%)';
  document.addEventListener('DOMContentLoaded', () => document.body.appendChild(d));
  addEventListener('mousemove', (e) => { d.style.left = e.clientX + 'px'; d.style.top = e.clientY + 'px'; });
})();`;
async function move(page, x, y) { await page.mouse.move(x, y, { steps: 14 }); }
async function tap(page, loc) {
  await loc.scrollIntoViewIfNeeded(); const b = await loc.boundingBox();
  await move(page, b.x + b.width / 2, b.y + b.height / 2); await sleep(250);
  await page.mouse.down(); await sleep(90); await page.mouse.up(); await sleep(900);
}
const go = async (page, path) => { await page.goto(`${BASE}/w/${id}${path}`); await page.waitForLoadState("networkidle").catch(() => {}); await sleep(1200); };

const st = await freshState();
const ctx = await browser.newContext({ ...common, storageState: st });
await ctx.addInitScript(CURSOR);
const page = await ctx.newPage();
const frames = []; let n = 0, rec = false;
(async () => {
  while (true) {
    if (!rec) { if (rec === null) break; await sleep(20); continue; }
    const t = Date.now() / 1000;
    const buf = await page.screenshot({ type: "jpeg", quality: 92 }).catch(() => null);
    if (!buf) continue;
    const name = `f${String(n++).padStart(5, "0")}.jpg`; fs.writeFileSync(`${OUT}/${name}`, buf); frames.push({ name, t });
  }
})();
const moved = [];
await go(page, "/stoly");
rec = true;
const T0 = Date.now();
await sleep(1800);
const marks = { start: 0 };
for (const k of [7, 8]) {
  const chip = page.locator(".person-chip").first();
  moved.push((await chip.innerText()).trim().split(String.fromCharCode(10))[0]);
  marks["dialog" + k] = (Date.now() - T0) / 1000;
  await tap(page, chip); await sleep(500);
  await tap(page, page.locator("[role=dialog]").getByRole("button", { name: new RegExp("Stół " + k) }));
  marks["tap" + k] = (Date.now() - T0) / 1000;
  await sleep(1100);
  await page.locator('.seating-table[aria-label="Stół ' + k + '"]').scrollIntoViewIfNeeded();
  await sleep(k === 7 ? 1600 : 2200);
}
rec = null; await sleep(600);
// plik czasów dla concat demuxera
let txt = "";
for (let i = 0; i < frames.length; i++) {
  const d = i + 1 < frames.length ? Math.max(0.001, frames[i + 1].t - frames[i].t) : 0.5;
  txt += `file '${frames[i].name}'\nduration ${d.toFixed(4)}\n`;
}
txt += `file '${frames[frames.length - 1].name}'\n`;
fs.writeFileSync(`${OUT}/frames.txt`, txt);
fs.writeFileSync(`${OUT}/marks.json`, JSON.stringify({ marks, moved, t0: frames[0].t }));
await ctx.close();
console.log("NAGRANO", frames.length, "klatek", JSON.stringify(marks), JSON.stringify(moved));

// przywrócenie danych demo
const st2 = await freshState();
const c2 = await browser.newContext({ ...common, deviceScaleFactor: 1, storageState: st2 });
const p2 = await c2.newPage();
await p2.goto(`${BASE}/w/${id}/stoly`); await p2.waitForLoadState("networkidle").catch(() => {});
for (const name of moved) {
  const chip = p2.locator(".seating-table .person-chip", { hasText: name }).first();
  if (await chip.count()) { await chip.click(); await sleep(600); await p2.locator("[role=dialog]").getByRole("button", { name: /Bez miejsca/ }).first().click().catch(() => {}); await sleep(900); }
}
console.log("PO:", await p2.locator("text=/Posadzeni.*/").first().innerText().catch(() => "?"));
await c2.close(); await browser.close();
