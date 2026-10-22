import { expect, test } from "@playwright/test";

// Service worker rejestruje się tylko w buildzie produkcyjnym (E2E_PROD=1 albo E2E_BASE_URL).
const prod = process.env.E2E_PROD === "1" || !!process.env.E2E_BASE_URL;
test.skip(!prod, "PWA tylko w buildzie produkcyjnym");

test("PWA: manifest, ikony, service worker, powłoka bez sieci, API poza pamięcią", async ({ page, context }) => {
  test.skip(!["320-light", "1280-dark"].includes(test.info().project.name), "Jeden telefon, jeden komputer");
  await page.goto("/logowanie");
  const manifestHref = await page.locator('link[rel="manifest"]').getAttribute("href");
  const manifest = await (await page.request.get(manifestHref!)).json();
  expect(manifest.short_name).toBe("Nasz dzień");
  expect(manifest.lang).toBe("pl");
  for (const icon of manifest.icons as { src: string; type: string }[]) {
    const r = await page.request.get(icon.src);
    expect(r.ok(), icon.src).toBeTruthy();
    expect(r.headers()["content-type"]).toContain("image/png");
  }
  expect((await page.request.get("/icons/apple-touch-icon.png")).ok()).toBeTruthy();

  await page.evaluate(() => navigator.serviceWorker.ready.then(() => undefined));
  // Kontrola przejęta dopiero po przeładowaniu.
  await page.reload();
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);

  await context.setOffline(true);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Zaloguj się" })).toBeVisible();
  await context.setOffline(false);

  const cached = await page.evaluate(async () => {
    const urls: string[] = [];
    for (const name of await caches.keys()) {
      for (const req of await (await caches.open(name)).keys()) urls.push(new URL(req.url).pathname);
    }
    return urls;
  });
  expect(cached).toContain("/");
  expect(cached.some((u) => u.startsWith("/assets/"))).toBe(true);
  expect(cached.filter((u) => u.startsWith("/api/"))).toEqual([]);
});

test("start bez sieci zalogowanej osoby: ekran „Brak połączenia”, po powrocie sieci — aplikacja", async ({ page, context }) => {
  test.skip(!["320-light", "1280-dark"].includes(test.info().project.name), "Jeden telefon, jeden komputer");
  await page.goto("/logowanie");
  await page.getByLabel("E-mail").fill("demo@example.com");
  await page.getByLabel("Hasło", { exact: true }).fill(process.env.WP_SEED_PASSWORD ?? "Demo-Wesele-2027!");
  await page.getByRole("button", { name: "Zaloguj się" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/logowanie"));
  await page.evaluate(() => navigator.serviceWorker.ready.then(() => undefined));
  await page.reload();
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);

  await context.setOffline(true);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Brak połączenia" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Spróbuj ponownie" })).toBeVisible();
  // Powrót sieci: aplikacja sama ponawia przywrócenie sesji (zdarzenie „online”).
  await context.setOffline(false);
  await expect(page.getByRole("heading", { name: "Brak połączenia" })).toHaveCount(0, { timeout: 10_000 });
  await expect(page).not.toHaveURL(/logowanie/);
});

test("bez sieci po przeładowaniu: zapisany program dnia (para i usługodawca), API nadal poza pamięcią", async ({ page, context, request }) => {
  test.skip(!["320-light", "1280-dark"].includes(test.info().project.name), "Jeden telefon, jeden komputer");
  const password = process.env.WP_SEED_PASSWORD ?? "Demo-Wesele-2027!";
  const login = await request.post("/api/v1/auth/login", { data: { email: "demo@example.com", password } });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", {
      headers: auth,
      data: { name: `Offline PWA ${Math.random().toString(36).slice(2, 7)}`, wedding_date: "2028-06-17", ceremony_type: "civil" },
    })
  ).json();
  try {
    await request.post(`/api/v1/weddings/${w.id}/schedule/from-template`, {
      headers: auth,
      data: { day: "2028-06-17", ceremony_time: "15:00", dry_run: false },
    });
    const dj = await (await request.post(`/api/v1/weddings/${w.id}/vendors`, { headers: auth, data: { name: "DJ Offline", category: "dj" } })).json();
    const dayToken = (await (await request.post(`/api/v1/weddings/${w.id}/vendors/${dj.id}/day-link`, { headers: auth })).json()).token as string;

    await page.goto("/logowanie");
    await page.getByLabel("E-mail").fill("demo@example.com");
    await page.getByLabel("Hasło", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Zaloguj się" }).click();
    await page.waitForURL((u) => !u.pathname.startsWith("/logowanie"));
    await page.goto(`/w/${w.id}/dzien`);
    await page.getByRole("button", { name: /Tryb dnia ślubu/ }).click();
    await page.getByRole("button", { name: "Zapisz program na tym telefonie (na wypadek braku zasięgu)" }).click();
    await expect(page.getByText(/^Kopia programu z godz\./)).toBeVisible();
    await page.evaluate(() => navigator.serviceWorker.ready.then(() => undefined));
    await page.reload();
    await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);

    // Para: start bez sieci → „Brak połączenia” z zapisanym programem.
    await context.setOffline(true);
    await page.reload();
    await expect(page.getByRole("heading", { name: "Brak połączenia" })).toBeVisible();
    await expect(page.getByRole("heading", { name: w.name })).toBeVisible();
    await expect(page.getByText(/Bez połączenia — program z godz\./)).toBeVisible();
    await expect(page.getByText("Krojenie tortu").first()).toBeVisible();
    await context.setOffline(false);

    // Usługodawca: kopia po pierwszym otwarciu, pokazywana bez sieci.
    await page.goto(`/dzien/${dayToken}`);
    await expect(page.getByRole("heading", { name: w.name, level: 1 })).toBeVisible();
    await context.setOffline(true);
    await page.reload();
    await expect(page.getByText(/Bez połączenia — program z godz\./)).toBeVisible();
    await expect(page.getByText("Krojenie tortu").first()).toBeVisible();
    await context.setOffline(false);

    const cached = await page.evaluate(async () => {
      const urls: string[] = [];
      for (const name of await caches.keys()) {
        for (const req of await (await caches.open(name)).keys()) urls.push(new URL(req.url).pathname);
      }
      return urls;
    });
    expect(cached.filter((u) => u.startsWith("/api/"))).toEqual([]);
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});
