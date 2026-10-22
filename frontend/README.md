# Nasz dzień: aplikacja webowa (PWA)

React 19 + TypeScript + Vite, kontrolki React Aria Components. Specyfikacja: [docs/gui/GUI-SPEC-v1.1.md](../docs/gui/GUI-SPEC-v1.1.md).

## Uruchomienie

```bash
task up
```

```bash
task web:install
```

```bash
task web:dev
```

Aplikacja: http://localhost:5173 (API przez proxy Vite z http://127.0.0.1:8010). Konto demo: `task seed`, a zawartość wesela demo (zadania, wydatki, goście; dane fikcyjne): `uv run python -m scripts.seed --content`. Testy E2E widoków wesela jej wymagają. Galeria komponentów (tylko tryb deweloperski): http://localhost:5173/komponenty.

## Struktura

```
src/
  api/          klient z typami z OpenAPI (schema.d.ts), sesja, błędy RFC 9457
  app/          routing, providery (React Query, i18n pl-PL, powiadomienia)
  components/   komponenty bazowe: Button, pola (tekst, hasło, kwota, data), Checkbox,
                Segmented, Card, StatusChip, Notice, EmptyState, Skeleton, Dialog, Sheet, Toast
  features/     ekrany: logowanie, powłoka, wesela, ustawienia wyglądu, galeria
  lib/          formatowanie pl-PL (kwoty, liczba mnoga, daty w Europe/Warsaw), preferencje
  styles/       tokens.css (GENEROWANY z design/tokens: task gui:tokens), base.css
e2e/            Playwright: 4 szerokości × 2 motywy, axe, tekst 200%, CSP, sesja
scripts/        kontrola licencji, budżet JS, raport pakietu
```

## Zasady

- **Kolory, fonty, ruch tylko z tokenów** (`--wp-*`). Zmiana: `design/tokens/tokens.json` → `task gui:tokens` → `task gui:contrast`. Test pilnuje, że `tokens.css` jest aktualny.
- **Sesja:** access token tylko w pamięci; refresh token w ciasteczku `HttpOnly; SameSite=Strict` (nagłówek `X-Client: web`). Nic z sesji w localStorage.
- **Zapisy tworzące rekord** wysyłają `Idempotency-Key` (ten sam przy ponowieniu).
- **Kwoty** jako napisy z API, formatowane przez `formatMoney` (grupowanie także 4 cyfr); brak kwoty = „Brak wyceny”.
- **Liczebniki** przez `plural()` z formami całego zdania.
- **CSP bez skryptów inline** (polityka w `vite.config.ts` = `deploy/Caddyfile`, test pilnuje zgodności). Skróty dopuszczają dwa stałe bloki stylu React Aria; po aktualizacji biblioteki test E2E `CSP` pokaże ewentualną zmianę.
- **Budżet JS na start ≤ 170 KB gzip** (`npm run budget`); ekrany po zalogowaniu ładowane osobno.
- Licencje: tylko MIT/Apache/BSD/ISC/OFL; MPL wyłącznie w narzędziach (axe, lightningcss) (`npm run licenses`).

## Testy

| Polecenie | Zakres |
|---|---|
| `npx vitest run` | jednostkowe i komponentów (jsdom) |
| `npx playwright test` | E2E na serwerze deweloperskim (wymaga `task up` + `task seed`) |
| `E2E_PROD=1 npx playwright test` | E2E na buildzie produkcyjnym z nagłówkiem CSP |
| `E2E_BASE_URL=https://localhost:9443 npx playwright test` | E2E na stagingu za Caddy (HTTPS) |
| `task web:ci` | wszystko powyżej (poza stagingiem) + typy, lint, licencje, budżet |
