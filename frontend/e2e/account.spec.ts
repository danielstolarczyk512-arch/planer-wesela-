import AxeBuilder from "@axe-core/playwright";
import { createHmac } from "node:crypto";

import { expect, test, type Page } from "@playwright/test";

// Rejestracja, potwierdzenie e-maila i reset hasła. Wiadomości odbiera lokalny Mailpit (docker compose).
// Limit API: 10 rejestracji na godzinę z jednego IP — scenariusz uruchamiamy na dwóch profilach.
const MAILPIT = process.env.MAILPIT_URL ?? "http://127.0.0.1:8025";

test.skip(!!process.env.E2E_BASE_URL, "Mailpit tylko w środowisku deweloperskim");

async function expectAccessible(page: Page) {
  await page.evaluate(
    () =>
      new Promise<void>((done) => requestAnimationFrame(() => requestAnimationFrame(() => done()))).then(() =>
        Promise.all(document.getAnimations().map((a) => a.finished.catch(() => undefined))),
      ),
  );
  const result = await new AxeBuilder({ page })
    .exclude('[role="log"][aria-live="assertive"] > [role="img"]')
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => `${n.target} ${n.html.slice(0, 120)}`).join(" | ")}`)).toEqual([]);
}

/** Kod TOTP (RFC 6238, SHA-1, 6 cyfr, 30 s) z sekretu base32 — jak w aplikacji w telefonie. */
function totp(secretBase32: string, offsetSeconds = 0): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const ch of secretBase32.replace(/\s|=/g, "").toUpperCase()) bits += alphabet.indexOf(ch).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g)!.map((b) => parseInt(b, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor((Date.now() / 1000 + offsetSeconds) / 30)));
  const h = createHmac("sha1", key).update(counter).digest();
  const o = h[h.length - 1]! & 0xf;
  const n = ((h[o]! & 0x7f) << 24) | (h[o + 1]! << 16) | (h[o + 2]! << 8) | h[o + 3]!;
  return String(n % 1_000_000).padStart(6, "0");
}

/** Token z najnowszej wiadomości do adresu (czeka, aż worker ją wyśle). */
async function tokenFromMail(page: Page, to: string, path: string): Promise<string> {
  let token = "";
  await expect
    .poll(
      async () => {
        const list = await (await page.request.get(`${MAILPIT}/api/v1/messages?limit=50`)).json();
        type Msg = { ID: string; To: { Address: string }[] };
        for (const m of ((list.messages ?? []) as Msg[]).filter((x) => x.To.some((t) => t.Address === to))) {
          const msg = await (await page.request.get(`${MAILPIT}/api/v1/message/${m.ID}`)).json();
          const text: string = msg.Text ?? "";
          const start = text.indexOf(`${path}?token=`);
          const found = start >= 0 ? [null, text.slice(start + path.length + 7).split(/\s/)[0]] : null;
          if (found) {
            token = found[1]!;
            return true;
          }
        }
        return false;
      },
      { timeout: 30_000, intervals: [1000] },
    )
    .toBe(true);
  return token;
}

test("rejestracja, potwierdzenie e-maila, reset hasła, ustawienia konta", async ({ page }) => {
  test.skip(!["320-light", "1280-dark"].includes(test.info().project.name), "Limit rejestracji na IP");
  test.setTimeout(120_000);
  const email = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`;
  // Hasła generowane w teście (bez stałych wartości w repozytorium).
  const words = () => ["kawa", "rower", "tulipan", "lampa", "sowa", "most"].sort(() => Math.random() - 0.5).slice(0, 3).join("-");
  const password = `${words()}-${Math.floor(Math.random() * 90 + 10)}`;
  const newPassword = `${words()}-${Math.floor(Math.random() * 90 + 10)}`;

  await page.goto("/logowanie");
  await page.getByRole("link", { name: "Załóż konto" }).click();
  await expect(page.getByRole("heading", { name: "Załóż konto" })).toBeVisible();
  await expectAccessible(page);
  // Walidacja: słabe hasło i brak zgody.
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Hasło", { exact: true }).fill("krotkie");
  await page.getByRole("button", { name: "Załóż konto" }).click();
  await expect(page.getByText("Hasło musi mieć co najmniej 10 znaków.")).toBeVisible();
  await expect(page.getByText("Aby założyć konto, zaakceptuj regulamin")).toBeVisible();
  await page.getByLabel("Hasło", { exact: true }).fill(password);
  await page.getByText("Akceptuję regulamin i politykę prywatności").click();
  await page.getByRole("button", { name: "Załóż konto" }).click();
  await expect(page.getByRole("heading", { name: "Sprawdź skrzynkę" })).toBeVisible();

  // E-mail prowadzi na polską trasę; stary adres /verify-email nadal przekierowuje.
  const verify = await tokenFromMail(page, email, "potwierdz-email");
  await page.goto(`/verify-email?token=${verify}`);
  await expect(page).toHaveURL(/\/potwierdz-email\?token=/);
  await expect(page.getByRole("heading", { name: "Adres potwierdzony" })).toBeVisible();
  // Drugi raz ten sam token: jednorazowy.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Link nie działa" })).toBeVisible();

  await page.goto("/logowanie");
  await page.getByRole("link", { name: "Nie pamiętasz hasła?" }).click();
  await expect(page.getByRole("heading", { name: "Nie pamiętasz hasła?" })).toBeVisible();
  await page.getByLabel("E-mail").fill(email);
  await page.getByRole("button", { name: "Wyślij link" }).click();
  await expect(page.getByRole("heading", { name: "Sprawdź skrzynkę" })).toBeVisible();
  const reset = await tokenFromMail(page, email, "nowe-haslo");
  await page.goto(`/reset-password?token=${reset}`);
  await page.getByLabel("Nowe hasło", { exact: true }).fill(newPassword);
  await page.getByLabel("Powtórz hasło", { exact: true }).fill(newPassword + "x");
  await page.getByRole("button", { name: "Ustaw hasło" }).click();
  await expect(page.getByText("Hasła się różnią.")).toBeVisible();
  await page.getByLabel("Powtórz hasło", { exact: true }).fill(newPassword);
  await expectAccessible(page);
  await page.getByRole("button", { name: "Ustaw hasło" }).click();
  await expect(page.getByRole("heading", { name: "Hasło zmienione" })).toBeVisible();

  await page.getByRole("link", { name: "Zaloguj się" }).click();
  await expect(page.getByRole("heading", { name: "Zaloguj się" })).toBeVisible();
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Hasło", { exact: true }).fill(newPassword);
  await page.getByRole("button", { name: "Zaloguj się" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/logowanie"));

  await page.goto("/ustawienia");
  await expect(page.getByText(email)).toBeVisible();
  await expect(page.getByText("Potwierdzony", { exact: true })).toBeVisible();
  await expect(page.getByText("To urządzenie")).toBeVisible();
  await expect(page.getByText(/^udzielona .* wersja /).first()).toBeVisible();
  await page.locator(".wp-segmented__option", { hasText: "Co tydzień" }).click();
  await expect(page.getByText("Zapisano częstotliwość podsumowań")).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Pobierz moje dane" }).click();
  expect((await download).suggestedFilename()).toMatch(/^moje-dane-\d{4}-\d{2}-\d{2}\.json$/);
  await expectAccessible(page);

  // Weryfikacja dwuetapowa: włączenie (kod z sekretu), kody zapasowe, logowanie w dwóch krokach.
  await page.getByRole("button", { name: "Włącz weryfikację dwuetapową" }).click();
  await page.getByLabel("Hasło (dla bezpieczeństwa)").fill(newPassword);
  await page.getByRole("button", { name: "Dalej" }).click();
  await expect(page.getByRole("img", { name: /Kod QR/ })).toBeVisible();
  const secret = (await page.locator(".mfa-secret").innerText()).replace(/\s/g, "");
  await page.getByLabel("Kod z aplikacji").fill(totp(secret));
  await page.getByRole("button", { name: "Włącz", exact: true }).click();
  await expect(page.getByRole("list", { name: "Kody zapasowe" }).getByRole("listitem")).toHaveCount(10);
  await expectAccessible(page);
  await page.getByText("Zapisałem/am kody w bezpiecznym miejscu").click();
  await page.getByRole("button", { name: "Gotowe" }).click();
  await expect(page.getByText("Kody zapasowe: 10 z 10")).toBeVisible();

  await page.getByRole("button", { name: "Wyloguj" }).first().click();
  await page.waitForURL(/logowanie/);
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Hasło", { exact: true }).fill(newPassword);
  await page.getByRole("button", { name: "Zaloguj się" }).click();
  await expect(page.getByRole("heading", { name: "Weryfikacja dwuetapowa" })).toBeVisible();
  await page.getByLabel("Kod z aplikacji").fill("000000");
  await page.getByRole("button", { name: "Potwierdź" }).click();
  await expect(page.getByText("Nieprawidłowy kod. Spróbuj ponownie.")).toBeVisible();
  await expectAccessible(page);
  // Kod z następnego okna 30 s (bieżący został zużyty przy włączaniu).
  await page.getByLabel("Kod z aplikacji").fill(totp(secret, 30));
  await page.getByRole("button", { name: "Potwierdź" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/logowanie"));
  await page.goto("/ustawienia");
  await expect(page.getByText("Włączona", { exact: true })).toBeVisible();

  // Usunięcie konta (karencja 30 dni) i anulowanie — po teście konto zostaje zaplanowane do usunięcia.
  await page.getByRole("button", { name: "Usuń konto" }).click();
  await page.getByRole("dialog").getByLabel("Hasło", { exact: true }).fill(newPassword);
  await page.getByRole("dialog").getByRole("button", { name: "Usuń konto" }).click();
  await expect(page.getByText("Konto zostanie usunięte")).toBeVisible();
  await page.getByRole("button", { name: "Nie usuwaj konta" }).click();
  await expect(page.getByText("Anulowano usunięcie konta")).toBeVisible();
  await page.getByRole("button", { name: "Usuń konto" }).click();
  await page.getByRole("dialog").getByLabel("Hasło", { exact: true }).fill(newPassword);
  await page.getByRole("dialog").getByRole("button", { name: "Usuń konto" }).click();
  await expect(page.getByText("Konto zostanie usunięte")).toBeVisible();
});

test("regulamin i polityka prywatności: dostępne bez logowania, oznaczone jako robocze", async ({ page }) => {
  for (const [path, title] of [
    ["/regulamin", "Regulamin"],
    ["/prywatnosc", "Polityka prywatności"],
  ] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: title, level: 1 })).toBeVisible();
    await expect(page.getByText("Wersja robocza")).toBeVisible();
    await expectAccessible(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
  }
});
