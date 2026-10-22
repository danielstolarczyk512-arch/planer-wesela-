# Raport GUI: kroki 1–2 (szkielet, tokeny, motywy, komponenty bazowe, logowanie)

Data: 2026-10-19. Zakres według [GUI-SPEC-v1.1](GUI-SPEC-v1.1.md), sekcja 11, kroki 1 i 2.

## Wykonane działania

| Obszar | Co działa |
|---|---|
| **Szkielet** | `frontend/`: React 19, TypeScript (tryb ścisły), Vite 8, ESLint. Proxy `/api` w dev, więc aplikacja i API mają ten sam origin (wymóg ciasteczka). |
| **Tokeny** | `design/tokens/tokens.json` → `frontend/src/styles/tokens.css` (`task gui:tokens`). Tekst w `rem` z interlinią bez jednostki, więc powiększenie tekstu w systemie skaluje interfejs. Test sprawdza, że CSS jest aktualny względem tokenów. |
| **Motywy** | Jasny / Ciemny / Systemowy. Zmiana bez przeładowania (fokus i wpisany tekst zostają, sprawdza to test E2E). Preferencja ustawiana przed pierwszym malowaniem, bez mignięcia. |
| **Ograniczenie ruchu** | Systemowe lub z aplikacji. Komponenty używają zmiennych ruchu; tryb ograniczony zeruje przesunięcia i skalę i skraca przenikania do 100 ms. |
| **Fonty** | Lora, DM Sans, Bodoni Moda, Inter (OFL) z własnego serwera (Fontsource), bez Google Fonts. |
| **Klient API** | Typy generowane z naszego OpenAPI (`openapi-typescript`), `openapi-fetch`. Błędy RFC 9457 → `ApiError` (kod, pola, `Retry-After`). Brak sieci → `NetworkError` (nic nie udaje sukcesu). Klucz idempotencji dla zapisów. |
| **Sesja (zmiana backendu)** | Klient webowy (`X-Client: web`) dostaje refresh token w ciasteczku `HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`, a nie w JSON. Access token tylko w pamięci. Przy wielu równoczesnych 401 wykonywane jest jedno odświeżenie. Sesja przetrwa przeładowanie strony, a wylogowanie czyści ciasteczko (także przy wygasłym tokenie). Aplikacja mobilna działa jak dotąd. |
| **Komponenty bazowe** | Przycisk (4 warianty, zapis w toku, nieaktywny, reakcja na naciśnięcie), pola: tekst, hasło z pokazywaniem, **kwota** (przecinek, napis dla API, formatowanie po edycji), **data** (segmenty pl-PL), checkbox, przełącznik segmentowy, karta, status z ikoną i nazwą, komunikat, stan pusty, szkielet (po 150 ms), **dialog** i **dolny panel** (Escape, powrót fokusu, ochrona niezapisanych zmian), powiadomienie z „Cofnij” (6 s, pauza przy fokusie). |
| **Ekrany** | Logowanie (walidacja z fokusem na pierwszym błędzie, jeden komunikat dla złego e-maila i hasła, odliczanie przy limicie prób, bezpieczny powrót bez otwartego przekierowania), powłoka z „Przejdź do treści”, lista wesel z prawdziwego API (data → „za N dni”, tylko miesiąc → „Sierpień 2027 · dokładna data do ustalenia”), panel „Nowe wesele”, ustawienia wyglądu, galeria komponentów (tylko dev). |
| **Produkcja** | Caddy serwuje aplikację i API pod jedną domeną, z polityką CSP bez skryptów inline. Dwa stałe bloki stylu React Aria są dopuszczone skrótami SHA-256, bez `unsafe-inline`. Cache: pliki z hashem rok, `index.html` zawsze świeży. |

## Wyniki weryfikacji

| Kontrola | Wynik |
|---|---|
| Testy jednostkowe i komponentów (Vitest) | **46 passed** |
| E2E na serwerze deweloperskim: 4 szerokości (320/390/768/1280) × 2 motywy | **72 passed** |
| E2E na buildzie produkcyjnym z nagłówkiem CSP | **40 passed** (galeria pominięta, istnieje tylko w dev) |
| E2E na stagingu za Caddy przez HTTPS (ciasteczko `Secure`, CSP z Caddy) | **40 passed** |
| Audyt dostępności axe (WCAG 2.0/2.1/2.2 A i AA) na logowaniu, liście wesel, galerii i otwartym panelu | **0 naruszeń** w obu motywach i na wszystkich szerokościach |
| Tekst powiększony do 200% przy 320 px | bez poziomego przewijania, przycisk osiągalny |
| Kolejność klawiatury na logowaniu | e-mail → hasło → pokaż hasło → zaloguj |
| Budżet JS na start | **129,7 KB** gzip (limit 170 KB); po zalogowaniu dochodzi 46 KB |
| Licencje npm (274 pakiety) | brak GPL/AGPL/SSPL; MPL tylko w narzędziach (axe, lightningcss) |
| Backend (nowe testy trybu ciasteczka) | ciasteczko `HttpOnly`/`SameSite`/ścieżka, odświeżenie tylko z nagłówkiem klienta, czyszczenie przy wylogowaniu i przy błędzie, klient mobilny bez zmian |
| `npm audit` | 0 podatności |

## Decyzje i odstępstwa od specyfikacji

| Decyzja | Uzasadnienie |
|---|---|
| Generator tokenów (nasz skrypt) zamiast Style Dictionary | tokeny mają motywy i wartości złożone; skrypt ma ok. 120 linii, a zależność byłaby większa niż generator |
| Bez react-hook-form i Zod | konflikt zależności `@hookform/resolvers`; Zod zajmował 361 KB źródeł przy dwóch prostych warunkach logowania. Walidację robią kontrolki React Aria + proste funkcje. Do powrotu przy dużych formularzach (kreator wesela). |
| Galeria w aplikacji zamiast Storybook | ta sama wartość (oba motywy, wszystkie stany, testy axe), bez kilkuset MB narzędzi |
| CSP ze skrótami dla stylów React Aria | bez osłabiania polityki przez `unsafe-inline`; test E2E wykrywa zmianę po aktualizacji biblioteki |
| TypeScript 5.9 zamiast 7 | typescript-eslint i openapi-typescript nie wspierają jeszcze 7.x |

## Ograniczenia (do kolejnych kroków)

- Dolna nawigacja z 5 zakładkami i widoki Dziś / Plan / Budżet / Goście: **krok 3**.
- PWA (manifest, instalacja, odczyt offline) i metryki zastępcze fontów (`size-adjust`, brak skoku układu przy wczytaniu): **krok 6**.
- Rejestracja, weryfikacja e-mail i reset hasła w GUI: kolejny krok (API gotowe).
- Szkice formularzy w IndexedDB: przy pierwszym dłuższym formularzu.
- Testy na prawdziwych telefonach (Android średniej klasy, iPhone): przed udostępnieniem parom.
