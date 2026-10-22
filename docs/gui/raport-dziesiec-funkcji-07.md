# Raport: dziesięć kolejnych funkcji (analiza 07)

Data: 2026-10-22. Analiza i propozycje: `docs/analysis/07-dziesiec-kolejnych-funkcji.md`.

Źródła inspiracji to publiczne artykuły i porównania, bez kont i bez pobierania danych:
- polskie serwisy: Strona Weselna, Weselio, Weselniak, Wedding Board;
- zagraniczne aplikacje: Coordon, Zola, Joy, przegląd RSVP'd 2026;
- poradniki o błędach par: fotograf Kasolik, studioweselne.pl.

Dwie propozycje zmieniłem po przeglądzie kodu, żeby nie dublować tego, co już mamy:
- **kalkulator napojów** już jest w Budżecie, więc zastąpił go pomocnik wyboru daty;
- **lista „nie grać”** jest już w informacji dla usługodawcy, więc muzyka skupia się na utworach na momenty i propozycjach gości.

Migracje (przed każdą kopia bazy dev w `backups/`, wesele właściciela nietknięte):
- `5534deb69bf7` — muzyka i zdjęcia grupowe;
- `25470a50ecdd` — przygotowania i menu;
- `6a908b84bb85` — stół na stronie gościa, komunikat, życzenia;
- `72f6321078e8` — pomocnicy (ostatnia).

## Co zrobiono

| # | Funkcja | Gdzie w aplikacji | Najważniejsze |
|---|---|---|---|
| 1 | Pomocnik wyboru daty | Ustawienia wesela → „Porównajcie daty” | do 4 terminów; święta i długie weekendy (także ruchome: Wielkanoc, Boże Ciało; Wigilia od 2025); Adwent i Wielki Post przy ślubie w kościele; sezon; zachód słońca (NOAA) dla 16 miast wojewódzkich i „złota godzina”; ile miesięcy zostało. Uwagi, nie „ocena” daty |
| 2 | Tryb czytelny | strona gościa (`/rsvp/…`) | „Wielkość tekstu: Zwykły / Większy”: 20 px, mocniejszy kontrast, większe pola; zapamiętany na urządzeniu (PL i EN) |
| 3 | Muzyka | Dzień → Muzyka | utwory na momenty (ceremonia, wejście, pierwszy taniec, tort, oczepiny…), „koniecznie” i „nie grać”; gość proponuje do 3 utworów w RSVP, para zatwierdza; zatwierdzone są na linku DJ-a, zespołu lub muzyka (nowa wersja programu do potwierdzenia) |
| 4 | Zdjęcia grupowe | Dzień → Zdjęcia grupowe | typowe grupy (dziadkowie najpierw), osoby z listy gości, minuty i suma czasu, kolejność; świadek odhacza w dniu ślubu; fotograf i filmowiec widzą listę na linku (imię i inicjał nazwiska) |
| 5 | Plan przygotowań | Dzień → Przygotowania | fryzura i makijaż liczone wstecz od godziny „gotowi”, liczba fryzjerek i makijażystek, ostrzeżenie o starcie przed 6:00; fryzjerka widzi tylko fryzury, makijażystka tylko makijaże |
| 6 | Menu z alergenami | Goście → Menu | dania z 14 alergenami (rozp. UE 1169/2011), wegetariańskie i wegańskie; ostrzeżenie, gdy w przystawce, zupie, daniu głównym lub gorącym nie ma nic dla diety gości; menu na stronie gościa (PL i EN) |
| 7 | Gdzie siedzimy | Goście → „Komunikat, stół i życzenia” | każde zaproszenie widzi tylko swój stół i miejsca, bez innych gości; włączane przez parę |
| 8 | Komunikat dla gości | jw. | baner na stronie gościa; e-mail do rodzin z adresem, z podglądem liczby odbiorców, raz na komunikat, **bez nowego linku** (kody QR z zaproszeń działają dalej) |
| 9 | Księga życzeń | jw. i wydruk „Księga życzeń” | gość zostawia do 5 wpisów; para ukrywa lub usuwa; ukryte nie trafiają do wydruku; wpisy zostają po usunięciu zaproszenia |
| 10 | Pomocnicy bez konta | Plan → Pomocnicy; pole „Pomocnik bez konta” w zadaniu | link `/pomocnik/…` tylko z zadaniami pomocnika (tytuł, opis, termin) i odhaczaniem; bez budżetu i gości; nowy link unieważnia stary |

## Bezpieczeństwo i prywatność

- Nowe trasy wesela są w teście IDOR (inne wesele → 404, bez logowania → 401).
- Uprawnienia ról:
  - viewer tylko czyta;
  - koordynator dnia czyta zdjęcia i przygotowania oraz odhacza zdjęcia, ale nie edytuje;
  - muzyki koordynator nie widzi.
- Publiczne linki pomocnika i strony gościa:
  - mają limit prób na IP;
  - w bazie zapisujemy tylko hash tokenu, a eksport wesela pomija hash pomocnika.
- Fotograf widzi imię i inicjał nazwiska gościa.
- Strona gościa pokazuje tylko jego zaproszenie (stół, propozycje, życzenia).
- Uwag dietetycznych (dane o zdrowiu) menu nie analizuje.

## Znalezione przy okazji

- **Tekst pomocniczy był większy, niż zakłada projekt** (naprawione na prośbę właściciela, niżej) (16 px zamiast 14 px). Token koloru `--wp-text-secondary` nadpisuje
  token kroju o tej samej nazwie. Poprawka zmieni wygląd całej aplikacji, więc to decyzja właściciela (znane ograniczenia nr 58).
- Strona gościa: przełączniki języka i wielkości tekstu ułożone pionowo, bez zawijania przycisków.

## Weryfikacja

- Nowe testy backendu:
  - `test_date_check.py`, `test_music_photos.py`, `test_prep_menu.py`;
  - `test_guest_page_extras.py`, `test_helpers.py`;
  - rozszerzony `test_idor.py`.
- Nowe testy frontendu: `dateCompare`, `music`, `photoGroups`, `menu`, `prep`, `guestPage`, `helpers`.
- Nowe testy E2E (każda funkcja, 8 profili z axe): przeszły przed commitami.
- Pełny przebieg 22.10:
  - backend 1094 passed;
  - test kontraktu (Schemathesis) wykrył 2 błędy w `GET /date-check`:
    - skrajne daty (rok 1, rok 9999) dawały błąd 500 — teraz 422 dla lat spoza 1900–2200;
    - godziny w formacie `time` bez strefy były niezgodne ze schematem — teraz tekst „HH:MM”;
  - po obu poprawkach kontrakt zielony, dopisany test;
  - vitest 133;
  - E2E dev 418 passed (bez błędów);
  - E2E produkcyjne 391 passed: 1 test (edycja zadania, 390 px) przekroczył czas pod obciążeniem i po powtórzeniu przeszedł;
  - start aplikacji 142,4 KB gzip.

## Poprawka: tekst pomocniczy 14 px (na prośbę właściciela)

**Przyczyna:** generator tokenów (`scripts/tokens_to_css.py`) tworzył krój pisma jako `--wp-text-secondary`, a motyw
kolorów definiował pod tą samą nazwą kolor. Kolor wygrywał, więc `font: var(--wp-text-secondary) …` był nieprawidłowy
i tekst pomocniczy dziedziczył 16 px.

**Poprawka:** wszystkie tokeny typografii mają teraz przedrostek `--wp-type-*` (`--wp-type-body`, `--wp-type-secondary`,
`--wp-type-h1-size` itd.), a `--wp-text-*` to wyłącznie kolory tekstu. Zmienione:
- generator;
- `tokens.css` (aplikacja i podgląd projektu);
- style komponentów i ekranów;
- tryb czytelny strony gościa.

**Wynik:** tekst pomocniczy ma 14 px i 20 px interlinii, zgodnie z `design/tokens/tokens.json`; kolor bez zmian.
