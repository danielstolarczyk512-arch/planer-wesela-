# Raport: strona gościa po angielsku — plan dalszej pracy C2 (analiza 03)

Data: 2026-10-21.

- Strona z linku RSVP (`/rsvp/:token`) i podgląd „Zobacz jak gość” w dwóch językach: polskim
  i angielskim (`features/rsvp/i18n.ts` — własny mały słownik, bez nowych zależności).
- Domyślnie polski; przeglądarka w innym języku → angielski. Przełącznik „Polski / English” na
  górze strony; wybór zapamiętany na urządzeniu gościa (localStorage, bez danych osobowych).
- Tłumaczony jest interfejs (formularz, odpowiedzi, diety, wiek, osoba towarzysząca, komunikaty,
  nota o prywatności) oraz daty („17 June 2028, at 15:00” w czasie polskim). Treści wpisane przez
  parę (powitanie, dojazd, nazwy wydarzeń, punkty programu) zostają jak są.
- `lang` na elemencie `main` — czytnik ekranu czyta stronę właściwym głosem.
- **Język zaproszenia** (`households.language`, migracja `c8e1a4d2f913`): w arkuszu zaproszenia
  „Automatycznie (wg przeglądarki gościa)” (domyślnie), „Polski” albo „Angielski”. Wybór pary decyduje
  o języku **e-maila z linkiem RSVP** (szablon EN, `<html lang="en">`) i o języku strony; kolejność
  na stronie: wybór gościa → język zaproszenia → przeglądarka. Przy „automatycznie” e-mail idzie
  po polsku.
- Ograniczenie: komunikaty błędów z API są po polsku.
- Testy: vitest `i18n.test.ts` (język domyślny, zapamiętany wybór, daty, liczba odpowiedzi,
  zgodność kluczy obu języków); E2E — przełączenie na angielski, przeładowanie, przeglądarka
  `en-US` (axe); dotychczasowy test RSVP po polsku bez zmian.
- **„Dodaj do kalendarza”** przy każdym wydarzeniu z godziną: plik `.ics` (RFC 5545, czas UTC, adres,
  koniec z danych albo 6 h) tworzony w przeglądarce gościa (`src/lib/ics.ts`) — bez nowych publicznych
  adresów; RSVP zwraca `ends_at` wydarzeń. Vitest (czas, ucieczka znaków) i E2E (pobranie pliku).
