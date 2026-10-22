# Raport GUI — konto, ruch, PWA (kroki 5 i część 6)

Data: 2026-10-20. Commity: `69a0abb` (konto, regulamin i polityka — robocze) oraz commit z ruchem i PWA.

## Konto (część kroku 6)

| Ekran | Adres | Uwagi |
|---|---|---|
| Rejestracja | `/rejestracja` | e-mail, hasło (min. 10 znaków + ocena siły po stronie serwera, komunikat przy polu), imię, zgoda na regulamin i politykę (linki obok pola, nie w etykiecie) |
| Potwierdzenie e-maila | `/potwierdz-email?token=` | token wysyłany raz (odporne na podwójny efekt w trybie deweloperskim); drugi raz → „Link nie działa” |
| Nie pamiętam hasła | `/zapomniane-haslo` | zawsze ten sam komunikat (bez ujawniania, czy konto istnieje) |
| Nowe hasło | `/nowe-haslo?token=` | powtórzenie hasła, informacja o wylogowaniu wszystkich urządzeń |
| Ustawienia | `/ustawienia` | e-mail i potwierdzenie (ponowna wysyłka), imię, zmiana hasła, zalogowane urządzenia z wylogowaniem, **eksport danych (JSON)**, **usunięcie konta** z 30-dniową karencją i anulowaniem, wygląd |
| Regulamin, polityka | `/regulamin`, `/prywatnosc` | **wersje robocze**, wyraźnie oznaczone; opisują faktyczne działanie (retencja gości 90 dni po weselu, karencja 30 dni, audyt 24 mies., AI lokalnie, jedno niezbędne ciasteczko) |

Linki z e-maili API (`/verify-email`, `/reset-password`, `/forgot-password`, `/settings`) przekierowują na polskie
adresy z zachowaniem tokenu — nie trzeba zmieniać szablonów wiadomości.

## Ruch (krok 5)

Według `design/tokens/motion.json` i GUI-SPEC v1.1 §7 (bez biblioteki animacji):

- **Zakładki** tylko się przenikają (View Transition, 180 ms) — wcześniej treść „wjeżdżała z boku” jak ekran
  szczegółów. **Ekrany szczegółów** (ustawienia, oferta, harmonogram…) zachowują przesuw 20 px + przenikanie (240 ms).
- **Zmiana motywu** przenika się (200 ms) zamiast skoku kolorów; stan formularzy zostaje.
- **Naciśnięcie** wierszy do edycji, kart-linków i „żetonów” osób: skala 0,985 jak przyciski.
- **Ograniczony ruch** (system lub ustawienie aplikacji): bez przesuwu i skali, przenikania ≤ 100 ms, zmiana motywu
  natychmiast.
- Bez zmian (było wcześniej): okna i panele, toasty, rozwijanie, zaznaczanie, przywracanie przewinięcia.

## PWA (część kroku 6)

- `manifest.webmanifest` (pl, standalone, kolory marki), ikony 192/512, maskowalna 512 i Apple 180 — generowane
  z logo SVG skryptem `task gui:icons` (Playwright, bez nowych zależności).
- `sw.js` napisany ręcznie, krótki i przejrzysty: strona — najpierw sieć, bez sieci ostatnia powłoka; pliki z hashem —
  z pamięci (limit 80). **`/api/*` nigdy nie trafia do pamięci podręcznej** (dane osobowe; test to sprawdza).
- Rejestracja tylko w buildzie produkcyjnym. Caddy: `sw.js` i manifest z `Cache-Control: no-cache`.
- **Start bez sieci**: zamiast wylogowania — ekran „Brak połączenia” z „Spróbuj ponownie”; po powrocie sieci aplikacja
  sama wraca (wcześniej użytkownik trafiał na logowanie).

## Weryfikacja

- Vitest: 64 testy (m.in. stan sesji bez sieci, nazwy urządzeń).
- Playwright: pełna ścieżka konta z lokalnym Mailpitem (rejestracja → potwierdzenie → reset → logowanie → eksport →
  usunięcie i anulowanie), dokumenty prawne na 8 profilach, PWA i start offline na buildzie produkcyjnym.
- Start aplikacji: 137,8 KB gzip (limit 170 KB).

## Do decyzji właściciela

1. **Regulamin i polityka prywatności** — robocze; przed startem: dane firmy, cennik, dostawcy (hosting, e-mail),
   okres kopii zapasowych i rozstrzygnięcie roli platformy wobec danych gości (administrator czy podmiot przetwarzający).
   Po zmianie treści podnieść `WP_TERMS_VERSION` / `WP_PRIVACY_VERSION` (zgody są wersjonowane).
2. **Testy na prawdziwym telefonie** (instalacja PWA na Androidzie i iPhonie, gesty, klawiatura ekranowa) — wymagają
   urządzeń; automaty sprawdzają tylko emulację szerokości i dotyku.
