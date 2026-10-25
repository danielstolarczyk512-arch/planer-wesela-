import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Wymaga danych demo: `python -m scripts.seed` oraz `python -m scripts.seed --content` (fikcyjne).
const DEMO = { email: "demo@example.com", password: process.env.WP_SEED_PASSWORD ?? "Demo-Wesele-2027!" };

test.skip(!!process.env.E2E_BASE_URL, "Dane demo istnieją tylko w środowisku deweloperskim");

async function expectAccessible(page: Page) {
  // Kontrast mierzymy po zakończeniu animacji wejścia (okno w trakcie pojawiania się jest półprzezroczyste).
  // Animacja wejścia startuje klatkę po pojawieniu się elementu: najpierw dwie klatki, potem czekamy na jej koniec.
  await page.evaluate(
    () =>
      new Promise<void>((done) => requestAnimationFrame(() => requestAnimationFrame(() => done()))).then(() =>
        Promise.all(document.getAnimations().map((a) => a.finished.catch(() => undefined))),
      ),
  );
  const result = await new AxeBuilder({ page })
    // Ukryty „spiker” React Aria (role=log) przez kilka sekund trzyma komunikat wskazujący na
    // zamknięty już formularz — to stan biblioteki, nie treść aplikacji (sprawdzone ręcznie).
    .exclude('[role="log"][aria-live="assertive"] > [role="img"]')
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(
    result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => `${n.target} ${n.html.slice(0, 160)} ${n.failureSummary ?? ""}`).join(" | ")}`),
  ).toEqual([]);
}

async function expectNoHorizontalScroll(page: Page) {
  // Przy błędzie podajemy elementy wystające poza ekran — bez tego trudno znaleźć przyczynę.
  const report = await page.evaluate(() => {
    const overflow = document.documentElement.scrollWidth - window.innerWidth;
    const culprits =
      overflow > 0
        ? Array.from(document.querySelectorAll("body *"))
            .filter((el) => el.getBoundingClientRect().right > window.innerWidth + 1)
            .slice(0, 5)
            .map((el) => `${el.tagName.toLowerCase()}.${Array.from(el.classList).join(".")} → ${Math.round(el.getBoundingClientRect().right)}px`)
        : [];
    return { overflow, culprits };
  });
  expect(report.overflow, report.culprits.join("; ")).toBeLessThanOrEqual(0);
}

async function openDemoWedding(page: Page) {
  await page.goto("/logowanie");
  await page.getByLabel("E-mail").fill(DEMO.email);
  await page.getByLabel("Hasło", { exact: true }).fill(DEMO.password);
  await page.getByRole("button", { name: "Zaloguj się" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/logowanie"));
  await page.goto("/?wybierz=1");
  await page.getByRole("link", { name: /Wesele demo/ }).click();
  await expect(page.getByRole("heading", { name: "Wesele demo" })).toBeVisible();
}

const tab = (page: Page, name: string) => page.getByRole("navigation", { name: "Główne" }).getByRole("link", { name });

test("Dziś: odliczanie, najbliższe kroki, płatność; dostępność", async ({ page }) => {
  await openDemoWedding(page);
  await expect(page.getByRole("region", { name: "Odliczanie do ślubu" })).toContainText("miesięcy do ślubu");
  await expect(page.getByRole("heading", { name: "Najbliższe kroki" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Najbliższa płatność.*DJ/ })).toBeVisible();
  await expect(tab(page, "Dziś")).toHaveAttribute("aria-current", "page");
  await expectAccessible(page);
  await expectNoHorizontalScroll(page);
});

test("zakładki: własne adresy, aktywna zakładka, przycisk Wstecz", async ({ page }) => {
  await openDemoWedding(page);
  await tab(page, "Plan").click();
  await expect(page).toHaveURL(/\/plan$/);
  await expect(tab(page, "Plan")).toHaveAttribute("aria-current", "page");
  await tab(page, "Goście").click();
  await expect(page.getByRole("heading", { name: "Goście", level: 1 })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("heading", { name: "Plan przygotowań" })).toBeVisible();
  // Link bezpośredni do zakładki działa po przeładowaniu.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Plan przygotowań" })).toBeVisible();
});

test("Plan: odhaczenie zadania i „Cofnij”; filtr w adresie", async ({ page }) => {
  await openDemoWedding(page);
  await tab(page, "Plan").click();
  const first = page.getByRole("checkbox").first();
  const name = (await first.getAttribute("aria-label"))!.split(":")[0]!;
  // Dotknięcie pola (jak palcem); input checkboxa jest wizualnie ukryty.
  await page.locator(".row .wp-checkbox").first().click();
  await expect(page.getByText(`„${name}” — zrobione`)).toBeVisible();
  // Zadanie nie znika spod palca: dalej widoczne, oznaczone.
  await expect(page.getByRole("checkbox", { name: `${name}: zrobione` })).toBeChecked();
  await page.getByRole("button", { name: "Cofnij" }).click();
  await expect(page.getByRole("checkbox", { name: `${name}: do zrobienia` })).not.toBeChecked();
  await page.locator(".wp-segmented__option", { hasText: "Później" }).click();
  await expect(page).toHaveURL(/widok=pozniej/);
  await expectAccessible(page);
  await expectNoHorizontalScroll(page);
});

test("Budżet: podsumowanie, płatności, walidacja nowego wydatku", async ({ page }) => {
  await openDemoWedding(page);
  await tab(page, "Budżet").click();
  await expect(page.getByRole("meter", { name: "Wykorzystanie limitu budżetu" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Płatności w najbliższych 30 dniach" })).toBeVisible();
  await expectAccessible(page);
  await page.getByRole("button", { name: "Dodaj wydatek" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Dodaj wydatek" }).click();
  await expect(page.getByText("Wpisz nazwę, np. Fotograf.")).toBeVisible();
  await expect(page.getByText("Wpisz szacunkową kwotę, np. 5000.")).toBeVisible();
  await expectAccessible(page);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expectNoHorizontalScroll(page);
});

test("Goście: statystyki, wyszukiwanie bez polskich znaków, filtr, rozwinięcie rodziny", async ({ page }) => {
  await openDemoWedding(page);
  await tab(page, "Goście").click();
  await page.getByLabel("Szukaj osoby lub rodziny").fill("zielinska");
  await expect(page.getByRole("button", { name: /^Marta Zielińska/ })).toBeVisible();
  await expect(page.getByText("Państwo Kowalscy")).toHaveCount(0);
  await page.getByLabel("Szukaj osoby lub rodziny").fill("");
  await page.locator(".wp-segmented__option", { hasText: "Odmowy" }).click();
  await expect(page).toHaveURL(/filtr=odmowy/);
  await expect(page.getByText("Wujek Zenek")).toBeVisible();
  await page.locator(".wp-segmented__option", { hasText: "Wszyscy" }).click();
  await page.getByRole("button", { name: /Państwo Kowalscy/ }).click();
  await expect(page.getByRole("button", { name: "Odpowiedz za: Zosia Kowalska" })).toBeVisible();
  await expectAccessible(page);
  await expectNoHorizontalScroll(page);
});

// Testy edycji tworzą własne dane z losowym dopiskiem i sprzątają po sobie (nie ruszają danych demo).
const tag = () => Math.random().toString(36).slice(2, 7);

test("Ustawienia wesela: dane podstawowe, podgląd zmiany daty, osoby z dostępem", async ({ page }) => {
  await openDemoWedding(page);
  await tab(page, "Więcej").click();
  await page.getByRole("link", { name: "Ustawienia wesela" }).click();
  await expect(page.getByRole("heading", { name: "Ustawienia wesela", level: 1 })).toBeVisible();
  await expect(page.getByLabel("Nazwa wesela")).toHaveValue("Wesele demo");
  await expect(page.getByRole("heading", { name: "Osoby z dostępem" })).toBeVisible();
  const exported = page.waitForEvent("download");
  await page.getByRole("button", { name: "Pobierz dane wesela" }).click();
  expect((await exported).suggestedFilename()).toMatch(/^wesele-\d{4}-\d{2}-\d{2}\.json$/);
  await expectAccessible(page);
  await expectNoHorizontalScroll(page);
  // Podgląd przesunięć bez zapisu: „Anuluj” nic nie zmienia.
  await page.getByRole("button", { name: "Pokaż, co się zmieni" }).click();
  const dialog = page.getByRole("alertdialog", { name: "Zmienić datę ślubu?" }).or(page.getByRole("dialog", { name: "Zmienić datę ślubu?" }));
  await expect(dialog).toBeVisible();
  await expectAccessible(page);
  await dialog.getByRole("button", { name: "Anuluj" }).click();
  await expect(dialog).toHaveCount(0);
});

test("Plan: edycja i usunięcie zadania", async ({ page }) => {
  const title = `Test E2E zadanie ${tag()}`;
  await openDemoWedding(page);
  await tab(page, "Plan").click();
  await page.getByRole("button", { name: "Dodaj zadanie" }).click();
  await page.getByRole("dialog").getByLabel("Co trzeba zrobić?").fill(title);
  await page.getByRole("dialog").getByRole("button", { name: "Dodaj zadanie" }).click();
  await page.locator(".wp-segmented__option", { hasText: "Później" }).click();
  await page.getByRole("button", { name: new RegExp(`^${title}`) }).click();
  const sheet = page.getByRole("dialog", { name: "Zadanie" });
  await sheet.getByLabel("Co trzeba zrobić?").fill(`${title} zmienione`);
  await expectAccessible(page);
  await sheet.getByRole("button", { name: "Zapisz" }).click();
  await expect(page.getByText("Zapisano zadanie")).toBeVisible();
  await page.getByRole("button", { name: new RegExp(`^${title} zmienione`) }).click();
  await sheet.getByRole("button", { name: "Usuń zadanie" }).click();
  await page.getByRole("button", { name: "Usuń", exact: true }).click();
  await expect(page.getByText(`Usunięto zadanie „${title} zmienione”`)).toBeVisible();
  await expect(page.getByRole("button", { name: new RegExp(`^${title}`) })).toHaveCount(0);
});

test("Budżet: edycja kwoty i usunięcie wydatku", async ({ page }) => {
  const name = `Test E2E wydatek ${tag()}`;
  await openDemoWedding(page);
  await tab(page, "Budżet").click();
  await page.getByRole("button", { name: "Dodaj wydatek" }).click();
  const add = page.getByRole("dialog");
  await add.getByLabel("Nazwa").fill(name);
  await add.getByRole("button", { name: /Kategoria/ }).click();
  await page.getByRole("option").first().click();
  await add.getByLabel("Kwota (szacunek)").fill("1200");
  await add.getByRole("button", { name: "Dodaj wydatek" }).click();
  await page.getByRole("button", { name: new RegExp(`^${name}`) }).click();
  const sheet = page.getByRole("dialog", { name: "Wydatek" });
  await sheet.getByLabel("Kwota (szacunek)").fill("1500");
  await expectAccessible(page);
  await sheet.getByRole("button", { name: "Zapisz" }).click();
  await expect(page.getByText("Zapisano wydatek")).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: name })).toContainText(/1\s500\szł/);
  await page.getByRole("button", { name: new RegExp(`^${name}`) }).click();
  await sheet.getByRole("button", { name: "Usuń wydatek" }).click();
  await expect(page.getByText("razem z zapisanymi płatnościami")).toBeVisible();
  await page.getByRole("button", { name: "Usuń", exact: true }).click();
  await expect(page.getByText(`Usunięto wydatek „${name}”`)).toBeVisible();
  await expectNoHorizontalScroll(page);
});

test("Goście: edycja osoby, usunięcie jednej osoby i całego zaproszenia", async ({ page }) => {
  const t = tag();
  const household = `Rodzina Testowa ${t}`;
  await openDemoWedding(page);
  await tab(page, "Goście").click();
  await page.getByRole("button", { name: "Dodaj zaproszenie" }).click();
  const add = page.getByRole("dialog");
  await add.getByLabel("Nazwa zaproszenia").fill(household);
  await add.getByLabel("Osoby").fill(`Anna Test${t}, Jan Test${t}`);
  await add.getByRole("button", { name: "Dodaj zaproszenie" }).click();
  await expect(page.getByText(`Dodano zaproszenie „${household}”`)).toBeVisible();

  await page.getByLabel("Szukaj osoby lub rodziny").fill(household);
  await page.getByRole("button", { name: new RegExp(household) }).click();
  await page.getByRole("button", { name: `Anna Test${t}`, exact: true }).click();
  const sheet = page.getByRole("dialog", { name: "Gość" });
  await sheet.getByLabel("Imię").fill("Hanna");
  await sheet.getByText("Potrzebuje noclegu").click();
  await expectAccessible(page);
  await sheet.getByRole("button", { name: "Zapisz" }).click();
  await expect(page.getByText("Zapisano gościa")).toBeVisible();

  // Dwie osoby w zaproszeniu: dialog pyta, kogo usunąć.
  await page.getByRole("button", { name: `Jan Test${t}`, exact: true }).click();
  await sheet.getByRole("button", { name: "Usuń osobę" }).click();
  await expect(page.getByRole("heading", { name: "Kogo usunąć?" })).toBeVisible();
  await page.getByRole("button", { name: "Usuń tylko: Jan" }).click();
  await expect(page.getByText(`Usunięto: Jan Test${t}`)).toBeVisible();

  await page.getByRole("button", { name: "Edytuj zaproszenie" }).click();
  const hs = page.getByRole("dialog", { name: "Zaproszenie" });
  await expect(hs.getByLabel("Nazwa zaproszenia")).toHaveValue(household);
  await expectAccessible(page);
  await hs.getByRole("button", { name: "Usuń zaproszenie" }).click();
  await page.getByRole("button", { name: "Usuń", exact: true }).click();
  await expect(page.getByText(`Usunięto zaproszenie „${household}”`)).toBeVisible();
  await expect(page.getByText("Nikt nie pasuje do wyszukiwania.")).toBeVisible();
  await expectNoHorizontalScroll(page);
});

test("RSVP: link dla rodziny, odpowiedź gościa bez logowania, wyłączenie linku", async ({ page, browser }) => {
  const t = tag();
  const household = `Rodzina RSVP ${t}`;
  await openDemoWedding(page);
  await tab(page, "Goście").click();
  await page.getByRole("button", { name: "Dodaj zaproszenie" }).click();
  const add = page.getByRole("dialog");
  await add.getByLabel("Nazwa zaproszenia").fill(household);
  await add.getByLabel("Osoby").fill(`Ola Rsvp${t}, Kuba Rsvp${t}`);
  await add.getByRole("button", { name: "Dodaj zaproszenie" }).click();
  await page.getByLabel("Szukaj osoby lub rodziny").fill(household);
  await page.getByRole("button", { name: new RegExp(household) }).click();
  await page.getByRole("button", { name: "Edytuj zaproszenie" }).click();
  const sheet = page.getByRole("dialog", { name: "Zaproszenie" });
  await sheet.getByRole("button", { name: "Utwórz link" }).click();
  const link = await sheet.getByLabel("Link (widoczny tylko teraz)").inputValue();
  expect(link).toMatch(/\/rsvp\/[\w-]+$/);
  // Kod QR przy nowym linku: obraz i pobranie SVG.
  await expect(sheet.getByRole("img", { name: `Kod QR z linkiem do odpowiedzi dla: ${household}` })).toBeVisible();
  const svg = page.waitForEvent("download");
  await sheet.getByRole("button", { name: "Pobierz kod QR (SVG)" }).click();
  expect((await svg).suggestedFilename()).toMatch(/^kod-qr-rodzina-rsvp-[a-z0-9]+\.svg$/);

  // Gość: osobna przeglądarka, bez sesji pary.
  const guest = await browser.newContext({ locale: "pl-PL", timezoneId: "Europe/Warsaw" });
  const g = await guest.newPage();
  await g.setViewportSize(page.viewportSize()!);
  await g.goto(link);
  await expect(g.getByRole("heading", { name: household, level: 1 })).toBeVisible();
  await expect(g.getByText("Wesele demo")).toBeVisible();
  await expectAccessible(g);
  await expectNoHorizontalScroll(g);
  const ola = g.getByRole("region", { name: `Ola` }).or(g.locator(".wp-card", { has: g.getByRole("heading", { name: "Ola" }) }));
  await ola.locator(".wp-segmented__option", { hasText: "Będę" }).first().click();
  await ola.getByText("Potrzebuję noclegu").click();

  // Osoba towarzysząca: gość dopisuje ją sam i od razu potwierdza obecność.
  await g.getByRole("button", { name: "Dodaj osobę towarzyszącą" }).click();
  await g.getByLabel("Imię").fill("Ewa");
  await g.getByRole("button", { name: "Dodaj", exact: true }).click();
  const ewa = g.locator(".wp-card", { has: g.getByRole("heading", { name: "Ewa" }) });
  await expect(ewa.getByRole("button", { name: "Usuń: Ewa" })).toBeVisible();
  await ewa.locator(".wp-segmented__option", { hasText: "Będę" }).first().click();
  await expectAccessible(g);
  await expectNoHorizontalScroll(g);

  await g.getByRole("button", { name: /^Wyślij/ }).click();
  await expect(g.getByRole("heading", { name: "Dziękujemy!" })).toBeVisible();
  await expect(g.getByText("Do zobaczenia: Ola, Ewa.")).toBeVisible();
  // Para widzi odpowiedź; po wyłączeniu link przestaje działać.
  await sheet.getByRole("button", { name: "Wyłącz link" }).click();
  await expect(page.getByText("Link wyłączony")).toBeVisible();
  await g.goto(link);
  await expect(g.getByRole("heading", { name: "Link nie działa" })).toBeVisible();
  await guest.close();

  await sheet.getByRole("button", { name: "Usuń zaproszenie" }).click();
  await page.getByRole("button", { name: "Usuń", exact: true }).click();
  await expect(page.getByText(`Usunięto zaproszenie „${household}”`)).toBeVisible();
});

test("Harmonogram dnia: typowy program, przesunięcie, nowy punkt", async ({ page, request }) => {
  // Osobne, tymczasowe wesele: szablon wstawia się tylko do pustego harmonogramu.
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  expect(login.ok()).toBeTruthy();
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const created = await request.post("/api/v1/weddings", {
    headers: auth,
    data: { name: `Test harmonogramu ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "religious_other" },
  });
  expect(created.ok()).toBeTruthy();
  const weddingId = (await created.json()).id as string;
  try {
    await openDemoWedding(page);
    await page.goto(`/w/${weddingId}/dzien`);
    await expect(page.getByRole("heading", { name: "Harmonogram dnia" })).toBeVisible();
    await page.getByRole("button", { name: "Wczytaj typowy program" }).click();
    const sheet = page.getByRole("dialog", { name: "Typowy program dnia" });
    await sheet.getByRole("group", { name: "Godzina ceremonii" }).getByRole("spinbutton").first().click();
    await page.keyboard.type("1500");
    await sheet.getByRole("button", { name: "Pokaż program" }).click();
    await expect(sheet.getByText("Krojenie tortu")).toBeVisible();
    await expectAccessible(page);
    await sheet.getByRole("button", { name: "Wstaw do harmonogramu" }).click();
    await expect(page.getByText(/^Dodano \d+ punkt/)).toBeVisible();
    await expect(page.getByRole("button", { name: /Krojenie tortu/ })).toBeVisible();
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

    // Opóźnienie: tort i wszystko po nim 15 minut później.
    await page.getByRole("button", { name: /Krojenie tortu/ }).click();
    const item = page.getByRole("dialog", { name: "Punkt programu" });
    await item.getByRole("button", { name: "+15 min" }).click();
    const confirm = page.getByRole("alertdialog", { name: "Przesunąć program?" }).or(page.getByRole("dialog", { name: "Przesunąć program?" }));
    await expect(confirm.getByText("Krojenie tortu")).toBeVisible();
    await confirm.getByRole("button", { name: "Przesuń" }).click();
    await expect(page.getByText(/^Przesunięto \d+ punkt/)).toBeVisible();

    // Nieaktualny podgląd: ktoś zmienia program między podglądem a zatwierdzeniem → nic się nie przesuwa.
    await page.getByRole("button", { name: /Krojenie tortu/ }).click();
    await item.getByRole("button", { name: "+15 min" }).click();
    await expect(confirm.getByText("Krojenie tortu")).toBeVisible();
    const schedule = await (await request.get(`/api/v1/weddings/${weddingId}/schedule`, { headers: auth })).json();
    const cake = schedule.find((i: { title: string }) => i.title === "Krojenie tortu");
    const patched = await request.patch(`/api/v1/weddings/${weddingId}/schedule/${cake.id}`, {
      headers: { ...auth, "If-Match": `"${cake.version}"` },
      data: { location: "Sala główna" },
    });
    expect(patched.ok()).toBeTruthy();
    await confirm.getByRole("button", { name: "Przesuń" }).click();
    await expect(item.getByText(/Ktoś zmienił te dane w międzyczasie/)).toBeVisible();
    await item.getByRole("button", { name: "Zamknij" }).click();
    await expect(item).toHaveCount(0);

    await page.getByRole("button", { name: "Dodaj punkt" }).click();
    const add = page.getByRole("dialog", { name: "Nowy punkt programu" });
    await add.getByLabel("Co się dzieje?").fill("Pokaz fajerwerków");
    await add.getByRole("group", { name: "Godzina" }).getByRole("spinbutton").first().click();
    await page.keyboard.type("2330");
    await add.getByRole("button", { name: "Dodaj punkt" }).click();
    await expect(page.getByRole("button", { name: /^23:30.*Pokaz fajerwerków/ })).toBeVisible();
  } finally {
    await request.delete(`/api/v1/weddings/${weddingId}`, { headers: auth });
  }
});

test("Wydarzenia: szybki start, godziny przez północ, adres, usunięcie", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const created = await request.post("/api/v1/weddings", {
    headers: auth,
    data: { name: `Test wydarzeń ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" },
  });
  const weddingId = (await created.json()).id as string;
  try {
    await openDemoWedding(page);
    await page.goto(`/w/${weddingId}/ustawienia`);
    const section = page.getByRole("region", { name: "Wydarzenia" });
    await section.getByRole("button", { name: "Dodaj ceremonię i przyjęcie" }).click();
    await expect(section.getByRole("button", { name: /^Ślub cywilny/ })).toBeVisible();
    await section.getByRole("button", { name: /^Przyjęcie weselne/ }).click();
    const sheet = page.getByRole("dialog", { name: "Wydarzenie" });
    await sheet.getByRole("group", { name: "Początek" }).getByRole("spinbutton").first().click();
    await page.keyboard.type("1700");
    await sheet.getByRole("group", { name: "Koniec (opcjonalnie)" }).getByRole("spinbutton").first().click();
    await page.keyboard.type("0400");
    await sheet.getByLabel("Adres (widzą go goście)").fill("Dworek pod Lipami, Lipowa 1");
    await expectAccessible(page);
    await sheet.getByRole("button", { name: "Zapisz" }).click();
    await expect(section.getByRole("button", { name: /Przyjęcie weselne.*17 czerwca 2028, godz\. 17:00.*Dworek pod Lipami/ })).toBeVisible();
    // Koniec po północy zapisany na następny dzień.
    const events = await (await request.get(`/api/v1/weddings/${weddingId}/events`, { headers: auth })).json();
    const reception = events.find((e: { kind: string }) => e.kind === "reception");
    expect(new Date(reception.ends_at).toISOString()).toBe("2028-06-18T02:00:00.000Z");

    await section.getByRole("button", { name: /^Ślub cywilny/ }).click();
    await sheet.getByRole("button", { name: "Usuń wydarzenie" }).click();
    await expect(page.getByText("razem z odpowiedziami gości")).toBeVisible();
    await page.getByRole("button", { name: "Usuń", exact: true }).click();
    await expect(section.getByRole("button", { name: /^Ślub cywilny/ })).toHaveCount(0);
    await expectNoHorizontalScroll(page);
  } finally {
    await request.delete(`/api/v1/weddings/${weddingId}`, { headers: auth });
  }
});

test("Plan stołów: stoły, automat z podglądem, przeniesienie, reguła", async ({ page, request }) => {
  test.setTimeout(90_000); // automat liczy do 10 s
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", {
      headers: auth,
      data: { name: `Test stołów ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" },
    })
  ).json();
  try {
    for (const [family, people] of [
      ["Kowalscy", ["Anna", "Piotr", "Zosia"]],
      ["Nowakowie", ["Ewa", "Marek"]],
      ["Wiśniewska", ["Ola"]],
    ] as const) {
      const h = await (
        await request.post(`/api/v1/weddings/${w.id}/households`, {
          headers: auth,
          data: { name: family, side: "both", invitation_status: "not_sent" },
        })
      ).json();
      for (const first of people) {
        await request.post(`/api/v1/weddings/${w.id}/households/${h.id}/guests`, {
          headers: auth,
          data: { first_name: first, last_name: family, age_group: "adult", is_plus_one: false, dietary_preference: "standard", needs_accommodation: false, needs_transport: false },
        });
      }
    }
    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/stoly`);
    await expect(page.getByRole("heading", { name: "Nie ma jeszcze stołów" })).toBeVisible();
    await page.getByRole("button", { name: "Dodaj stoły" }).click();
    const add = page.getByRole("dialog", { name: "Dodaj stoły" });
    await add.getByLabel("Ile stołów?").fill("2");
    await add.getByLabel("Miejsc przy stole").fill("4");
    await add.getByText("Dodaj też stół pary młodej").click(); // bez stołu pary młodej
    await add.getByRole("button", { name: "Dodaj", exact: true }).click();
    await expect(page.getByText("Dodano 2 stoły")).toBeVisible();
    await expect(page.getByText(/bez miejsca: 6/)).toBeVisible();

    await page.getByRole("button", { name: "Usadź automatycznie" }).click();
    const auto = page.getByRole("dialog", { name: "Usadź automatycznie" });
    await auto.getByRole("button", { name: "Pokaż propozycję" }).click();
    await expect(auto.getByText(/Stół 1 \(\d\/4\)/)).toBeVisible({ timeout: 30_000 });
    await expectAccessible(page);
    await auto.getByRole("button", { name: "Zapisz ten układ" }).click();
    await expect(page.getByText("Zapisano układ stołów")).toBeVisible();
    await expect(page.getByText(/bez miejsca: 0/)).toBeVisible();
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

    // Ręczne przeniesienie Oli: przypina miejsce.
    await page.getByRole("button", { name: "Ola Wiśniewska", exact: true }).click();
    const move = page.getByRole("dialog", { name: "Gdzie siedzi Ola Wiśniewska?" });
    await move.getByRole("button", { name: /^Stół \d/ }).filter({ hasNotText: "tu siedzi teraz" }).first().click();
    await expect(page.getByText(/^Ola Wiśniewska → Stół \d$/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Ola Wiśniewska (przypięty)" })).toBeVisible();

    await page.getByRole("region", { name: "Razem i osobno" }).getByRole("button", { name: "Dodaj" }).click();
    const rule = page.getByRole("dialog", { name: "Nowa reguła" });
    await rule.getByRole("button", { name: /Osoba/ }).click();
    await page.getByRole("option", { name: "Anna Kowalscy" }).click();
    await rule.getByRole("button", { name: /Druga osoba/ }).click();
    await page.getByRole("option", { name: "Marek Nowakowie" }).click();
    await rule.getByRole("button", { name: "Dodaj regułę" }).click();
    await expect(page.getByText("Anna Kowalscy osobno od Marek Nowakowie")).toBeVisible();
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Oferty: usługodawca, oferta ręcznie, zatwierdzenie, porównanie i wybór z konsekwencjami", async ({ page, request }) => {
  test.setTimeout(90_000);
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", {
      headers: auth,
      data: { name: `Test ofert ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil", guest_count_planned: 80 },
    })
  ).json();
  try {
    // Druga sala przez API: 280 zł za osobę, już sprawdzona.
    const other = await (
      await request.post(`/api/v1/weddings/${w.id}/vendors`, { headers: auth, data: { name: "Sala Druga", category: "venue" } })
    ).json();
    const otherOffer = await request.post(`/api/v1/weddings/${w.id}/offers`, {
      headers: auth,
      data: { vendor_id: other.id, title: "Pakiet Srebrny", status: "approved", components: [{ label: "Menu", kind: "per_guest", amount: 280 }] },
    });
    expect(otherOffer.ok()).toBeTruthy();

    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/uslugodawcy`);
    await page.getByRole("button", { name: "Dodaj usługodawcę" }).click();
    const vs = page.getByRole("dialog", { name: "Nowy usługodawca" });
    await vs.getByLabel("Nazwa").fill("Dworek Testowy");
    await vs.getByRole("button", { name: /Kategoria/ }).click();
    await page.getByRole("option", { name: "Sala weselna" }).click();
    await vs.getByLabel("Telefon (opcjonalnie)").fill("600 100 200");
    await expectAccessible(page);
    await vs.getByRole("button", { name: "Dodaj usługodawcę" }).click();
    await expect(page.getByRole("heading", { name: "Dworek Testowy", level: 1 })).toBeVisible();
    await expect(page.getByRole("link", { name: "600 100 200" })).toHaveAttribute("href", "tel:600100200");

    await page.getByRole("button", { name: "Dodaj ofertę" }).click();
    const os = page.getByRole("dialog", { name: "Nowa oferta" });
    await os.getByLabel("Nazwa oferty").fill("Pakiet Złoty");
    // Oferta sali startuje z typowych pozycji; wypełniamy pierwszą (menu), resztę bez kwot pominie zapis.
    await expect(os.locator(".offer-row").first().getByLabel("Za co?")).toHaveValue("Menu weselne");
    await os.locator(".offer-row").first().getByLabel("Kwota za osobę").fill("250");
    await os.getByRole("button", { name: "Dodaj pozycję" }).click();
    const row2 = os.locator(".offer-row").last();
    await row2.getByLabel("Za co?").fill("Obsługa kelnerska");
    await row2.getByLabel("Kwota", { exact: true }).fill("2000");
    await os.getByLabel("Kwota (opcjonalnie)").fill("5000");
    await expectAccessible(page);
    await os.getByRole("button", { name: "Dodaj ofertę" }).click();
    await expect(page.getByRole("heading", { name: "Pakiet Złoty", level: 1 })).toBeVisible();
    await expect(page.getByText("250 zł za osobę")).toBeVisible();
    await page.getByRole("button", { name: "Zatwierdź ofertę" }).click();
    await expect(page.getByText("Oferta sprawdzona")).toBeVisible();
    // Po przewinięciu link „wstecz” chowa się pod przyklejonym nagłówkiem (axe uznaje go za zasłonięty).
    await page.evaluate(() => window.scrollTo(0, 0));
    await expectAccessible(page);

    await page.getByRole("link", { name: "Porównaj z innymi" }).click();
    await page.getByRole("button", { name: "Porównaj", exact: true }).click();
    const gold = page.locator(".quote", { hasText: "Pakiet Złoty" });
    await expect(gold).toContainText(/22\s000\szł/); // 80 × 250 + 2000
    await expect(gold).toContainText("Najtańsza");
    await expect(page.locator(".quote", { hasText: "Pakiet Srebrny" })).toContainText(/22\s400\szł/);
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

    // „Co jeśli”: dwa scenariusze obok siebie (jeden profil telefonu i jeden komputera).
    if (["390-light", "1280-light"].includes(test.info().project.name)) {
      await page.getByRole("button", { name: /Co jeśli/ }).click();
      await page.getByText("Porównaj dwa scenariusze").click();
      await page.getByRole("group", { name: "B: Co jeśli" }).getByLabel("Dorośli").fill("100");
      await page.getByRole("button", { name: "Porównaj", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Plan i Co jeśli" })).toBeVisible();
      const card = page.getByRole("region", { name: "Dworek Testowy: Pakiet Złoty" });
      if (page.viewportSize()!.width >= 768) {
        // Tabela: 80 × 250 + 2000 = 22 000 → 100 × 250 + 2000 = 27 000; dopłata 27 000 − 5 000 zadatku.
        const row = page.getByRole("row", { name: /Dworek Testowy/ });
        await expect(row).toContainText(/22\s000\szł/);
        await expect(row).toContainText(/27\s000\szł/);
        await expect(row).toContainText(/\+5\s000\szł/);
        await expect(row).toContainText(/22\s000\szł/);
      } else {
        await expect(card).toContainText(/27\s000\szł/);
        await expect(card).toContainText(/\+5\s000\szł/);
      }
      await card.getByRole("button", { name: /Raty i dopłata/ }).click();
      await expect(card).toContainText(/\+5\s000\szł w dopłacie/);
      await expect(card).toContainText("Dopłata (wyliczona)");
      await expectAccessible(page);
      await expectNoHorizontalScroll(page);
      await page.getByText("Porównaj dwa scenariusze").click();
      await expect(gold).toBeVisible();
    }

    await gold.getByRole("button", { name: "Wybieram tę ofertę" }).click();
    const dialog = page.getByRole("alertdialog", { name: "Wybrać tę ofertę?" }).or(page.getByRole("dialog", { name: "Wybrać tę ofertę?" }));
    await expect(dialog).toContainText("1 inna oferta z tej kategorii zostanie odrzucona");
    await expect(dialog).toContainText(/22\s000\szł/);
    await expectAccessible(page);
    await dialog.getByRole("button", { name: "Wybieram", exact: true }).click();
    await expect(page.getByText(/^Wybrano\. W budżecie: 22\s000\szł, płatności: 1/)).toBeVisible();
    await expect(page.getByText("Wybrana oferta — jest w budżecie.")).toBeVisible();

    await page.getByRole("link", { name: "Przejdź do budżetu" }).click();
    await expect(page.getByRole("button", { name: /Dworek Testowy: Pakiet Złoty/ })).toBeVisible();
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

/** Najprostszy poprawny PDF z jedną linią tekstu (bez zależności). */
function tinyPdf(text: string): Buffer {
  const content = `BT /F1 18 Tf 50 750 Td (${text}) Tj ET`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${content.length} >>\nstream\n${content}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let pdf = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((o, i) => {
    offsets.push(pdf.length);
    pdf += `${i + 1} 0 obj\n${o}\nendobj\n`;
  });
  const xref = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n${offsets.map((o) => `${String(o).padStart(10, "0")} 00000 n \n`).join("")}`;
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(pdf, "latin1");
}

test("Dokumenty: wgranie oferty PDF z karty usługodawcy, odczyt tekstu, pobranie", async ({ page, request }) => {
  test.setTimeout(90_000);
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", { headers: auth, data: { name: `Test dokumentów ${tag()}`, ceremony_type: "civil" } })
  ).json();
  try {
    const v = await (
      await request.post(`/api/v1/weddings/${w.id}/vendors`, { headers: auth, data: { name: "Dworek PDF", category: "venue" } })
    ).json();
    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/uslugodawcy/${v.id}`);
    await page.getByRole("button", { name: "Wgraj ofertę lub umowę" }).click();
    const sheet = page.getByRole("dialog", { name: "Nowy dokument" });
    await sheet.locator('input[type="file"]').setInputFiles({ name: "oferta-dworek.pdf", mimeType: "application/pdf", buffer: tinyPdf("Menu weselne 250 zl za osobe") });
    await expect(sheet.getByText(/oferta-dworek\.pdf · \d+ KB/)).toBeVisible();
    await expect(sheet.getByLabel("Tytuł")).toHaveValue("oferta-dworek");
    await expectAccessible(page);
    await sheet.getByRole("button", { name: "Wgraj" }).click();
    await expect(page.getByText("Wgrano „oferta-dworek”")).toBeVisible();
    // Tekst odczytuje worker w tle; lista sama się odświeża.
    await expect(page.getByText("Tekst gotowy")).toBeVisible({ timeout: 45_000 });

    await page.getByRole("button", { name: /^oferta-dworek/ }).click();
    const details = page.getByRole("dialog", { name: "oferta-dworek" });
    const download = page.waitForEvent("download");
    await details.getByRole("button", { name: "Pobierz plik" }).click();
    expect((await download).suggestedFilename()).toBe("oferta-dworek.pdf");
    await expect(details.getByRole("button", { name: "Odczytaj ofertę" })).toBeEnabled();
    await details.getByRole("button", { name: "Odczytany tekst" }).click();
    await expect(details.getByRole("region", { name: "Strona 1" })).toContainText("Menu weselne 250 zl za osobe");
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);
    await page.keyboard.press("Escape");

    // Wyszukiwanie w treści (wielkość liter bez znaczenia), fragment ze stroną.
    await page.goto(`/w/${w.id}/dokumenty`);
    await page.getByLabel("Szukaj w dokumentach").fill("ZA OSOBE");
    const hit = page.getByRole("button", { name: /oferta-dworek.*strona 1.*Menu weselne 250 zl za osobe/ });
    await expect(hit).toBeVisible();
    await expectAccessible(page);
    await page.getByLabel("Szukaj w dokumentach").fill("nadgodziny");
    await expect(page.getByText("Nic nie znaleźliśmy dla „nadgodziny”.")).toBeVisible();
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Budżet: płatności wydatku, kategorie z planem, podział budżetu z podglądem", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", {
      headers: auth,
      data: { name: `Test budżetu ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil", total_budget: { amount: "80000", currency: "PLN" } },
    })
  ).json();
  try {
    const cats = await (await request.get(`/api/v1/weddings/${w.id}/budget/categories`, { headers: auth })).json();
    await request.post(`/api/v1/weddings/${w.id}/budget/items`, {
      headers: auth,
      data: { category_id: cats[0].id, name: "Fotograf testowy", cost_mode: "fixed", planned: { amount: "6000", currency: "PLN" }, status: "planned" },
    });
    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/budzet`);

    // Podział budżetu: podgląd, potem zapis.
    await page.getByRole("button", { name: "Podziel budżet na kategorie" }).click();
    const split = page.getByRole("alertdialog", { name: "Podzielić budżet?" }).or(page.getByRole("dialog", { name: "Podzielić budżet?" }));
    await expect(split.getByText(/→/).first()).toBeVisible();
    await expectAccessible(page);
    await split.getByRole("button", { name: "Zastosuj podział" }).click();
    await expect(page.getByText("Podzielono budżet na kategorie")).toBeVisible();

    // Nowa kategoria z planem.
    await page.getByRole("region", { name: "Kategorie" }).getByRole("button", { name: "Dodaj" }).click();
    const cs = page.getByRole("dialog", { name: "Nowa kategoria" });
    await cs.getByLabel("Nazwa").fill("Fotobudka");
    await cs.getByLabel("Plan na kategorię (opcjonalnie)").fill("1500");
    await cs.getByRole("button", { name: "Dodaj kategorię" }).click();
    await expect(page.getByRole("button", { name: /^Fotobudka/ })).toContainText(/1\s500\szł/);

    // Płatności: zadatek zapłacony, rata z terminem, potem oznaczenie raty.
    await page.getByRole("button", { name: /^Fotograf testowy/ }).click();
    const sheet = page.getByRole("dialog", { name: "Wydatek" });
    await sheet.getByRole("button", { name: "Dodaj płatność" }).click();
    await expect(sheet.getByText("art. 394 KC")).toBeVisible();
    await sheet.getByLabel("Kwota", { exact: true }).fill("1500");
    await sheet.getByText("Już zapłacone (dzisiaj)").click();
    await expectAccessible(page);
    await sheet.getByRole("button", { name: "Dodaj płatność" }).last().click();
    await expect(page.getByText("Dodano płatność")).toBeVisible();
    await expect(sheet.getByText(/Zadatek · 1\s500\szł/)).toBeVisible();
    await expect(sheet.getByText(/^Zapłacono/)).toBeVisible();

    await sheet.getByRole("button", { name: "Dodaj płatność" }).click();
    await sheet.getByRole("button", { name: /Rodzaj/ }).click();
    await page.getByRole("option", { name: "Rata" }).click();
    await sheet.getByLabel("Kwota", { exact: true }).fill("4500");
    await sheet.getByRole("button", { name: "Dodaj płatność" }).last().click();
    await expect(sheet.getByText(/Rata · 4\s500\szł/)).toBeVisible();
    await sheet.getByRole("button", { name: /Rata · 4\s500\szł/ }).click();
    await sheet.getByRole("button", { name: "Oznacz jako zapłacone" }).click();
    await expect(page.getByText("Oznaczono jako zapłacone")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.locator(".stat", { hasText: "Wpłacono" })).toContainText(/6\s000\szł/);
    await expectNoHorizontalScroll(page);
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Goście: import z pliku CSV (polskie nagłówki), podgląd, błędy wierszy, zapis", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", { headers: auth, data: { name: `Test importu ${tag()}`, ceremony_type: "civil" } })
  ).json();
  try {
    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/goscie`);
    await page.getByRole("button", { name: "Import z pliku" }).click();
    const sheet = page.getByRole("dialog", { name: "Import gości z pliku" });
    const download = page.waitForEvent("download");
    await sheet.getByRole("button", { name: "Pobierz wzór pliku" }).click();
    expect((await download).suggestedFilename()).toBe("goscie-wzor.csv");

    // Plik z błędem w drugim wierszu (nieznana dieta).
    const bad = "Zaproszenie;Imię;Nazwisko;Dieta\r\nKowalscy;Anna;Kowalska;\r\nKowalscy;Piotr;Kowalski;paleo\r\n";
    await sheet.locator('input[type="file"]').setInputFiles({ name: "goscie.csv", mimeType: "text/csv", buffer: Buffer.from(bad, "utf8") });
    await expect(sheet.getByText(/Wiersz 3: Nieznana dieta/)).toBeVisible();
    await expect(sheet.getByRole("button", { name: "Importuj" })).toHaveCount(0);

    const good = "Zaproszenie;Imię;Nazwisko;Wiek;Nocleg\r\nKowalscy;Anna;Kowalska;dorosły;tak\r\nKowalscy;Zosia;Kowalska;dziecko;tak\r\nNowakowie;Ewa;Nowak;;\r\n";
    await sheet.locator('input[type="file"]').setInputFiles({ name: "goscie.csv", mimeType: "text/csv", buffer: Buffer.from(good, "utf8") });
    await expect(sheet.getByText("3 osoby w 2 zaproszeniach")).toBeVisible();
    await expectAccessible(page);
    await sheet.getByRole("button", { name: "Importuj" }).click();
    await expect(page.getByText("Zaimportowano 3 osoby")).toBeVisible();
    await expect(page.getByRole("button", { name: /Kowalscy/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Nowakowie/ })).toBeVisible();
    await expectNoHorizontalScroll(page);
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});


test("Plan: zależność zadań („czeka na”) i jej usunięcie", async ({ page }) => {
  const t = tag();
  const first = `Ustalić listę gości ${t}`;
  const second = `Wysłać zaproszenia ${t}`;
  await openDemoWedding(page);
  await tab(page, "Plan").click();
  for (const title of [first, second]) {
    await page.getByRole("main").getByRole("button", { name: "Dodaj zadanie" }).click();
    await page.getByRole("dialog").getByLabel("Co trzeba zrobić?").fill(title);
    await page.getByRole("dialog").getByRole("button", { name: "Dodaj zadanie" }).click();
    await expect(page.getByText(`Dodano zadanie „${title}”`)).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
  }
  await page.locator(".wp-segmented__option", { hasText: "Później" }).click();
  await page.getByRole("button", { name: new RegExp(`^${second}`) }).click();
  const sheet = page.getByRole("dialog", { name: "Zadanie" });
  await sheet.getByRole("button", { name: "Dodaj zadanie, które musi być wcześniej" }).click();
  await sheet.getByRole("button", { name: /Które zadanie musi być wcześniej/ }).click();
  await page.getByRole("option", { name: first }).click();
  await expect(sheet.getByText("jeszcze nie zrobione")).toBeVisible();
  await expectAccessible(page);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: new RegExp(`^${second}.*czeka na „${first}”`) })).toBeVisible();

  // Sprzątanie: usuwamy oba zadania.
  for (const title of [second, first]) {
    await page.getByRole("button", { name: new RegExp(`^${title}`) }).click();
    await sheet.getByRole("button", { name: "Usuń zadanie" }).click();
    await page.getByRole("button", { name: "Usuń", exact: true }).click();
    await expect(page.getByText(`Usunięto zadanie „${title}”`)).toBeVisible();
  }
});

test("Link dla sali: liczby dla kuchni, zgoda na listę diet, stoły", async ({ page, browser, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", {
      headers: auth,
      data: { name: `Test sali ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil", guest_count_planned: 80 },
    })
  ).json();
  const api = (path: string) => `/api/v1/weddings/${w.id}${path}`;
  try {
    const sala = await (await request.post(api("/vendors"), { headers: auth, data: { name: "Dworek Kuchnia", category: "venue" } })).json();
    await request.post(api("/schedule/from-template"), { headers: auth, data: { day: "2028-06-17", ceremony_time: "15:00", dry_run: false } });
    const reception = await (await request.post(api("/events"), { headers: auth, data: { kind: "reception", name: "Przyjęcie" } })).json();
    const h = await (await request.post(api("/households"), { headers: auth, data: { name: "Nowakowie" } })).json();
    const guest = async (first_name: string, age_group: string, extra = {}) =>
      (await (await request.post(api(`/households/${h.id}/guests`), { headers: auth, data: { first_name, age_group, ...extra } })).json()) as { id: string };
    const ania = await guest("Ania", "adult", { dietary_preference: "vegan", dietary_note: "alergia na orzechy" });
    const kuba = await guest("Kuba", "child");
    await guest("Ola", "adult");
    for (const g of [ania, kuba]) {
      await request.put(api(`/guests/${g.id}/attendance/${reception.id}`), { headers: auth, data: { status: "attending" } });
    }
    const t1 = await (await request.post(api("/seating/tables"), { headers: auth, data: { name: "Stół Młodej", capacity: 8 } })).json();
    for (const g of [ania, kuba]) {
      expect((await request.put(api(`/seating/guests/${g.id}`), { headers: auth, data: { table_id: t1.id } })).ok()).toBeTruthy();
    }

    // Para: zgoda na listę diet przy tworzeniu linku.
    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/uslugodawcy/${sala.id}`);
    await expect(page.getByText("Sala i catering widzą też liczby dla kuchni")).toBeVisible();
    await page.getByText("Udostępnić sali listę diet i plan stołów").click();
    await expect(page.getByText("Uwagi dietetyczne mogą dotyczyć zdrowia")).toBeVisible();
    await page.getByRole("button", { name: "Utwórz link" }).click();
    const link = (await page.locator(".feed-url").textContent())!.trim();
    expect(link).toMatch(/\/dzien\/[\w-]+$/);
    await expectAccessible(page);

    // Sala: osobna przeglądarka, bez logowania.
    const venue = await browser.newContext({ locale: "pl-PL", timezoneId: "Europe/Warsaw" });
    const v = await venue.newPage();
    await v.setViewportSize(page.viewportSize()!);
    await v.goto(link);
    const section = v.getByRole("region", { name: "Dla kuchni i obsługi sali" });
    await expect(section).toContainText("1 dorosły, 1 dziecko");
    await expect(section).toContainText("wegańska: 1");
    await expect(section).toContainText("Stół Młodej");
    await expect(section).toContainText("alergia na orzechy");
    await expect(section).toContainText(/Jeszcze bez odpowiedzi\s*1/);
    // Program do kalendarza (sala nie ma własnych punktów — cały program dnia).
    const cal = v.waitForEvent("download");
    await v.getByRole("button", { name: "Dodaj program do kalendarza" }).click();
    const calFile = await cal;
    expect(calFile.suggestedFilename()).toBe("program-wesela.ics");
    expect((await import("node:fs")).readFileSync((await calFile.path())!, "utf8")).toContain("BEGIN:VEVENT");
    await expectAccessible(v);
    await expectNoHorizontalScroll(v);
    await venue.close();
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Karty z kodem QR i wygląd strony dla gości", async ({ page, browser, request }) => {
  test.skip(!test.info().project.name.startsWith("390"), "motywy sprawdzamy na 390 px (jasny i ciemny)");
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", {
      headers: auth,
      data: { name: `Test QR ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil", guest_count_planned: 40 },
    })
  ).json();
  const api = (path: string) => `/api/v1/weddings/${w.id}${path}`;
  try {
    const withLink = await (await request.post(api("/households"), { headers: auth, data: { name: "Rodzina Z Linkiem" } })).json();
    await request.post(api("/households"), { headers: auth, data: { name: "Rodzina Bez Linku", rsvp_deadline: "2028-05-01" } });
    const token = (await (await request.post(api(`/households/${withLink.id}/rsvp-link`), { headers: auth })).json()).token as string;

    // Druk hurtowy: rodzina z linkiem pominięta, karta z kodem dla drugiej.
    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/druk/qr`);
    await expect(page.getByText("Pominięte, bo mają aktywny link: 1.")).toBeVisible();
    await page.getByRole("button", { name: "Utwórz linki i przygotuj karty (1)" }).click();
    const card = page.locator(".qr-card", { hasText: "Rodzina Bez Linku" });
    await expect(card.getByRole("img", { name: "Kod QR dla: Rodzina Bez Linku" })).toBeVisible();
    await expect(card).toContainText("Zeskanujcie, aby potwierdzić obecność do 1 maja 2028.");
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

    // Wygląd: wybór w arkuszu „Strona dla gości” (Goście → Strona gościa) z podglądem.
    await page.goto(`/w/${w.id}/strona-goscia`);
    await page.getByRole("button", { name: "Edytuj informacje i wygląd strony" }).click();
    const sheet = page.getByRole("dialog", { name: "Strona dla gości" });
    await sheet.locator(".wp-segmented__option", { hasText: "Ogród" }).click();
    await sheet.locator(".wp-segmented__option", { hasText: "Szałwia" }).click();
    await expect(sheet.getByLabel("Podgląd wyglądu")).toHaveAttribute("data-guest-theme", "garden");
    await expectAccessible(page);
    await sheet.getByRole("button", { name: "Zapisz" }).click();
    await expect(page.getByText("Zapisano (jeszcze niewidoczne dla gości)")).toBeVisible();

    // Gość: każdy motyw czytelny (axe) w jasnym i ciemnym motywie urządzenia.
    const guest = await browser.newContext({ locale: "pl-PL", timezoneId: "Europe/Warsaw", colorScheme: test.info().project.name.endsWith("dark") ? "dark" : "light" });
    const g = await guest.newPage();
    await g.setViewportSize(page.viewportSize()!);
    let version = 1;
    for (const [theme, accent] of [["garden", "sage"], ["modern", "navy"], ["classic", null]] as const) {
      if (theme !== "garden") {
        const r = await request.put(api("/guest-info"), { headers: { ...auth, "If-Match": `"${version}"` }, data: { theme, accent, published: true, welcome: "Do zobaczenia!" } });
        expect(r.ok()).toBeTruthy();
        version += 1;
      }
      await g.goto(`/rsvp/${token}`);
      await expect(g.getByRole("heading", { name: "Rodzina Z Linkiem", level: 1 })).toBeVisible();
      await expect(g.locator("main")).toHaveAttribute("data-guest-theme", theme);
      await expectAccessible(g);
      await expectNoHorizontalScroll(g);
    }
    await guest.close();
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Dzień ślubu bez sieci: kopia programu na telefonie, przesuwanie ukryte, wylogowanie usuwa kopię", async ({ page, context, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", {
      headers: auth,
      data: { name: `Test offline ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" },
    })
  ).json();
  try {
    const tpl = await request.post(`/api/v1/weddings/${w.id}/schedule/from-template`, {
      headers: auth,
      data: { day: "2028-06-17", ceremony_time: "15:00", dry_run: false },
    });
    expect(tpl.ok()).toBeTruthy();
    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/dzien`);
    await page.getByRole("button", { name: /Tryb dnia ślubu/ }).click();
    await expect(page.getByRole("heading", { name: "Przesuń ten i wszystkie późniejsze" })).toBeVisible();
    await page.getByRole("button", { name: "Zapisz program na tym telefonie (na wypadek braku zasięgu)" }).click();
    await expect(page.getByText(/^Kopia programu z godz\. \d{1,2}:\d{2} jest na tym urządzeniu/)).toBeVisible();
    const stored = await page.evaluate((id) => localStorage.getItem(`wp-day-copy:w:${id}`), w.id as string);
    expect(stored).toContain("Krojenie tortu");
    expect(stored).not.toContain("amount"); // bez kwot
    await expectAccessible(page);

    await context.setOffline(true);
    // Para może przesuwać: przesunięcia trafią do kolejki (osobny test), zwykłe przesuwanie ukryte.
    await expect(page.getByText(/Przesunięcia zapiszemy na tym telefonie i wyślemy, gdy wróci internet\./)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Przesuń ten i wszystkie późniejsze" })).toHaveCount(0);
    await expectNoHorizontalScroll(page);
    await context.setOffline(false);

    await page.getByRole("button", { name: "Wyloguj" }).click();
    await expect(page.getByRole("heading", { name: "Zaloguj się" })).toBeVisible();
    expect(await page.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith("wp-day-copy:")))).toEqual([]);
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Układ sali: przesuwanie stołu, parkiet, numery miejsc, wydruk planu sali", async ({ page, request }) => {
  test.skip(!["390-light", "390-dark", "1280-light", "1280-dark"].includes(test.info().project.name), "telefon i komputer");
  test.setTimeout(90_000);
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", {
      headers: auth,
      data: { name: `Test sali układ ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" },
    })
  ).json();
  const api = (path: string) => `/api/v1/weddings/${w.id}${path}`;
  try {
    const t1 = await (await request.post(api("/seating/tables"), { headers: auth, data: { name: "Stół 1", capacity: 8 } })).json();
    await request.post(api("/seating/tables"), { headers: auth, data: { name: "Para Młoda", capacity: 2, kind: "head" } });
    const h = await (await request.post(api("/households"), { headers: auth, data: { name: "Kowalscy" } })).json();
    for (const [first, age] of [["Anna", "adult"], ["Jan", "adult"], ["Zosia", "child"]]) {
      const g = await (await request.post(api(`/households/${h.id}/guests`), { headers: auth, data: { first_name: first, age_group: age } })).json();
      await request.put(api(`/seating/guests/${g.id}`), { headers: auth, data: { table_id: t1.id } });
    }

    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/stoly`);
    const plan = page.getByRole("img", { name: /Plan sali 20 na 12 m: 2 stołów/ });
    await expect(plan).toBeVisible();
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

    // Klawiaturowa alternatywa przeciągania: wybór stołu i przyciski.
    await page.getByRole("button", { name: /Przesuń stół/ }).click();
    await page.getByRole("option", { name: "Stół 1" }).click();
    const position = page.getByText(/^Stół 1: [\d.]+ m od lewej/);
    const before = await position.textContent();
    await page.getByRole("group", { name: "Położenie: Stół 1" }).getByRole("button", { name: "W prawo" }).click();
    await page.getByRole("group", { name: "Położenie: Stół 1" }).getByRole("button", { name: "Obróć" }).click();
    await expect(position).not.toHaveText(before!);
    await expect(position).toContainText("obrót 45°");
    await page.getByRole("button", { name: "Zapisz układ" }).click();
    await expect(page.getByText("Zapisano układ sali")).toBeVisible();
    const saved = await (await request.get(api("/seating"), { headers: auth })).json();
    const stol = saved.tables.find((t: { name: string }) => t.name === "Stół 1");
    expect(stol.pos_x).not.toBeNull();
    expect(stol.rotation).toBe(45);

    // Parkiet na planie sali.
    await page.getByRole("button", { name: "Wymiary i elementy sali" }).click();
    await page.getByRole("button", { name: "Dodaj na plan" }).click();
    await page.getByRole("button", { name: "Zapisz salę" }).click();
    await expect(page.getByText("Zapisano salę")).toBeVisible();
    await expect(page.getByRole("img", { name: /Parkiet/ })).toBeVisible();

    // Numery miejsc: rodzina obok siebie.
    await page.getByRole("button", { name: "Ponumeruj miejsca" }).click();
    await expect(page.getByText(/^Ponumerowano miejsca/)).toBeVisible();
    const card = page.getByRole("region", { name: "Stół 1" });
    await expect(card).toContainText("1.Anna");
    await expect(card).toContainText("3.Zosia");
    // Po przewinięciu podnawigacja chowa się pod przyklejonym nagłówkiem — axe liczy to jako
    // zbyt mały cel (fałszywy alarm target-size); sprawdzamy stronę od góry.
    await page.evaluate(() => window.scrollTo(0, 0));
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

    await page.goto(`/w/${w.id}/druk/sala`);
    await expect(page.getByRole("img", { name: "Plan sali 20 na 12 m" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "3 / 8" })).toBeVisible();
    // Kolor przewodni ze strony dla gości także na winietkach.
    await request.put(api("/guest-info"), {
      headers: { ...auth, "If-Match": '"0"' },
      data: { welcome: "Witajcie!", theme: "classic", accent: "sage", published: false },
    });
    await page.goto(`/w/${w.id}/druk/winietki`);
    await expect(page.getByText("Stół 1, miejsce 2")).toBeVisible();
    await expect(page.locator(".place-cards")).toHaveClass(/print-accented/);
    await expectAccessible(page);
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Kreator nowego wesela: termin, ceremonia, budżet i goście → plan zadań i podział budżetu", async ({ page, request }) => {
  test.skip(!["390-light", "390-dark", "1280-light", "1280-dark"].includes(test.info().project.name), "telefon i komputer");
  test.setTimeout(90_000);
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const name = `Kreator ${tag()}`;
  let weddingId = "";
  try {
    await openDemoWedding(page);
    await page.goto("/?wybierz=1");
    await page.getByRole("button", { name: "Nowe wesele" }).click();
    const sheet = page.getByRole("dialog", { name: "Nowe wesele" });
    await expect(sheet.getByText("Krok 1 z 4")).toBeVisible();
    // Bez nazwy nie przejdziemy dalej.
    await sheet.getByRole("button", { name: "Dalej" }).click();
    await expect(sheet.getByText("Wpisz nazwę, np. Anna i Michał.")).toBeVisible();
    await sheet.getByLabel("Nazwa wesela").fill(name);
    await sheet.getByRole("button", { name: /Albo planowany miesiąc/ }).click();
    await page.getByRole("option").nth(12).click();
    await expectAccessible(page);
    await sheet.getByRole("button", { name: "Dalej" }).click();

    await expect(sheet.getByText("Krok 2 z 4")).toBeVisible();
    await sheet.locator(".wp-segmented__option", { hasText: "Cywilny" }).click();
    await expect(sheet.getByText("Formalności w urzędzie stanu cywilnego.")).toBeVisible();
    await sheet.getByRole("button", { name: "Dalej" }).click();

    await expect(sheet.getByText("Krok 3 z 4")).toBeVisible();
    await sheet.getByLabel("Planowana liczba gości (opcjonalnie)").fill("abc");
    await sheet.getByLabel("Budżet na całe wesele (opcjonalnie)").fill("60 000");
    await sheet.getByRole("button", { name: "Dalej" }).click();
    await expect(sheet.getByText("Wpisz liczbę od 1 do 2000.")).toBeVisible();
    await sheet.getByLabel("Planowana liczba gości (opcjonalnie)").fill("90");
    await sheet.getByText("Rodzice Panny Młodej").click();
    await sheet.getByRole("button", { name: "Dalej" }).click();

    await expect(sheet.getByText("Krok 4 z 4")).toBeVisible();
    await expect(sheet).toContainText(name);
    await expect(sheet).toContainText("Cywilny");
    await expect(sheet).toContainText(/60\s000 zł/);
    await expect(sheet).toContainText("rodzice Panny Młodej");
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);
    await sheet.getByRole("button", { name: "Utwórz wesele" }).click();
    await expect(page.getByText(/^Gotowe: plan zadań i budżet podzielony na \d+ kategori/)).toBeVisible();
    await expect(page).toHaveURL(/\/w\/[0-9a-f-]+/);
    weddingId = new URL(page.url()).pathname.split("/")[2]!;

    const w = await (await request.get(`/api/v1/weddings/${weddingId}`, { headers: auth })).json();
    expect(w.ceremony_type).toBe("civil");
    expect(w.guest_count_planned).toBe(90);
    expect(w.planned_month).not.toBeNull();
    const tasks = await (await request.get(`/api/v1/weddings/${weddingId}/tasks?limit=200`, { headers: auth })).json();
    expect(tasks.items.length).toBeGreaterThan(20);
    const cats = await (await request.get(`/api/v1/weddings/${weddingId}/budget/categories`, { headers: auth })).json();
    expect(cats.some((c: { planned: { amount: string } }) => Number(c.planned.amount) > 0)).toBe(true);
    const funders = await (await request.get(`/api/v1/weddings/${weddingId}/funders`, { headers: auth })).json();
    expect(funders.funders.map((f: { name: string }) => f.name)).toEqual(["Rodzice Panny Młodej"]);
  } finally {
    if (weddingId) await request.delete(`/api/v1/weddings/${weddingId}`, { headers: auth });
  }
});

test("Dzień ślubu bez sieci: przesunięcie w kolejce, wysyłka po powrocie sieci, konflikt", async ({ page, context, request }) => {
  test.skip(!["390-light", "1280-dark"].includes(test.info().project.name), "jeden telefon, jeden komputer");
  test.setTimeout(90_000);
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", {
      headers: auth,
      data: { name: `Test kolejki ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" },
    })
  ).json();
  const api = (path: string) => `/api/v1/weddings/${w.id}${path}`;
  type Item = { id: string; title: string; starts_at: string };
  const schedule = async () => (await (await request.get(api("/schedule"), { headers: auth })).json()) as Item[];
  try {
    await request.post(api("/schedule/from-template"), { headers: auth, data: { day: "2028-06-17", ceremony_time: "15:00", dry_run: false } });
    const before = await schedule();
    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/dzien`);
    await page.getByRole("button", { name: /Tryb dnia ślubu/ }).click();
    await expect(page.getByRole("heading", { name: "Przesuń ten i wszystkie późniejsze" })).toBeVisible();

    // 1) Bez sieci: przesunięcie do kolejki, po powrocie sieci wysyłka automatyczna.
    await context.setOffline(true);
    await expect(page.getByRole("heading", { name: /^Przesuń bez sieci/ })).toBeVisible();
    await page.getByRole("button", { name: "+15 min" }).click();
    await expect(page.getByText(/i późniejsze: \+15 min/)).toBeVisible();
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);
    expect(await page.evaluate((id) => localStorage.getItem(`wp-day-queue:${id}`), w.id as string)).toContain('"minutes":15');
    await context.setOffline(false);
    await expect(page.getByText("Wysłano 1 przesunięcie zrobione bez sieci")).toBeVisible({ timeout: 15_000 });
    const after = await schedule();
    const delta = (new Date(after[0]!.starts_at).getTime() - new Date(before[0]!.starts_at).getTime()) / 60_000;
    expect(delta).toBe(15); // pierwszy punkt programu to „za chwilę” — przesunięty wraz z resztą
    expect(await page.evaluate((id) => localStorage.getItem(`wp-day-queue:${id}`), w.id as string)).toBeNull();

    // 2) Konflikt: bez sieci +15, a w tym czasie ktoś inny przesuwa program o 30 min.
    await context.setOffline(true);
    await page.getByRole("button", { name: "+15 min" }).click();
    await expect(page.getByText(/i późniejsze: \+15 min/)).toBeVisible();
    const current = await schedule();
    await request.post(api("/schedule/shift"), { headers: auth, data: { from_item_id: current[0]!.id, minutes: 30, dry_run: false } });
    await context.setOffline(false);
    await expect(page.getByText("Program zmienił się w międzyczasie")).toBeVisible({ timeout: 15_000 });
    await page.getByRole("button", { name: "Odrzuć" }).click();
    await expect(page.getByText("Program zmienił się w międzyczasie")).toHaveCount(0);
    const final = await schedule();
    // Na serwerze tylko przesunięcie „innej osoby” (+30), odrzucone +15 nie poszło.
    expect((new Date(final[0]!.starts_at).getTime() - new Date(current[0]!.starts_at).getTime()) / 60_000).toBe(30);
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Zobacz jak gość: podgląd strony z linku RSVP z fikcyjną rodziną", async ({ page, request }) => {
  test.skip(!["390-light", "390-dark", "1280-light"].includes(test.info().project.name), "telefon i komputer");
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", { headers: auth, data: { name: `Podgląd gościa ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" } })
  ).json();
  try {
    await request.post(`/api/v1/weddings/${w.id}/events`, { headers: auth, data: { kind: "reception", name: "Przyjęcie", address: "Dworek, ul. Lipowa 1" } });
    await request.put(`/api/v1/weddings/${w.id}/guest-info`, {
      headers: { ...auth, "If-Match": '"0"' },
      data: { welcome: "Witajcie!", theme: "garden", accent: "rose", published: false },
    });
    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/strona-goscia`);
    await page.getByRole("link", { name: "Zobacz jak gość" }).click();
    await expect(page.getByRole("heading", { name: "Przykładowa rodzina", level: 1 })).toBeVisible();
    await expect(page.getByText("Informacje dla gości są jeszcze nieopublikowane")).toBeVisible();
    await expect(page.getByText("Witajcie!")).toBeVisible();
    await expect(page.locator(".guest-preview-page")).toHaveAttribute("data-guest-theme", "garden");
    await expect(page.getByRole("button", { name: "Dodaj osobę towarzyszącą" })).toHaveCount(0);
    await page.getByRole("button", { name: /^Wyślij/ }).click();
    await expect(page.getByText(/Zaznaczcie odpowiedź|To podgląd/)).toBeVisible();
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Goście: lista do Excela (CSV) bez uwag dietetycznych i z nimi", async ({ page }) => {
  test.skip(!["390-light", "1280-dark"].includes(test.info().project.name), "jeden telefon, jeden komputer");
  await openDemoWedding(page);
  await tab(page, "Goście").click();
  // Rzadsze działania są w rozwijanym menu „Więcej działań”.
  await page.getByText("Więcej działań", { exact: true }).click();
  await page.getByRole("button", { name: "Pobierz do Excela (CSV)" }).click();
  const dialog = page.getByRole("alertdialog", { name: "Lista gości do Excela" }).or(page.getByRole("dialog", { name: "Lista gości do Excela" }));
  await expectAccessible(page);
  let download = page.waitForEvent("download");
  await dialog.getByRole("button", { name: "Pobierz plik" }).click();
  let file = await download;
  expect(file.suggestedFilename()).toBe("goscie.csv");
  const plain = (await import("node:fs")).readFileSync((await file.path())!, "utf8");
  expect(plain.charCodeAt(0)).toBe(0xfeff);
  expect(plain).toContain("Zaproszenie;Imię;Nazwisko;Wiek;Przyjęcie;Dieta;Stół");
  expect(plain).toContain("Marta");
  expect(plain).not.toContain("Uwagi dla kuchni");

  await page.getByRole("button", { name: "Pobierz do Excela (CSV)" }).click();
  await dialog.getByText("Dołącz uwagi dla kuchni").click();
  await expect(dialog.getByText("Uwagi mogą dotyczyć zdrowia.")).toBeVisible();
  download = page.waitForEvent("download");
  await dialog.getByRole("button", { name: "Pobierz plik" }).click();
  file = await download;
  const withNotes = (await import("node:fs")).readFileSync((await file.path())!, "utf8");
  expect(withNotes).toContain("Uwagi dla kuchni");
});

test("Strona gościa po angielsku: przełącznik języka, zapamiętany wybór, przeglądarka w innym języku", async ({ browser, request }) => {
  test.skip(!["390-light", "1280-dark"].includes(test.info().project.name), "jeden telefon, jeden komputer");
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", { headers: auth, data: { name: `Język gościa ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" } })
  ).json();
  const api = (path: string) => `/api/v1/weddings/${w.id}${path}`;
  try {
    await request.post(api("/events"), { headers: auth, data: { kind: "reception", name: "Przyjęcie", starts_at: "2028-06-17T15:00:00+02:00" } });
    const h = await (await request.post(api("/households"), { headers: auth, data: { name: "Smith family", rsvp_deadline: "2028-05-01" } })).json();
    await request.post(api(`/households/${h.id}/guests`), { headers: auth, data: { first_name: "John" } });
    const token = (await (await request.post(api(`/households/${h.id}/rsvp-link`), { headers: auth })).json()).token as string;

    // Przeglądarka po polsku: strona po polsku, przełączenie na angielski zostaje po przeładowaniu.
    const pl = await browser.newContext({ locale: "pl-PL", timezoneId: "Europe/Warsaw", colorScheme: test.info().project.name.endsWith("dark") ? "dark" : "light" });
    const g = await pl.newPage();
    await g.goto(`/rsvp/${token}`);
    await expect(g.getByText("Prosimy o odpowiedź do 1 maja 2028.")).toBeVisible();
    await g.locator(".wp-segmented__option", { hasText: "English" }).click();
    await expect(g.getByText("Please reply by 1 May 2028.")).toBeVisible();
    await expect(g.getByText("17 June 2028, at 15:00")).toBeVisible();
    // Plik kalendarza z wydarzeniem (tworzony w przeglądarce gościa).
    const ics = g.waitForEvent("download");
    await g.getByRole("button", { name: "Add to calendar" }).click();
    const file = await ics;
    expect(file.suggestedFilename()).toBe("wesele.ics");
    const body = (await import("node:fs")).readFileSync((await file.path())!, "utf8");
    expect(body).toContain("DTSTART:20280617T130000Z");
    expect(body).toContain("SUMMARY:Przyjęcie — Język gościa");
    await expect(g.locator("main")).toHaveAttribute("lang", "en");
    await expectAccessible(g);
    await g.reload();
    await expect(g.getByText("Will you come?")).toBeVisible();
    await pl.close();

    // Zaproszenie oznaczone przez parę jako angielskie: po angielsku także w polskiej przeglądarce.
    const h2 = await (await request.post(api("/households"), { headers: auth, data: { name: "Brown family", language: "en" } })).json();
    await request.post(api(`/households/${h2.id}/guests`), { headers: auth, data: { first_name: "Mary" } });
    const token2 = (await (await request.post(api(`/households/${h2.id}/rsvp-link`), { headers: auth })).json()).token as string;
    const pl2 = await browser.newContext({ locale: "pl-PL", timezoneId: "Europe/Warsaw" });
    const g2 = await pl2.newPage();
    await g2.goto(`/rsvp/${token2}`);
    await expect(g2.getByText("Will you come?")).toBeVisible();
    await pl2.close();

    // Przeglądarka w innym języku: od razu angielski.
    const en = await browser.newContext({ locale: "en-US", timezoneId: "Europe/Warsaw" });
    const e = await en.newPage();
    await e.goto(`/rsvp/${token}`);
    await expect(e.getByRole("button", { name: /^Send/ })).toBeVisible();
    await en.close();
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Dziś: wygląd odliczania w dniach, tygodniach i miesiącach (zapamiętany)", async ({ page, request }) => {
  test.skip(!["390-light", "390-dark", "1280-light"].includes(test.info().project.name), "telefon i komputer");
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", { headers: auth, data: { name: `Odliczanie ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" } })
  ).json();
  try {
    await openDemoWedding(page);
    await page.goto(`/w/${w.id}`);
    const hero = page.getByRole("region", { name: "Odliczanie do ślubu" });
    await expect(hero).toContainText("dni do ślubu");
    await hero.getByRole("button", { name: "Pokaż w tygodniach" }).click();
    await expect(hero).toContainText("tygodni");
    await hero.getByRole("button", { name: "Pokaż w miesiącach" }).click();
    await expect(hero).toContainText("miesięcy");
    await expectAccessible(page);
    await page.reload();
    await expect(hero).toContainText("miesięcy");
    await hero.getByRole("button", { name: "Pokaż w dniach" }).click();
    await expect(hero).toContainText("dni do ślubu");
    await expectNoHorizontalScroll(page);
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Budżet: pozycje i płatności do Excela (CSV)", async ({ page }) => {
  test.skip(!["390-light", "1280-dark"].includes(test.info().project.name), "jeden telefon, jeden komputer");
  await openDemoWedding(page);
  await tab(page, "Budżet").click();
  await page.getByRole("button", { name: "Pobierz do Excela (CSV)" }).click();
  const dialog = page.getByRole("alertdialog", { name: "Budżet do Excela" }).or(page.getByRole("dialog", { name: "Budżet do Excela" }));
  await expectAccessible(page);
  let download = page.waitForEvent("download");
  await dialog.getByRole("button", { name: "Pobierz plik" }).click();
  let file = await download;
  expect(file.suggestedFilename()).toBe("budzet.csv");
  const fs = await import("node:fs");
  const items = fs.readFileSync((await file.path())!, "utf8");
  expect(items.charCodeAt(0)).toBe(0xfeff);
  expect(items).toContain("Kategoria;Pozycja;Koszt");
  expect(items).toContain("DJ");

  await page.getByRole("button", { name: "Pobierz do Excela (CSV)" }).click();
  await dialog.getByText("Płatności", { exact: true }).click();
  download = page.waitForEvent("download");
  await dialog.getByRole("button", { name: "Pobierz plik" }).click();
  file = await download;
  expect(file.suggestedFilename()).toBe("budzet-platnosci.csv");
  expect(fs.readFileSync((await file.path())!, "utf8")).toContain("Pozycja;Kategoria;Rodzaj;Kwota (zł);Termin;Status");
});

test("Frekwencja: prognoza, minimum sali, lista rezerwowa i zaproszenie", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  expect(login.ok()).toBeTruthy();
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const created = await request.post("/api/v1/weddings", {
    headers: auth,
    data: { name: `Test frekwencji ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil", guest_count_planned: 40 },
  });
  expect(created.ok()).toBeTruthy();
  const weddingId = (await created.json()).id as string;
  const url = `/api/v1/weddings/${weddingId}`;
  try {
    const event = await (await request.post(`${url}/events`, { headers: auth, data: { kind: "reception", name: "Przyjęcie" } })).json();
    await request.post(`${url}/events`, { headers: auth, data: { kind: "after_party", name: "Poprawiny" } });
    for (const [name, status] of [
      ["Nowakowie", "attending"],
      ["Kowalscy", null],
    ] as const) {
      const h = await (await request.post(`${url}/households`, { headers: auth, data: { name } })).json();
      for (const first_name of ["Jan", "Ewa"]) {
        const g = await (await request.post(`${url}/households/${h.id}/guests`, { headers: auth, data: { first_name } })).json();
        if (status) await request.put(`${url}/guests/${g.id}/attendance/${event.id}`, { headers: auth, data: { status } });
      }
    }
    const vendor = await (await request.post(`${url}/vendors`, { headers: auth, data: { name: "Sala testowa", category: "venue" } })).json();
    const offer = await (
      await request.post(`${url}/offers`, {
        headers: auth,
        data: { vendor_id: vendor.id, title: "Pakiet", min_guests: 30, components: [{ label: "Menu", kind: "per_guest", amount: "300" }] },
      })
    ).json();
    expect((await request.post(`${url}/offers/${offer.id}/select`, { headers: auth, data: {} })).ok()).toBeTruthy();

    await openDemoWedding(page);
    await page.goto(`/w/${weddingId}/frekwencja`);
    await expect(page.getByRole("heading", { name: "Frekwencja", level: 1 })).toBeVisible();
    await expect(page.getByText("ok. 4 osoby")).toBeVisible();
    await expect(page.getByText(/brakuje 26 osób/)).toBeVisible();
    // Poprawiny osobno: nikt jeszcze nie odpowiedział, 4 osoby · 85%.
    await expect(page.getByRole("heading", { name: "Prognoza: Poprawiny" })).toBeVisible();
    await expect(page.getByText("ok. 3 osoby")).toBeVisible();
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

    await page.getByRole("button", { name: "Dodaj osobę" }).click();
    const add = page.getByRole("dialog", { name: "Nowa osoba na liście rezerwowej" });
    await add.getByLabel("Kogo zaprosicie").fill("Kuzyn Marek z żoną");
    await add.getByLabel("Ile osób").fill("2");
    await add.getByRole("button", { name: "Dodaj do listy" }).click();
    await expect(page.getByText("Dodano do listy rezerwowej: Kuzyn Marek z żoną")).toBeVisible();
    await expect(page.getByText("Można zaprosić")).toBeVisible();

    await page.getByRole("button", { name: "Zaproś", exact: true }).click();
    const invite = page.getByRole("dialog", { name: "Zaproś: Kuzyn Marek z żoną" });
    await invite.getByRole("textbox", { name: "Imię" }).first().fill("Marek");
    await invite.getByRole("textbox", { name: "Imię" }).nth(1).fill("Iza");
    await expectAccessible(page);
    await invite.getByRole("button", { name: "Zaproś na wesele" }).click();
    await expect(page.getByText(/Kuzyn Marek z żoną — dopisani do listy gości/)).toBeVisible();
    await expect(page.getByText("Bez odpowiedzi: 4")).toBeVisible();
    await expect(page.getByText("Zaproszeni z listy rezerwowej (1)")).toBeVisible();
  } finally {
    await request.delete(`/api/v1/weddings/${weddingId}`, { headers: auth });
  }
});

test("Usługodawca: informacje od pary, wersja programu i potwierdzenie", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  expect(login.ok()).toBeTruthy();
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const created = await request.post("/api/v1/weddings", {
    headers: auth,
    data: { name: `Test wersji programu ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" },
  });
  expect(created.ok()).toBeTruthy();
  const weddingId = (await created.json()).id as string;
  const url = `/api/v1/weddings/${weddingId}`;
  try {
    const band = await (await request.post(`${url}/vendors`, { headers: auth, data: { name: "Zespół Testowy", category: "band" } })).json();
    const item = await request.post(`${url}/schedule`, {
      headers: auth,
      data: { title: "Pierwszy taniec", starts_at: "2028-06-17T21:00:00+02:00", vendor_id: band.id },
    });
    expect(item.ok()).toBeTruthy();
    const token = (await (await request.post(`${url}/vendors/${band.id}/day-link`, { headers: auth })).json()).token as string;

    await openDemoWedding(page);
    await page.goto(`/w/${weddingId}/uslugodawcy/${band.id}`);
    await page.getByLabel("Utwory obowiązkowe").fill("Pierwszy taniec: Perfect");
    await page.getByLabel("Nie grać").fill("Disco polo");
    await page.getByRole("button", { name: "Zapisz informacje" }).click();
    await expect(page.getByText("Zapisano informacje dla usługodawcy")).toBeVisible();
    await expectAccessible(page);

    // Strona usługodawcy (bez logowania): informacje i potwierdzenie wersji.
    await page.goto(`/dzien/${token}`);
    await expect(page.getByRole("heading", { name: "Informacje od pary" })).toBeVisible();
    await expect(page.getByText("Disco polo")).toBeVisible();
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);
    await page.getByRole("button", { name: /Potwierdzam, że znam wersję \d+/ }).click();
    await expect(page.getByText(/Potwierdziliście wersję \d+ programu/)).toBeVisible();

    await page.goto(`/w/${weddingId}/dzien`);
    const summary = page.getByRole("region", { name: "Kto zna aktualny program" });
    await expect(summary.getByText("Wszyscy usługodawcy z linkiem potwierdzili aktualną wersję.")).toBeVisible();
    await expect(summary.getByText("Zespół Testowy")).toBeVisible();
  } finally {
    await request.delete(`/api/v1/weddings/${weddingId}`, { headers: auth });
  }
});

test("Kto płaci: sponsor, obiecana kwota, wpłata i płatność przypisana", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  expect(login.ok()).toBeTruthy();
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const created = await request.post("/api/v1/weddings", {
    headers: auth,
    data: { name: `Test sponsorów ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" },
  });
  expect(created.ok()).toBeTruthy();
  const weddingId = (await created.json()).id as string;
  const url = `/api/v1/weddings/${weddingId}`;
  try {
    const cats = await (await request.get(`${url}/budget/categories`, { headers: auth })).json();
    const item = await (
      await request.post(`${url}/budget/items`, {
        headers: auth,
        data: { name: "Sala", category_id: cats[0].id, planned: { amount: "40000", currency: "PLN" } },
      })
    ).json();
    const payment = await (
      await request.post(`${url}/budget/items/${item.id}/payments`, {
        headers: auth,
        data: { kind: "final", amount: { amount: "8000", currency: "PLN" }, due_date: "2028-06-01" },
      })
    ).json();

    await openDemoWedding(page);
    await page.goto(`/w/${weddingId}/sponsorzy`);
    await expect(page.getByRole("heading", { name: "Kto płaci", level: 1 })).toBeVisible();
    await page.getByRole("button", { name: "Dodaj sponsora" }).click();
    const sheet = page.getByRole("dialog", { name: "Nowy sponsor" });
    await sheet.getByLabel("Kto").fill("Rodzice Panny Młodej");
    await sheet.getByLabel("Obiecana kwota (opcjonalnie)").fill("20000");
    await sheet.getByRole("button", { name: "Dodaj sponsora" }).click();
    await expect(page.getByText("Dodano: Rodzice Panny Młodej")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Rodzice Panny Młodej" })).toBeVisible();

    // Para przypisuje płatność rodzicom (jak w formularzu płatności: pole „Kto płaci”).
    const funders = await (await request.get(`${url}/funders`, { headers: auth })).json();
    const moved = await request.patch(`${url}/payments/${payment.id}`, {
      headers: { ...auth, "If-Match": `"${payment.version}"` },
      data: { funder_id: funders.funders[0].id },
    });
    expect(moved.ok()).toBeTruthy();
    await page.reload();

    await page.getByRole("button", { name: "Płatności i wpłaty" }).click();
    await expect(page.getByText("Sala · Dopłata")).toBeVisible();
    await page.getByLabel("Nowa wpłata od sponsora").fill("3000");
    await page.getByLabel("Notatka (opcjonalnie)").fill("Przelew na konto");
    await page.getByRole("button", { name: "Zapisz wpłatę" }).click();
    await expect(page.getByText("Zapisano wpłatę")).toBeVisible();
    await expect(page.getByText(/Do rozpisania: 9\s000/)).toBeVisible();
    await expect(page.getByText("15% obiecanej kwoty już dotarło")).toBeVisible();
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

  } finally {
    await request.delete(`/api/v1/weddings/${weddingId}`, { headers: auth });
  }
});

test("Dokumenty do ślubu: okna ważności, data wydania i ostrzeżenie", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  expect(login.ok()).toBeTruthy();
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const created = await request.post("/api/v1/weddings", {
    headers: auth,
    data: { name: `Test dokumentów ${tag()}`, wedding_date: "2028-07-01", ceremony_type: "concordat" },
  });
  expect(created.ok()).toBeTruthy();
  const weddingId = (await created.json()).id as string;
  try {
    await openDemoWedding(page);
    await page.goto(`/w/${weddingId}/formalnosci`);
    await expect(page.getByRole("heading", { name: "Dokumenty do ślubu", level: 1 })).toBeVisible();
    const usc = page.getByRole("listitem").filter({ hasText: "Zaświadczenie z USC do ślubu kościelnego" });
    await expect(usc.getByText("Najwcześniej od 1 stycznia 2028")).toBeVisible();
    await expect(usc.getByRole("link", { name: /gov\.pl/ })).toBeVisible();
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

    // Świadectwo chrztu wydane za wcześnie: ostrzeżenie, że straci ważność przed ślubem.
    const baptism = page.getByRole("listitem").filter({ hasText: "Świadectwo chrztu do ślubu" });
    await baptism.getByRole("group", { name: "Data wydania" }).getByRole("spinbutton").first().click();
    await page.keyboard.type("15112027");
    await baptism.getByRole("button", { name: "Zapisz" }).click();
    await expect(baptism.getByText(/Straci ważność 15 maja 2028 — przed ślubem/)).toBeVisible();

    const protocol = page.getByRole("listitem").filter({ hasText: "Zgłoszenie w kancelarii parafialnej" });
    await protocol.getByText("Zrobione").click();
    await expect(protocol.getByText("Zrobione", { exact: true }).first()).toBeVisible();
    await expectAccessible(page);
  } finally {
    await request.delete(`/api/v1/weddings/${weddingId}`, { headers: auth });
  }
});

test("Budżet: podwyżka ceny w umowie i trzy warianty kosztu", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  expect(login.ok()).toBeTruthy();
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const created = await request.post("/api/v1/weddings", {
    headers: auth,
    data: { name: `Test waloryzacji ${tag()}`, wedding_date: "2028-07-01", ceremony_type: "civil" },
  });
  expect(created.ok()).toBeTruthy();
  const weddingId = (await created.json()).id as string;
  const url = `/api/v1/weddings/${weddingId}`;
  try {
    const cats = await (await request.get(`${url}/budget/categories`, { headers: auth })).json();
    await request.post(`${url}/budget/items`, {
      headers: auth,
      data: { name: "Sala testowa", category_id: cats[0].id, planned: { amount: "40000", currency: "PLN" }, indexation: "none" },
    });

    await openDemoWedding(page);
    await page.goto(`/w/${weddingId}/budzet`);
    await expect(page.getByText("Podwyżka ceny w umowie", { exact: false }).first()).toBeVisible();
    await page.getByRole("button", { name: /^Sala testowa/ }).click();
    const sheet = page.getByRole("dialog", { name: "Wydatek" });
    await sheet.getByText("Podwyżka ceny w umowie (waloryzacja)").click();
    await sheet.getByRole("button", { name: /Czy umowa pozwala podnieść cenę/ }).click();
    await page.getByRole("option", { name: "Podwyżka z limitem (np. max 5%)" }).click();
    await sheet.getByLabel("Maksymalna podwyżka łącznie (%)").fill("5");
    await expectAccessible(page);
    await sheet.getByRole("button", { name: "Zapisz" }).first().click();
    await expect(page.getByRole("heading", { name: "Podwyżki cen w umowach" })).toBeVisible();
    const worst = page.locator(".stat", { hasText: "W najgorszym razie" });
    await expect(worst).toContainText(/42\s000\szł/); // 40 000 zł + limit 5%
    await expect(page.getByText(/z limitem 5%/)).toBeVisible();
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);
    // Założenia zapisują się na weselu: Dziś liczy tak samo jak Budżet.
    await page.getByText("Założenia", { exact: true }).click();
    await page.getByRole("radiogroup", { name: "Najgorszy przypadek: inflacja rocznie" }).getByText("15%").click();
    await expect(page.getByText("Zapisano założenia", { exact: false })).toBeVisible();
    // Ekran Dziś: kafelek kosztu podpowiada najgorszy wariant i prowadzi do podwyżek w budżecie.
    await page.goto(`/w/${weddingId}`);
    await page.getByRole("link", { name: /z podwyżkami cen do 42\s000\szł.*15% rocznie/ }).click();
    await expect(page.getByRole("heading", { name: "Podwyżki cen w umowach" })).toBeVisible();
  } finally {
    await request.delete(`/api/v1/weddings/${weddingId}`, { headers: auth });
  }
});

test("Zaproszenia: objazdy po miejscowościach, plan i wręczone", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  expect(login.ok()).toBeTruthy();
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const created = await request.post("/api/v1/weddings", {
    headers: auth,
    data: { name: `Test zaproszeń ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" },
  });
  expect(created.ok()).toBeTruthy();
  const weddingId = (await created.json()).id as string;
  const url = `/api/v1/weddings/${weddingId}`;
  try {
    for (const [name, place] of [
      ["Babcia Zosia", "Tarnów"],
      ["Wujostwo Nowak", "Tarnów"],
      ["Kuzyni", "Kraków"],
    ]) {
      await request.post(`${url}/households`, { headers: auth, data: { name, delivery_method: "in_person", delivery_place: place } });
    }

    await openDemoWedding(page);
    await page.goto(`/w/${weddingId}/zaproszenia`);
    await expect(page.getByRole("heading", { name: "Zaproszenia", level: 1 })).toBeVisible();
    const tarnow = page.getByRole("region", { name: "Tarnów" });
    await expect(tarnow.getByText("Do wręczenia: 2")).toBeVisible();
    await expect(page.locator(".stat", { hasText: "Wręczone osobiście" })).toContainText("0 z 3");
    // Do drukarni: 3 rodziny + zapas co najmniej 3.
    const order = page.locator(".stat", { hasText: "Do zamówienia w drukarni" });
    await expect(order).toContainText("6");
    await expect(order).toContainText("3 zaproszenia dla rodzin + 3 zapasu");
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

    await tarnow.getByText("Babcia Zosia").click();
    await tarnow.getByText(/^Zaplanuj objazd/).click();
    await tarnow.getByLabel("Kto wręcza (opcjonalnie)").fill("Ania i mama");
    await tarnow.getByRole("button", { name: "Zapisz plan" }).click();
    await expect(page.getByText("Zaplanowano objazd")).toBeVisible();
    await expect(tarnow.getByText(/wręcza: Ania i mama/)).toBeVisible();

    await tarnow.getByRole("button", { name: "Wręczone" }).first().click();
    await expect(page.getByText("Zaznaczono jako wręczone")).toBeVisible();
    await expect(page.locator(".stat", { hasText: "Wręczone osobiście" })).toContainText("1 z 3");
    // Wydruk na objazd: tylko niewręczone, pogrupowane po miejscowościach.
    await page.getByRole("link", { name: "Wydrukuj listę na objazd" }).click();
    await expect(page.getByRole("heading", { name: "Objazd z zaproszeniami", level: 1 })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Kraków" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "Babcia Zosia" })).toHaveCount(0);
    await page.goBack();
    // Po przewinięciu podzakładki chowają się pod przyklejonym nagłówkiem (axe uznaje je za zasłonięte).
    await page.evaluate(() => window.scrollTo(0, 0));
    await expectAccessible(page);
    // Lista gości: filtr „Do wręczenia” pokazuje tylko niewręczone zaproszenia osobiste.
    await page.goto(`/w/${weddingId}/goscie?filtr=do-wreczenia`);
    await expect(page.getByText("Kuzyni")).toBeVisible();
    await expect(page.getByText("Babcia Zosia")).toHaveCount(0);
  } finally {
    await request.delete(`/api/v1/weddings/${weddingId}`, { headers: auth });
  }
});

test("Transport i noclegi: kurs, pasażerowie, pokój i brakujący nocleg", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  expect(login.ok()).toBeTruthy();
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const created = await request.post("/api/v1/weddings", {
    headers: auth,
    data: { name: `Test transportu ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" },
  });
  expect(created.ok()).toBeTruthy();
  const weddingId = (await created.json()).id as string;
  const url = `/api/v1/weddings/${weddingId}`;
  try {
    const h = await (await request.post(`${url}/households`, { headers: auth, data: { name: "Rodzina z Gdańska" } })).json();
    for (const first_name of ["Ala", "Ola"]) {
      await request.post(`${url}/households/${h.id}/guests`, {
        headers: auth,
        data: { first_name, needs_transport: true, needs_accommodation: true },
      });
    }

    await openDemoWedding(page);
    await page.goto(`/w/${weddingId}/logistyka`);
    await expect(page.getByRole("heading", { name: "Transport i noclegi", level: 1 })).toBeVisible();
    await expect(page.getByText(/bez kursu: 2 osoby/)).toBeVisible();

    await page.getByRole("button", { name: "Dodaj kurs" }).click();
    const run = page.getByRole("dialog", { name: "Nowy kurs" });
    await run.getByLabel("Nazwa kursu").fill("Autokar: kościół → sala");
    await run.getByLabel("Liczba miejsc").fill("1");
    await run.getByRole("button", { name: "Dodaj kurs" }).click();
    await expect(page.getByText("Dodano kurs")).toBeVisible();

    await page.getByRole("button", { name: "Pasażerowie" }).click();
    const people = page.getByRole("dialog", { name: /Pasażerowie/ });
    for (const name of ["Ala", "Ola"]) {
      await people.getByText(name, { exact: true }).click();
      await expect(people.getByRole("checkbox", { name: new RegExp(`^${name}`) })).toBeChecked();
    }
    await expectAccessible(page);
    await people.getByRole("button", { name: "Zapisz (2)" }).click();
    await expect(page.getByText("Przepełniony o 1 (2/1)")).toBeVisible();
    await expect(page.getByText(/bez kursu/)).toHaveCount(0);

    await page.getByRole("button", { name: "Dodaj pokój" }).click();
    const room = page.getByRole("dialog", { name: "Nowy pokój" });
    await room.getByLabel("Obiekt").fill("Hotel przy sali");
    await room.getByLabel("Pokój", { exact: true }).fill("12");
    await room.getByRole("button", { name: "Dodaj pokój" }).click();
    await expect(page.getByText("Dodano pokój")).toBeVisible();
    await page.getByRole("button", { name: "Kto śpi" }).click();
    const sleep = page.getByRole("dialog", { name: /Kto śpi/ });
    await sleep.getByText("Ala", { exact: true }).click();
    await expect(sleep.getByRole("checkbox", { name: /^Ala/ })).toBeChecked();
    await sleep.getByRole("button", { name: "Zapisz (1)" }).click();
    await expect(page.getByText(/bez pokoju: 1 osoba/)).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);
    // Wydruk list pasażerów.
    await page.getByRole("link", { name: "Listy pasażerów" }).click();
    await expect(page.getByRole("heading", { name: "Listy pasażerów", level: 1 })).toBeVisible();
    await expect(page.getByRole("cell", { name: "Ola" })).toBeVisible();
    // Ekran Dzień: kursy z liczbą osób (widzi je też koordynator dnia).
    await page.goto(`/w/${weddingId}/dzien`);
    const runs = page.getByRole("region", { name: "Kursy" });
    await expect(runs.getByText("Autokar: kościół → sala")).toBeVisible();
    await expect(runs.getByText("2 osoby / 1")).toBeVisible();
  } finally {
    await request.delete(`/api/v1/weddings/${weddingId}`, { headers: auth });
  }
});

test("Po weselu: zdjęcia po terminie, przypomnienie i zmiana nazwiska", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  expect(login.ok()).toBeTruthy();
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  // Data ślubu nie może być w przeszłości, ale termin oddania zdjęć już minął (2026-08-31).
  const created = await request.post("/api/v1/weddings", {
    headers: auth,
    data: { name: `Test po weselu ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" },
  });
  expect(created.ok()).toBeTruthy();
  const weddingId = (await created.json()).id as string;
  const url = `/api/v1/weddings/${weddingId}`;
  try {
    await request.post(`${url}/deliverables`, { headers: auth, data: { title: "Zdjęcia — galeria", due_on: "2026-08-31" } });
    await request.post(`${url}/vendors`, { headers: auth, data: { name: "Kamera Jan", category: "videographer", status: "booked" } });

    await openDemoWedding(page);
    await page.goto(`/w/${weddingId}/wiecej`);
    await page.getByRole("link", { name: /Po weselu/ }).click();
    await expect(page.getByRole("heading", { name: "Po weselu", level: 1 })).toBeVisible();
    await expect(page.getByText(/Spóźnienie: \d+ dni/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Kopiuj przypomnienie" })).toBeVisible();
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

    await page.getByRole("button", { name: "Odebrane" }).click();
    await expect(page.getByText("Zaznaczono jako odebrane")).toBeVisible();
    await expect(page.getByText(/^Odebrane \d/)).toBeVisible();

    // Podpowiedź z zarezerwowanego filmowca.
    await page.getByRole("button", { name: "Film — Kamera Jan" }).click();
    await expect(page.getByRole("heading", { name: "Film — Kamera Jan" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Film — Kamera Jan" })).toHaveCount(0);

    const bank = page.getByRole("listitem").filter({ hasText: "Bank i karty płatnicze" });
    await bank.getByText("Bank i karty płatnicze").click();
    await expect(bank.getByText("Zrobione", { exact: true })).toBeVisible();
    await expect(page.getByText(/zrobione 1 z 8/)).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await expectAccessible(page);
  } finally {
    await request.delete(`/api/v1/weddings/${weddingId}`, { headers: auth });
  }
});

test("Dziś: „Wymaga uwagi” zbiera ostrzeżenia i prowadzi do ekranu", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  expect(login.ok()).toBeTruthy();
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const created = await request.post("/api/v1/weddings", {
    headers: auth,
    data: { name: `Test uwagi ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" },
  });
  expect(created.ok()).toBeTruthy();
  const weddingId = (await created.json()).id as string;
  const url = `/api/v1/weddings/${weddingId}`;
  try {
    const run = (await (await request.post(`${url}/transport-runs`, { headers: auth, data: { name: "Bus z dworca", capacity: 1 } })).json()).runs[0];
    const h = await (await request.post(`${url}/households`, { headers: auth, data: { name: "Rodzina" } })).json();
    const ids: string[] = [];
    for (const first_name of ["A", "B"]) {
      ids.push((await (await request.post(`${url}/households/${h.id}/guests`, { headers: auth, data: { first_name } })).json()).id);
    }
    await request.put(`${url}/transport-runs/${run.id}/guests`, { headers: auth, data: { guest_ids: ids } });

    await openDemoWedding(page);
    await page.goto(`/w/${weddingId}`);
    const card = page.getByRole("region", { name: "Wymaga uwagi" });
    await expect(card.getByText("Kurs „Bus z dworca” jest przepełniony o 1 os.")).toBeVisible();
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);
    await card.getByRole("link", { name: /Bus z dworca/ }).click();
    await expect(page.getByRole("heading", { name: "Transport i noclegi", level: 1 })).toBeVisible();
  } finally {
    await request.delete(`/api/v1/weddings/${weddingId}`, { headers: auth });
  }
});

test("RSVP: gość zapisuje się na kurs autokaru udostępniony przez parę", async ({ page, request, browser }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  expect(login.ok()).toBeTruthy();
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const created = await request.post("/api/v1/weddings", {
    headers: auth,
    data: { name: `Test kursów RSVP ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" },
  });
  expect(created.ok()).toBeTruthy();
  const weddingId = (await created.json()).id as string;
  const url = `/api/v1/weddings/${weddingId}`;
  try {
    await request.post(`${url}/events`, { headers: auth, data: { kind: "reception", name: "Przyjęcie", starts_at: "2028-06-17T15:00:00+02:00" } });
    await request.post(`${url}/transport-runs`, {
      headers: auth,
      data: { name: "Autokar z dworca", capacity: 40, show_to_guests: true, departs_at: "2028-06-17T14:00:00+02:00" },
    });
    const h = await (await request.post(`${url}/households`, { headers: auth, data: { name: "Kowalscy" } })).json();
    await request.post(`${url}/households/${h.id}/guests`, { headers: auth, data: { first_name: "Jan" } });
    const token = (await (await request.post(`${url}/households/${h.id}/rsvp-link`, { headers: auth })).json()).token as string;

    const guest = await browser.newContext({ locale: "pl-PL", timezoneId: "Europe/Warsaw", colorScheme: test.info().project.name.endsWith("dark") ? "dark" : "light" });
    const g = await guest.newPage();
    await g.setViewportSize(page.viewportSize()!);
    await g.goto(`/rsvp/${token}`);
    // Rozkład przejazdów na stronie gościa (niezależnie od formularza).
    await expect(g.getByRole("heading", { name: "Przejazdy" })).toBeVisible();
    await expect(g.getByText(/14:00 Autokar z dworca/)).toBeVisible();
    const jan = g.locator(".wp-card", { has: g.getByRole("heading", { name: "Jan" }) });
    await jan.locator(".wp-segmented__option", { hasText: "Będę" }).first().click();
    await jan.getByText("Potrzebuję transportu").click();
    await expect(jan.getByText("Przejazd zorganizowany przez parę")).toBeVisible();
    await jan.getByText(/Autokar z dworca/).click();
    await expect(jan.getByRole("checkbox", { name: /Autokar z dworca/ })).toBeChecked();
    await expectAccessible(g);
    await expectNoHorizontalScroll(g);
    await g.getByRole("button", { name: /^Wyślij/ }).click();
    await expect(g.getByRole("heading", { name: "Dziękujemy!" })).toBeVisible();
    await guest.close();

    // Para widzi Jana na kursie.
    const o = await (await request.get(`${url}/logistics`, { headers: auth })).json();
    expect(o.runs[0].passengers.map((p: { name: string }) => p.name)).toEqual(["Jan"]);
  } finally {
    await request.delete(`/api/v1/weddings/${weddingId}`, { headers: auth });
  }
});

test("Dzień: lista „Co zabrać” — typowa lista, własna pozycja, odhaczanie", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  expect(login.ok()).toBeTruthy();
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const created = await request.post("/api/v1/weddings", {
    headers: auth,
    // Ślub dziś (czas polski): ekran Dziś prowadzi do programu dnia.
    data: { name: `Test co zabrać ${tag()}`, wedding_date: new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Warsaw" }), ceremony_type: "civil" },
  });
  expect(created.ok()).toBeTruthy();
  const weddingId = (await created.json()).id as string;
  try {
    await openDemoWedding(page);
    await page.goto(`/w/${weddingId}`);
    await page.getByRole("link", { name: /Dziś Wasz dzień!/ }).click();
    await expect(page.getByRole("heading", { name: "Harmonogram dnia" })).toBeVisible();
    const box = page.getByRole("region", { name: /Co zabrać/ });
    await box.getByRole("button", { name: "Wczytaj typową listę" }).click();
    await expect(page.getByText("Wczytano typową listę")).toBeVisible();
    await expect(box.getByText("Obrączki")).toBeVisible();
    await box.getByLabel("Co zabrać").fill("Głośnik bluetooth");
    await box.getByLabel("Kto bierze (opcjonalnie)").fill("Tomek");
    await box.getByRole("button", { name: "Dodaj", exact: true }).click();
    await expect(box.getByText("Głośnik bluetooth")).toBeVisible();
    await box.getByText("Obrączki").click();
    await expect(box.getByRole("checkbox", { name: /Obrączki/ })).toBeChecked();
    await expect(box.getByRole("heading", { name: /1 z 11/ })).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);
  } finally {
    await request.delete(`/api/v1/weddings/${weddingId}`, { headers: auth });
  }
});

test("Ustawienia: porównanie dat ślubu (święta, Wielki Post, zachód słońca)", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  expect(login.ok()).toBeTruthy();
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const created = await request.post("/api/v1/weddings", {
    headers: auth,
    data: { name: `Test dat ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "concordat", city: "Kraków" },
  });
  expect(created.ok()).toBeTruthy();
  const weddingId = (await created.json()).id as string;
  try {
    await openDemoWedding(page);
    await page.goto(`/w/${weddingId}/ustawienia`);
    const compare = page.getByRole("region", { name: "Porównajcie daty" });
    // Pierwszy termin to obecna data ślubu.
    const june = compare.getByRole("region", { name: /Termin 17 czerwca 2028/ });
    await expect(june.getByRole("heading", { name: /sobota, 17 czerwca 2028/ })).toBeVisible();
    await expect(june.getByText("Blisko święta", { exact: true })).toBeVisible();
    await expect(june.getByText(/Boże Ciało/)).toBeVisible();
    await expect(june.getByText(/Zachód słońca \d\d:\d\d/)).toBeVisible();
    await expect(compare.getByRole("button", { name: /Zachód słońca liczymy dla/ })).toContainText("Kraków");

    await compare.getByRole("group", { name: "Termin 2" }).getByRole("spinbutton").first().click();
    await page.keyboard.type("11032028");
    const lent = compare.getByRole("region", { name: /Termin 11 marca 2028/ });
    await expect(lent.getByText("Wielki Post").first()).toBeVisible();
    await expect(lent.getByText(/zapytajcie w parafii/)).toBeVisible();
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);
  } finally {
    await request.delete(`/api/v1/weddings/${weddingId}`, { headers: auth });
  }
});

test("Strona gościa: tryb czytelny (większy tekst) zapamiętany na urządzeniu", async ({ browser, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", { headers: auth, data: { name: `Czytelnie ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" } })
  ).json();
  const api = (path: string) => `/api/v1/weddings/${w.id}${path}`;
  try {
    await request.post(api("/events"), { headers: auth, data: { kind: "reception", name: "Przyjęcie", starts_at: "2028-06-17T15:00:00+02:00" } });
    const h = await (await request.post(api("/households"), { headers: auth, data: { name: "Babcia Zosia" } })).json();
    await request.post(api(`/households/${h.id}/guests`), { headers: auth, data: { first_name: "Zofia" } });
    const token = (await (await request.post(api(`/households/${h.id}/rsvp-link`), { headers: auth })).json()).token as string;

    const project = test.info().project;
    const ctx = await browser.newContext({ ...project.use, locale: "pl-PL", timezoneId: "Europe/Warsaw" });
    const g = await ctx.newPage();
    await g.goto(`/rsvp/${token}`);
    await expect(g.getByText("Czy będziesz?").first()).toBeVisible();
    const size = () => g.locator("main").evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
    expect(await size()).toBe(16);
    await g.locator(".wp-segmented__option", { hasText: "Większy" }).click();
    await expect(g.locator("main")).toHaveAttribute("data-readable", "true");
    expect(await size()).toBe(20);
    await expectAccessible(g);
    await expectNoHorizontalScroll(g);
    await g.reload();
    await expect(g.locator("main")).toHaveAttribute("data-readable", "true");
    await ctx.close();
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Muzyka: utwory na momenty, propozycja gościa w RSVP, lista na linku DJ-a", async ({ page, request, browser }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", { headers: auth, data: { name: `Muzyka ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" } })
  ).json();
  const api = (path: string) => `/api/v1/weddings/${w.id}${path}`;
  try {
    const h = await (await request.post(api("/households"), { headers: auth, data: { name: "Nowakowie" } })).json();
    await request.post(api(`/households/${h.id}/guests`), { headers: auth, data: { first_name: "Jan" } });
    const rsvp = (await (await request.post(api(`/households/${h.id}/rsvp-link`), { headers: auth })).json()).token as string;
    const dj = await (await request.post(api("/vendors"), { headers: auth, data: { name: "DJ Marek", category: "dj" } })).json();
    const djToken = (await (await request.post(api(`/vendors/${dj.id}/day-link`), { headers: auth })).json()).token as string;

    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/dzien`);
    await page.getByRole("navigation", { name: "Dzień ślubu" }).getByRole("link", { name: "Muzyka" }).click();
    await expect(page.getByRole("heading", { name: "Muzyka", level: 1 })).toBeVisible();
    await page.getByLabel("Tytuł").fill("Perfect");
    await page.getByLabel("Wykonawca (opcjonalnie)").fill("Ed Sheeran");
    await page.getByRole("button", { name: "Dodaj", exact: true }).click();
    await expect(page.getByRole("region", { name: "Pierwszy taniec" }).getByText("Perfect — Ed Sheeran")).toBeVisible();
    await page.getByText(/Goście mogą zaproponować utwór/).click();
    await expect(page.getByText("Goście mogą proponować utwory")).toBeVisible();
    // Po przewinięciu podzakładki chowają się pod przyklejonym nagłówkiem (axe uznaje je za zasłonięte).
    await page.evaluate(() => window.scrollTo(0, 0));
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

    // Gość proponuje utwór w formularzu RSVP.
    const ctx = await browser.newContext({ ...test.info().project.use, locale: "pl-PL", timezoneId: "Europe/Warsaw" });
    const g = await ctx.newPage();
    await g.goto(`/rsvp/${rsvp}`);
    const songs = g.getByRole("region", { name: "Piosenka na parkiet" });
    await songs.getByLabel("Tytuł utworu").fill("Jolka, Jolka");
    await songs.getByLabel("Wykonawca (opcjonalnie)").fill("Budka Suflera");
    await songs.getByRole("button", { name: "Zaproponuj" }).click();
    await expect(songs.getByText("Dziękujemy! Propozycja trafiła do pary.")).toBeVisible();
    await expect(songs.getByText("Jolka, Jolka — Budka Suflera")).toBeVisible();
    await expectAccessible(g);
    await ctx.close();

    // Para zatwierdza propozycję — trafia na listę DJ-a.
    await page.reload();
    const waiting = page.getByRole("region", { name: /Propozycje gości/ });
    await expect(waiting.getByText("od: Nowakowie")).toBeVisible();
    await waiting.getByRole("button", { name: "Dodaj do listy DJ-a: Jolka, Jolka" }).click();
    await expect(page.getByRole("region", { name: "Koniecznie zagrajcie" }).getByText("Jolka, Jolka — Budka Suflera")).toBeVisible();

    await page.goto(`/dzien/${djToken}`);
    const music = page.getByRole("region", { name: "Muzyka od pary" });
    await expect(music.getByText("Perfect — Ed Sheeran")).toBeVisible();
    await expect(music.getByText("Jolka, Jolka — Budka Suflera")).toBeVisible();
    await expectAccessible(page);
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Zdjęcia grupowe: typowe grupy, osoby z listy gości, kolejność i link fotografa", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", { headers: auth, data: { name: `Zdjęcia ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" } })
  ).json();
  const api = (path: string) => `/api/v1/weddings/${w.id}${path}`;
  try {
    const h = await (await request.post(api("/households"), { headers: auth, data: { name: "Dziadkowie" } })).json();
    await request.post(api(`/households/${h.id}/guests`), { headers: auth, data: { first_name: "Halina", last_name: "Kowalska" } });
    const photo = await (await request.post(api("/vendors"), { headers: auth, data: { name: "Foto Jan", category: "photographer" } })).json();
    const token = (await (await request.post(api(`/vendors/${photo.id}/day-link`), { headers: auth })).json()).token as string;

    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/zdjecia`);
    await expect(page.getByRole("heading", { name: "Zdjęcia grupowe", level: 1 })).toBeVisible();
    await page.getByRole("button", { name: "Wczytaj typowe grupy" }).click();
    await expect(page.getByText("Wczytano typowe grupy")).toBeVisible();
    await expect(page.getByText(/11 grup · ok\. 35 min/)).toBeVisible();

    await page.getByRole("button", { name: "Edytuj: Para Młoda z dziadkami" }).click();
    const sheet = page.getByRole("dialog", { name: "Para Młoda z dziadkami" });
    await sheet.getByText("Halina Kowalska").click();
    await expect(sheet.getByRole("checkbox", { name: /Halina Kowalska/ })).toBeChecked();
    await sheet.getByLabel("Osoby spoza listy gości (opcjonalnie)").fill("ksiądz");
    await expectAccessible(page);
    await sheet.getByRole("button", { name: "Zapisz" }).click();
    await expect(page.getByText("Zapisano grupę")).toBeVisible();
    await expect(page.getByText(/Halina Kowalska, ksiądz · 3 minuty/)).toBeVisible();

    await page.getByRole("button", { name: "Niżej: Para Młoda z dziadkami" }).click();
    await expect(page.locator(".photo-groups > li").nth(1)).toContainText("Para Młoda z dziadkami");
    await page.locator(".photo-groups > li").nth(1).getByText("Para Młoda z dziadkami").click();
    await expect(page.getByText(/zostało ok\. 32 min/)).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

    await page.goto(`/dzien/${token}`);
    const groups = page.getByRole("region", { name: "Zdjęcia grupowe" });
    await expect(groups.getByText(/Halina K\., ksiądz/)).toBeVisible();
    await expect(groups.getByText("Halina Kowalska")).toHaveCount(0);
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Fryzura i makijaż: liczone wstecz od godziny „gotowi”, godziny na linku fryzjerki", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", { headers: auth, data: { name: `Przygotowania ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" } })
  ).json();
  const api = (path: string) => `/api/v1/weddings/${w.id}${path}`;
  try {
    const hair = await (await request.post(api("/vendors"), { headers: auth, data: { name: "Fryzjerka Ola", category: "hairdresser" } })).json();
    const token = (await (await request.post(api(`/vendors/${hair.id}/day-link`), { headers: auth })).json()).token as string;

    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/dzien`);
    await page.getByRole("navigation", { name: "Dzień ślubu" }).getByRole("link", { name: "Fryzura i makijaż" }).click();
    await expect(page.getByRole("heading", { name: "Fryzura i makijaż", level: 1 })).toBeVisible();
    const add = page.getByRole("form", { name: "Nowa osoba na fotel" });
    for (const [name, hairMin, makeupMin] of [
      ["Mama", "60", "45"],
      ["Panna Młoda", "90", "60"],
    ]) {
      await add.getByLabel("Kto").fill(name);
      await add.getByLabel("Fryzura (minuty)").fill(hairMin);
      await add.getByLabel("Makijaż (minuty)").fill(makeupMin);
      await add.getByRole("button", { name: "Dodaj" }).click();
      await expect(page.locator(".row__title", { hasText: name })).toBeVisible();
    }
    // Gotowi o 13:00 (domyślnie): Panna Młoda ostatnia, mama zaczyna o 9:30.
    await expect(page.getByText(/Pierwsza osoba siada na fotel o\s09:30/)).toBeVisible();
    await expect(page.getByText(/fryzura 10:30–12:00 · makijaż 12:00–13:00/)).toBeVisible();

    const plan = page.getByRole("form", { name: "Godzina gotowości i osoby obsługujące" });
    await plan.getByLabel("Ile fryzjerek").fill("2");
    await plan.getByRole("button", { name: "Zapisz plan" }).click();
    await expect(page.getByText("Zapisano godziny")).toBeVisible();
    await expect(page.getByText(/Pierwsza osoba siada na fotel o\s10:15/)).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

    await page.goto(`/dzien/${token}`);
    const slots = page.getByRole("region", { name: "Fryzury" });
    await expect(slots.getByText(/10:15–11:15\s*Mama/)).toBeVisible();
    await expect(slots.getByText(/10:30–12:00\s*Panna Młoda/)).toBeVisible();
    await expectAccessible(page);
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Menu: alergeny, ostrzeżenie o diecie gości i menu na stronie gościa", async ({ page, request, browser }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", { headers: auth, data: { name: `Menu ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" } })
  ).json();
  const api = (path: string) => `/api/v1/weddings/${w.id}${path}`;
  try {
    const h = await (await request.post(api("/households"), { headers: auth, data: { name: "Nowakowie" } })).json();
    await request.post(api(`/households/${h.id}/guests`), { headers: auth, data: { first_name: "Jan", dietary_preference: "vegetarian" } });
    const rsvp = (await (await request.post(api(`/households/${h.id}/rsvp-link`), { headers: auth })).json()).token as string;

    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/menu`);
    await expect(page.getByRole("heading", { name: "Menu", level: 1 })).toBeVisible();
    const form = page.getByRole("form", { name: "Nowe danie" });
    await form.getByLabel("Nazwa").fill("Schab ze śliwką");
    await form.getByText("gluten", { exact: true }).click();
    await form.getByText("mleko", { exact: true }).click();
    await form.getByRole("button", { name: "Dodaj danie" }).click();
    await expect(page.getByText("Dodano danie")).toBeVisible();
    await expect(page.getByText(/Danie główne: nic dla diety wegetariańskiej \(1 os\./)).toBeVisible();
    await expect(page.getByText("alergeny: gluten, mleko")).toBeVisible();

    await form.getByLabel("Nazwa").fill("Pierogi ruskie");
    await form.getByText("Wegetariańskie", { exact: true }).click();
    await form.getByRole("button", { name: "Dodaj danie" }).click();
    await expect(page.getByText(/nic dla diety wegetariańskiej/)).toHaveCount(0);
    await page.getByText(/Pokaż menu na stronie gościa/).click();
    await expect(page.getByText("Menu widoczne na stronie gościa")).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

    const ctx = await browser.newContext({ ...test.info().project.use, locale: "pl-PL", timezoneId: "Europe/Warsaw" });
    const g = await ctx.newPage();
    await g.goto(`/rsvp/${rsvp}`);
    const menu = g.getByRole("region", { name: "Menu" });
    await expect(menu.getByText("Schab ze śliwką")).toBeVisible();
    await expect(menu.getByText(/wegetariańskie/)).toBeVisible();
    await expectAccessible(g);
    await ctx.close();
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Strona gościa: komunikat od pary, swój stół i księga życzeń", async ({ page, request, browser }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", { headers: auth, data: { name: `Strona gościa ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" } })
  ).json();
  const api = (path: string) => `/api/v1/weddings/${w.id}${path}`;
  try {
    const h = await (await request.post(api("/households"), { headers: auth, data: { name: "Nowakowie", contact_email: "nowak@example.com" } })).json();
    const jan = await (await request.post(api(`/households/${h.id}/guests`), { headers: auth, data: { first_name: "Jan" } })).json();
    const token = (await (await request.post(api(`/households/${h.id}/rsvp-link`), { headers: auth })).json()).token as string;
    const t5 = await (await request.post(api("/seating/tables"), { headers: auth, data: { name: "Stół 5", capacity: 8 } })).json();
    await request.put(api(`/seating/guests/${jan.id}`), { headers: auth, data: { table_id: t5.id, seat_number: 3 } });

    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/goscie`);
    await page.getByRole("navigation", { name: "Goście" }).getByRole("link", { name: "Strona gościa" }).click();
    await expect(page.getByRole("heading", { name: "Strona gościa", level: 1 })).toBeVisible();
    await page.getByLabel("Treść komunikatu").fill("Ceremonia przesunięta na 16:30.");
    await page.getByRole("button", { name: "Pokaż gościom" }).click();
    await expect(page.getByText("Komunikat widoczny dla gości")).toBeVisible();
    await page.getByRole("button", { name: "Wyślij e-mailem" }).click();
    const confirm = page.getByRole("alertdialog", { name: "Wysłać komunikat e-mailem?" }).or(page.getByRole("dialog", { name: "Wysłać komunikat e-mailem?" }));
    await expect(confirm.getByText(/do 1 z 1 rodzin/)).toBeVisible();
    await confirm.getByRole("button", { name: "Wyślij" }).click();
    await expect(page.getByText(/Wysłano e-mailem/)).toBeVisible();
    await page.getByText("Pokaż gościom ich stół i miejsca").click();
    await expect(page.getByRole("checkbox", { name: "Pokaż gościom ich stół i miejsca" })).toBeChecked();
    await page.getByText(/Goście mogą zostawić życzenia/).click();
    await expect(page.getByRole("checkbox", { name: /Goście mogą zostawić życzenia/ })).toBeChecked();
    await page.evaluate(() => window.scrollTo(0, 0));
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

    const ctx = await browser.newContext({ ...test.info().project.use, locale: "pl-PL", timezoneId: "Europe/Warsaw" });
    const g = await ctx.newPage();
    await g.goto(`/rsvp/${token}`);
    await expect(g.getByText("Ceremonia przesunięta na 16:30.")).toBeVisible();
    await expect(g.getByRole("region", { name: "Gdzie siedzicie" }).getByText(/Stół 5, miejsce 3/)).toBeVisible();
    const book = g.getByRole("region", { name: "Księga życzeń" });
    await book.getByLabel("Życzenia").fill("Sto lat, kochani!");
    await book.getByLabel("Podpis").fill("Jan z rodziną");
    await book.getByRole("button", { name: "Zostaw życzenia" }).click();
    await expect(book.getByText("Dziękujemy! Życzenia trafiły do pary.")).toBeVisible();
    await expectAccessible(g);
    await expectNoHorizontalScroll(g);
    await ctx.close();

    await page.reload();
    const wishes = page.getByRole("region", { name: /Księga życzeń/ });
    await expect(wishes.getByText("Sto lat, kochani!")).toBeVisible();
    await wishes.getByRole("link", { name: "Drukuj życzenia" }).click();
    await expect(page.getByRole("heading", { name: "Księga życzeń", level: 1 })).toBeVisible();
    await expect(page.getByText("— Jan z rodziną")).toBeVisible();
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Pomocnicy bez konta: link z zadaniami, przypisanie w zadaniu, odhaczenie przez pomocnika", async ({ page, request, browser }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", { headers: auth, data: { name: `Pomocnicy ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" } })
  ).json();
  const api = (path: string) => `/api/v1/weddings/${w.id}${path}`;
  try {
    // Termin za tydzień: zadanie widać od razu w Planie („Teraz”).
    const due = new Date(Date.now() + 7 * 864e5).toISOString().slice(0, 10);
    await request.post(api("/tasks"), { headers: auth, data: { title: "Ustalić kierowców na powroty", description: "3 auta z Tarnowa", due_date: due } });

    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/plan`);
    await page.getByRole("navigation", { name: "Plan" }).getByRole("link", { name: "Pomocnicy" }).click();
    await expect(page.getByRole("heading", { name: "Pomocnicy", level: 1 })).toBeVisible();
    await page.getByLabel("Kto pomaga").fill("Tata — kierowcy");
    await page.getByRole("button", { name: "Dodaj i utwórz link" }).click();
    const notice = page.getByText(/\/pomocnik\//);
    await expect(notice).toBeVisible();
    const url = (await notice.textContent())!.trim();
    await expect(page.getByText(/bez zadań/)).toBeVisible();
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

    // Przypisanie w oknie zadania.
    await page.goto(`/w/${w.id}/plan`);
    await page.getByText("Ustalić kierowców na powroty").first().click();
    const sheet = page.getByRole("dialog", { name: "Zadanie" });
    await sheet.getByRole("button", { name: /Pomocnik bez konta/ }).click();
    await page.getByRole("option", { name: "Tata — kierowcy" }).click();
    await sheet.getByRole("button", { name: "Zapisz", exact: true }).click();
    await expect(page.getByText("Zapisano zadanie")).toBeVisible();

    const ctx = await browser.newContext({ ...test.info().project.use, locale: "pl-PL", timezoneId: "Europe/Warsaw" });
    const g = await ctx.newPage();
    await g.goto(new URL(url).pathname);
    await expect(g.getByRole("heading", { name: "Tata — kierowcy", level: 1 })).toBeVisible();
    await expect(g.getByText("3 auta z Tarnowa")).toBeVisible();
    await g.getByText("Ustalić kierowców na powroty").click();
    await expect(g.getByText("Wszystko zrobione — dziękujemy!")).toBeVisible();
    await expectAccessible(g);
    await expectNoHorizontalScroll(g);
    await ctx.close();

    await page.goto(`/w/${w.id}/pomocnicy`);
    await expect(page.getByText("1 zrobione")).toBeVisible();
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Strona gościa: co widzą goście, lista prezentów i rezerwacja przez gościa", async ({ page, request, browser }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", { headers: auth, data: { name: `Prezenty ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" } })
  ).json();
  const api = (path: string) => `/api/v1/weddings/${w.id}${path}`;
  try {
    const h = await (await request.post(api("/households"), { headers: auth, data: { name: "Nowakowie" } })).json();
    await request.post(api(`/households/${h.id}/guests`), { headers: auth, data: { first_name: "Jan" } });
    const token = (await (await request.post(api(`/households/${h.id}/rsvp-link`), { headers: auth })).json()).token as string;

    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/goscie`);
    await page.getByRole("navigation", { name: "Goście" }).getByRole("link", { name: "Strona gościa" }).click();
    await expect(page.getByRole("heading", { name: "Strona gościa", level: 1 })).toBeVisible();
    const visible = page.getByRole("region", { name: "Co widzą goście" });
    await expect(visible.getByText("Informacje (dojazd, nocleg, dress code…)")).toBeVisible();
    await expect(visible.getByText("szkic")).toBeVisible();
    const gifts = page.getByRole("region", { name: /Lista prezentów/ });
    await gifts.getByText(/Pokaż gościom listę prezentów/).click();
    await expect(gifts.getByRole("checkbox", { name: /Pokaż gościom listę prezentów/ })).toBeChecked();
    await gifts.getByLabel("Co", { exact: true }).fill("Ekspres do kawy");
    await gifts.getByRole("button", { name: "Dodaj pomysł" }).click();
    await expect(gifts.getByText("wolne")).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

    const ctx = await browser.newContext({ ...test.info().project.use, locale: "pl-PL", timezoneId: "Europe/Warsaw" });
    const g = await ctx.newPage();
    await g.goto(`/rsvp/${token}`);
    const list = g.getByRole("region", { name: "Lista prezentów" });
    await list.getByRole("button", { name: "Wybieramy ten" }).click();
    await expect(list.getByRole("button", { name: "Rezygnuję" })).toBeVisible();
    await expectAccessible(g);
    await expectNoHorizontalScroll(g);
    await ctx.close();

    await page.reload();
    await expect(page.getByRole("region", { name: /Lista prezentów/ }).getByText("wybrali: Nowakowie")).toBeVisible();
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Szukaj: lupa w nagłówku, wynik otwiera zadanie w Planie, komentarz przy zadaniu", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", { headers: auth, data: { name: `Szukaj ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" } })
  ).json();
  const api = (path: string) => `/api/v1/weddings/${w.id}${path}`;
  try {
    await request.post(api("/tasks"), { headers: auth, data: { title: "Zamówić girlandę z eukaliptusa" } });
    await openDemoWedding(page);
    await page.goto(`/w/${w.id}`);
    await page.getByRole("link", { name: "Szukaj w weselu" }).click();
    await page.getByLabel("Zadania, goście, usługodawcy, wydatki").fill("eukalip");
    const tasks = page.getByRole("region", { name: "Zadania" });
    await expect(tasks.getByText("Zamówić girlandę z eukaliptusa")).toBeVisible();
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);
    await tasks.getByText("Zamówić girlandę z eukaliptusa").click();
    const sheet = page.getByRole("dialog", { name: "Zadanie" });
    await expect(sheet.getByLabel("Co trzeba zrobić?")).toHaveValue("Zamówić girlandę z eukaliptusa");

    await sheet.getByLabel("Dopisz komentarz").fill("Zapytać kwiaciarnię o cenę");
    await sheet.getByRole("button", { name: "Dodaj komentarz" }).click();
    await expect(sheet.getByText("Zapytać kwiaciarnię o cenę")).toBeVisible();
    await expect(sheet.getByText(/^Ty · /)).toBeVisible();
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Budżet: plan wydatków po miesiącach i koszt jednego gościa; podsumowanie dla rodziców", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", { headers: auth, data: { name: `Wydatki ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" } })
  ).json();
  const api = (path: string) => `/api/v1/weddings/${w.id}${path}`;
  try {
    const h = await (await request.post(api("/households"), { headers: auth, data: { name: "Nowakowie" } })).json();
    await request.post(api(`/households/${h.id}/guests`), { headers: auth, data: { first_name: "Jan" } });
    const cats = await (await request.get(api("/budget/categories"), { headers: auth })).json();
    const item = await (
      await request.post(api("/budget/items"), {
        headers: auth,
        data: { category_id: cats[0].id, name: "Sala", cost_mode: "per_guest", unit_price: { amount: "300", currency: "PLN" }, guest_basis: "invited" },
      })
    ).json();
    await request.post(api(`/budget/items/${item.id}/payments`), {
      headers: auth,
      data: { kind: "advance_zaliczka", amount: { amount: "100", currency: "PLN" }, due_date: "2028-03-15" },
    });

    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/budzet`);
    const plan = page.getByRole("region", { name: "Plan wydatków" });
    await expect(plan.getByText(/Odkładajcie ok\./)).toBeVisible();
    await expect(plan.getByRole("rowheader", { name: /marzec 2028/ })).toBeVisible();
    const cost = page.getByRole("region", { name: "Ile kosztuje gość" });
    await expect(cost.getByText(/\+300/).first()).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);

    await page.goto(`/w/${w.id}/wiecej`);
    await page.getByRole("link", { name: /Podsumowanie dla rodziców/ }).click();
    await expect(page.getByRole("heading", { name: "Jak idą przygotowania", level: 1 })).toBeVisible();
    await expect(page.getByText(/Zaproszonych: 1/)).toBeVisible();
    await expectAccessible(page);
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Usługodawca: gotowa wiadomość z danymi wesela", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", {
      headers: auth,
      data: { name: `Wiadomość ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "concordat", guest_count_planned: 120 },
    })
  ).json();
  try {
    const v = await (
      await request.post(`/api/v1/weddings/${w.id}/vendors`, { headers: auth, data: { name: "Dworek", category: "venue", email: "sala@example.com" } })
    ).json();
    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/uslugodawcy/${v.id}`);
    const box = page.getByRole("region", { name: "Napisz do usługodawcy" });
    await expect(box.getByLabel("Treść wiadomości")).toHaveValue(/ślub kościelny i wesele: 17 czerwca 2028/);
    await expect(box.getByLabel("Treść wiadomości")).toHaveValue(/dla ok\. 120 gości/);
    await expect(box.getByRole("link", { name: "Otwórz w poczcie" })).toHaveAttribute("href", /^mailto:sala@example\.com\?subject=/);
    await page.evaluate(() => window.scrollTo(0, 0));
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});

test("Muzyka: usunięcie utworu z „Cofnij”", async ({ page, request }) => {
  const login = await request.post("/api/v1/auth/login", { data: DEMO });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const w = await (
    await request.post("/api/v1/weddings", { headers: auth, data: { name: `Cofnij ${tag()}`, wedding_date: "2028-06-17", ceremony_type: "civil" } })
  ).json();
  try {
    await request.post(`/api/v1/weddings/${w.id}/music`, { headers: auth, data: { moment: "first_dance", title: "Perfect" } });
    await openDemoWedding(page);
    await page.goto(`/w/${w.id}/muzyka`);
    await page.getByRole("button", { name: "Usuń: Perfect" }).click();
    await expect(page.getByText("Usunięto: Perfect")).toBeVisible();
    await page.getByRole("button", { name: "Cofnij" }).click();
    await expect(page.getByRole("region", { name: "Pierwszy taniec" }).getByText("Perfect")).toBeVisible();
  } finally {
    await request.delete(`/api/v1/weddings/${w.id}`, { headers: auth });
  }
});
