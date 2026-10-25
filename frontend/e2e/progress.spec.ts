import { expect, test, type Page, type Route } from "@playwright/test";

// Pasek „Wasze postępy”: stan zadań podmieniamy w odpowiedzi API (dane demo nie są zmieniane).
const DEMO = { email: "demo@example.com", password: process.env.WP_SEED_PASSWORD ?? "Demo-Wesele-2027!" };

test.skip(!!process.env.E2E_BASE_URL, "Dane demo istnieją tylko w środowisku deweloperskim");

type T = { id: string; status: string; parent_task_id?: string | null };

const TASKS = /\/api\/v1\/weddings\/[^/]+\/tasks(\?.*)?$/;
const FINALE = "Wszystko dopięte na ostatni guzik! Teraz czas powiedzieć «TAK»! 💗";

/** Pierwsze `done` zadań głównych (bez pominiętych) jako zrobione, reszta do zrobienia. */
function withDone(tasks: T[], done: number): T[] {
  const top = tasks.filter((t) => !t.parent_task_id && t.status !== "skipped").map((t) => t.id);
  const finished = new Set(top.slice(0, done));
  return tasks.map((t) => (top.includes(t.id) ? { ...t, status: finished.has(t.id) ? "done" : "todo" } : t));
}

async function login(page: Page) {
  await page.goto("/logowanie");
  await page.getByLabel("E-mail").fill(DEMO.email);
  await page.getByLabel("Hasło", { exact: true }).fill(DEMO.password);
  await page.getByRole("button", { name: "Zaloguj się" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/logowanie"));
  await page.goto("/?wybierz=1");
  await page.getByRole("link", { name: /Wesele demo/ }).click();
  await expect(page.getByRole("heading", { name: "Wesele demo" })).toBeVisible();
}

/** Zwraca liczbę zadań głównych i sterownik stanu (ile zrobionych). */
async function mockTasks(page: Page) {
  const state = { done: 0, total: 0, failSave: false };
  let last: T[] = [];
  await page.route(TASKS, async (route: Route) => {
    if (route.request().method() !== "GET") return route.fallback();
    const res = await route.fetch();
    const body = (await res.json()) as { items: T[]; next_cursor: string | null };
    const real = body.items;
    state.total = real.filter((t) => !t.parent_task_id && t.status !== "skipped").length;
    last = withDone(real, Math.min(state.done, state.total));
    await route.fulfill({ response: res, json: { ...body, items: last } });
  });
  await page.route(/\/tasks\/[^/]+\/(complete|reopen)$/, async (route: Route) => {
    if (state.failSave) return route.fulfill({ status: 500, contentType: "application/problem+json", json: { title: "Błąd", status: 500 } });
    const done = route.request().url().endsWith("/complete");
    state.done += done ? 1 : -1;
    const id = route.request().url().match(/tasks\/([^/]+)\//)![1];
    const task = last.find((t) => t.id === id)!;
    await route.fulfill({ json: { ...task, status: done ? "done" : "todo" } });
  });
  return state;
}

async function openPlan(page: Page) {
  await page.getByRole("navigation", { name: "Główne" }).getByRole("link", { name: "Plan" }).click();
  await expect(page).toHaveURL(/\/plan$/);
  await expect(page.getByRole("progressbar", { name: "Postęp przygotowań" })).toBeVisible();
}

/** Jedyne niezrobione zadanie: w „Teraz” albo „Później”. */
async function openTask(page: Page) {
  const box = page.getByRole("checkbox", { checked: false });
  await expect(bar(page)).toBeVisible();
  if ((await box.count()) === 0) await page.getByText("Później", { exact: true }).click();
  await expect(box.first()).toBeVisible();
  return box.first();
}

const bar = (page: Page) => page.getByRole("progressbar", { name: "Postęp przygotowań" });
const ring = (page: Page) => page.locator('.wpb__icon img[src*="pierscionek"]');
const couple = (page: Page) => page.locator(".wpb__couple--on img");

async function expectNoOverflow(page: Page) {
  const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(over).toBeLessThanOrEqual(0);
  // Ikona (pierścionek lub para) mieści się w oknie na obu końcach toru.
  const vw = page.viewportSize()!.width;
  for (const img of await page.locator(".wpb__icon img, .wpb__couple img").all()) {
    const box = (await img.boundingBox())!;
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(vw);
  }
  // Procent nie wychodzi poza ekran.
  const pct = (await page.locator(".wpb__percent").boundingBox())!;
  expect(pct.x).toBeGreaterThanOrEqual(0);
  expect(pct.x + pct.width).toBeLessThanOrEqual(vw);
}

async function shot(page: Page, name: string) {
  if (process.env.SHOTS_DIR) {
    const w = page.viewportSize()!.width;
    await page.locator(".meter").screenshot({ path: `${process.env.SHOTS_DIR}/${name}-${w}.png` });
  }
}

test("Pasek postępu: 0%, 10%, 50%, 99% i 100% z realnych danych; bez przepełnienia", async ({ page }) => {
  const errors: string[] = [];
  await login(page);
  // Błędy konsoli liczymy po zalogowaniu (przed nim 401 na /me jest normalne).
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  const state = await mockTasks(page);
  await openPlan(page);
  const total = state.total;
  expect(total).toBeGreaterThan(2);

  const cases = [0, Math.round(total * 0.1), Math.round(total / 2), total - 1, total];
  for (const done of cases) {
    state.done = done;
    await page.reload();
    await expect(bar(page)).toBeVisible();
    const share = (done / total) * 100;
    const label = done === total ? 100 : Math.min(99, Math.round(share));
    await expect(bar(page)).toHaveAttribute("aria-valuenow", String(label));
    await expect(page.getByText(`${label}%`, { exact: true })).toBeVisible();
    await expect(page.locator(".meter .num").first()).toContainText(`${done} z ${total}`);
    if (done === total) {
      await expect(couple(page)).toBeVisible();
      await expect(page.getByText(FINALE)).toBeVisible();
      // Ponowne otwarcie ukończonej listy: statyczny stan, bez konfetti.
      await expect(page.locator(".wpb__burst")).toHaveCount(0);
    } else {
      await expect(ring(page)).toBeVisible();
      await expect(page.getByText(FINALE)).toHaveCount(0);
    }
    await page.waitForTimeout(900); // koniec przejścia paska
    await expectNoOverflow(page);
    if ([0, cases[1], cases[2], total].includes(done)) await shot(page, `${Math.round(share)}pct`);
  }
  expect(errors).toEqual([]);
});

test("Pasek postępu: finał tylko po zapisie, cofnięcie, nieudany zapis", async ({ page }) => {
  await login(page);
  const state = await mockTasks(page);
  await openPlan(page);
  state.done = state.total - 1;
  await page.reload();
  await expect(ring(page)).toBeVisible();
  // Nieudany zapis ostatniego zadania: brak finału i brak konfetti, pasek wraca.
  state.failSave = true;
  const first = await openTask(page);
  await first.check({ force: true });
  await page.waitForTimeout(600);
  await expect(page.getByText(FINALE)).toHaveCount(0);
  await expect(page.locator(".wpb__burst")).toHaveCount(0);
  await expect(ring(page)).toBeVisible();
  await expect(bar(page)).toHaveAttribute("aria-valuenow", String(Math.min(99, Math.round(((state.total - 1) / state.total) * 100))));

  // Udany zapis: para, komunikat i jednorazowe konfetti.
  state.failSave = false;
  await first.check({ force: true });
  await expect(couple(page)).toBeVisible();
  await expect(page.getByText(FINALE)).toBeVisible();
  await expect(page.locator(".wpb__burst")).toHaveCount(1);
  await shot(page, "finale-konfetti");
  await expect(page.locator(".wpb__burst")).toHaveCount(0, { timeout: 5000 });
});

test("Pasek postępu: ograniczenie ruchu pomija konfetti", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await login(page);
  const state = await mockTasks(page);
  await openPlan(page);
  state.done = state.total - 1;
  await page.reload();
  await (await openTask(page)).check({ force: true });
  await expect(couple(page)).toBeVisible();
  await expect(page.getByText(FINALE)).toBeVisible();
  await expect(page.locator(".wpb__burst")).toHaveCount(0);
});
