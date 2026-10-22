import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Konto demo z danymi fikcyjnymi (scripts/seed.py, tylko środowisko deweloperskie).
const DEMO = { email: "demo@example.com", password: process.env.WP_SEED_PASSWORD ?? "Demo-Wesele-2027!" };

async function expectAccessible(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(", ")}`)).toEqual([]);
}

async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

async function signIn(page: Page) {
  await page.goto("/logowanie");
  await page.getByLabel("E-mail").fill(DEMO.email);
  await page.getByLabel("Hasło", { exact: true }).fill(DEMO.password);
  await page.getByRole("button", { name: "Zaloguj się" }).click();
  await expectSignedIn(page);
}

/** Po zalogowaniu: lista wesel albo od razu otwarte wesele (jedno lub ostatnio używane). */
async function expectSignedIn(page: Page) {
  await expect(
    page.getByRole("heading", { name: "Wasze wesela" }).or(page.getByRole("navigation", { name: "Główne" })),
  ).toBeVisible();
}

test.describe("logowanie", () => {
  test("strona logowania: dostępność, układ, kolejność klawiatury", async ({ page }) => {
    await page.goto("/logowanie");
    await expect(page.getByRole("heading", { name: "Zaloguj się" })).toBeVisible();
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);
    await page.getByLabel("E-mail").focus();
    await page.keyboard.press("Tab");
    await expect(page.getByLabel("Hasło", { exact: true })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "Pokaż hasło" })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "Zaloguj się" })).toBeFocused();
  });

  test("tekst powiększony do 200%: bez poziomego przewijania, przycisk dostępny", async ({ page }) => {
    await page.goto("/logowanie");
    await page.evaluate(() => (document.documentElement.style.fontSize = "200%"));
    await expectNoHorizontalScroll(page);
    // Przy dużym tekście strona się przewija (spec: przewijanie zamiast pomniejszania).
    await page.getByRole("button", { name: "Zaloguj się" }).scrollIntoViewIfNeeded();
    await expect(page.getByRole("button", { name: "Zaloguj się" })).toBeVisible();
  });

  test("błędne hasło: komunikat ogólny, bez ujawniania konta", async ({ page }) => {
    await page.goto("/logowanie");
    // Osobny adres: nieudane próby na koncie demo zablokowałyby je limitem (5 na 15 min).
    await page.getByLabel("E-mail").fill(`nie-ma-takiego-${Date.now()}@example.com`);
    await page.getByLabel("Hasło", { exact: true }).fill("zdecydowanie-zle-haslo");
    await page.getByRole("button", { name: "Zaloguj się" }).click();
    await expect(page.getByRole("alert")).toHaveText(/Nieprawidłowy e-mail lub hasło/);
  });

  test("sesja: refresh token w ciasteczku HttpOnly, przetrwa przeładowanie, wylogowanie ją kończy", async ({ page, context }) => {
    await signIn(page);
    const cookie = (await context.cookies()).find((c) => c.name === "wp_refresh");
    expect(cookie?.httpOnly).toBe(true);
    expect(cookie?.sameSite).toBe("Strict");
    expect(await page.evaluate(() => JSON.stringify(localStorage) + document.cookie)).not.toContain(cookie!.value);
    await page.reload();
    await expectSignedIn(page);
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);
    await page.getByRole("button", { name: "Wyloguj" }).click();
    await expect(page.getByRole("heading", { name: "Zaloguj się" })).toBeVisible();
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Zaloguj się" })).toBeVisible();
  });
});

test("CSP: brak naruszeń polityki bezpieczeństwa (build produkcyjny z nagłówkiem)", async ({ page }) => {
  const violations: string[] = [];
  page.on("console", (m) => m.text().includes("Content Security Policy") && violations.push(m.text()));
  page.on("pageerror", (e) => violations.push(e.message));
  await signIn(page);
  await page.goto("/ustawienia");
  await expect(page.getByRole("heading", { name: "Wygląd" })).toBeVisible();
  await page.goto("/?wybierz=1");
  // Lista wesel albo stan pusty (nowe konto): oba otwierają ten sam panel.
  await page.getByRole("button", { name: /Nowe wesele|Utwórz wesele/ }).first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  expect(violations).toEqual([]);
});

test.describe("komponenty", () => {
  test.skip(
    process.env.E2E_PROD === "1" || !!process.env.E2E_BASE_URL,
    "Galeria istnieje tylko w trybie deweloperskim",
  );

  test("galeria: dostępność w motywie i bez poziomego przewijania", async ({ page }) => {
    await page.goto("/komponenty");
    await expect(page.getByRole("heading", { name: "Komponenty" })).toBeVisible();
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);
  });

  test("dolny panel: Escape chroni zmiany, fokus wraca do przycisku", async ({ page }) => {
    await page.goto("/komponenty");
    const trigger = page.getByRole("button", { name: "Dolny panel" });
    await trigger.click();
    await page.getByLabel("Treść notatki").fill("Zadzwonić do DJ-a");
    await page.keyboard.press("Escape");
    await expect(page.getByText("Zapisać szkic czy odrzucić zmiany?")).toBeVisible();
    await expectAccessible(page);
    await page.getByRole("button", { name: "Odrzuć zmiany" }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });

  test("ograniczenie ruchu z systemu wyłącza przesunięcia i skalę", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/komponenty");
    // Arkusz stylów może dojść po pierwszym renderze: czekamy na wartości, a nie czytamy raz.
    await expect
      .poll(() =>
        page.evaluate(() => {
          const s = getComputedStyle(document.documentElement);
          return [s.getPropertyValue("--wp-motion-detail-translate").trim(), s.getPropertyValue("--wp-motion-press-scale").trim()];
        }),
      )
      .toEqual(["0px", "1"]);
  });

  test("zmiana motywu nie gubi wpisanego tekstu", async ({ page }) => {
    await page.goto("/komponenty");
    const field = page.getByLabel("Nazwa usługodawcy");
    await field.fill("Dworek pod Lipami");
    // Kliknięcie w etykietę opcji (jak palcem); pole radio jest wizualnie ukryte.
    await page.locator(".wp-segmented__option", { hasText: "Ciemny" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.getByRole("radio", { name: "Ciemny" })).toBeChecked();
    await expect(field).toHaveValue("Dworek pod Lipami");
    await page.locator(".wp-segmented__option", { hasText: "Systemowy" }).click();
  });
});
