# Raport: spójność aplikacji i 7 nowych funkcji (analiza 08)

Data: 2026-10-22. Analiza: `docs/analysis/08-spojnosc-i-nowe-funkcje.md`.

Migracja `62688b77b348`: lista prezentów, komentarze przy zadaniach, `guest_info.gifts_enabled`. Przed nią zrobiona kopia
bazy dev; wesele właściciela nietknięte.

## Wtyczki

Zaproponowane do instalacji (darmowe, z katalogu Anthropic). Instalację zatwierdza właściciel w karcie:
- **frontend-design** — projektowanie interfejsu;
- **Design** — przegląd projektu, teksty UX, audyt dostępności;
- **A11y Enforcer** — WCAG 2.2.

Bez nich dostępność sprawdza axe w każdym teście E2E (8 profili).

## Część 1. Niespójności — poprawione

| # | Było | Jest |
|---|---|---|
| S1 | Tekst pomocniczy 16 px zamiast 14 px (ta sama nazwa tokenu dla koloru i kroju) | tokeny typografii `--wp-type-*`, kolory `--wp-text-*`; 14 px / 20 px. Przy okazji: pola daty mają co najmniej 24 × 24 px (WCAG 2.5.8), a na telefonie ≤ 400 px „Wyloguj” to sama ikona |
| S2 | „Plan przygotowań” (Plan) i „Przygotowania” (Dzień) — dwa znaczenia | Dzień → **„Fryzura i makijaż”** (`/fryzura-i-makijaz`) |
| S3 | Ustawienia strony gościa w 5 miejscach | podzakładka **Goście → „Strona gościa”**: „Co widzą goście” (stan każdej części z linkiem tam, gdzie się ją ustawia), „Zobacz jak gość”, edycja informacji i wyglądu, komunikat, stół, lista prezentów, życzenia |
| S4 | „Co zabrać”, Muzyka, Fryzura i makijaż usuwały bez możliwości cofnięcia | usunięcie od razu z **„Cofnij”** w powiadomieniu (jak przy zadaniach); większe obiekty — okno potwierdzenia |
| S5 | „gospodarstwa” w interfejsie | „rodziny” |

## Część 2. Nowe funkcje

| # | Funkcja | Gdzie | Najważniejsze |
|---|---|---|---|
| N1 | Wyszukiwarka | lupa w nagłówku (w weselu) → `/szukaj` | zadania, goście (z rodziną), usługodawcy, wydatki; od 2 znaków; wynik otwiera zadanie w Planie, gościa na liście z filtrem, kartę usługodawcy |
| N2 | Plan wydatków | Budżet → „Plan wydatków” | płatności w każdym miesiącu (Wy / sponsorzy), po terminie, bez terminu, bez zaplanowanej płatności. Sugestia: ile odkładać miesięcznie po odjęciu deklaracji sponsorów; miesiąc szczytu wyróżniony |
| N3 | Koszt gościa | Budżet i Goście → Frekwencja | średnio na osobę oraz koszt każdej kolejnej dorosłej osoby i dziecka. Liczone wyceną wybranych ofert (z minimum sali i ceną dziecięcą) i pozycjami „za osobę”. Poniżej minimum sali kolejna osoba na przyjęciu nic nie kosztuje (poprawiny tak) |
| N4 | Lista prezentów | Strona gościa (para), strona z linku RSVP (gość) | rzecz rezerwuje jedno zaproszenie (równoczesna rezerwacja: druga dostaje 409); fundusz (np. podróż) bez kwot i rezerwacji; para widzi, kto wybrał; gość zwalnia tylko swoje; PL i EN |
| N5 | Wiadomości do usługodawców | karta usługodawcy → „Napisz do usługodawcy” | 5 sytuacji (zapytanie, rezerwacja, umowa i płatności, dzień ślubu, podziękowanie) z datą, liczbą gości, rodzajem ślubu i zdaniem pod rodzaj firmy; „Kopiuj” i „Otwórz w poczcie” (mailto) — aplikacja nic nie wysyła |
| N6 | Komentarze przy zadaniach | okno zadania → „Komentarze” | czytają role z odczytem planu, piszą role z zapisem; usuwa autor albo właściciel; w audycie bez treści |
| N7 | Podsumowanie dla rodziców | Więcej → „Podsumowanie dla rodziców” (`/druk/podsumowanie`) | jedna strona: termin i miejsca, goście z prognozą, budżet i wkład sponsorów, postęp zadań, najbliższe 2 tygodnie — do druku lub PDF |

## Weryfikacja

- Backend:
  - nowe testy: `test_budget_insights.py`, `test_search.py`, `test_gifts_comments.py`;
  - test IDOR obejmuje nowe trasy;
  - kontrakt Schemathesis — w pełnym przebiegu.
- Frontend:
  - testy jednostkowe: `round08.test.ts`;
  - E2E (8 profili, axe) dla: strony gościa z prezentami i rezerwacją, wyszukiwarki z komentarzem, planu wydatków i kosztu gościa
    z podsumowaniem dla rodziców, wiadomości do usługodawcy, „Cofnij” w Muzyce;
  - E2E zaktualizowane po zmianie nazwy „Fryzura i makijaż”.
- Pełny przebieg 22.10:
  - backend **1133 passed** (z kontraktem API) i vitest 139;
  - E2E dev 445 i produkcyjne 419 zaliczonych;
  - 3 starsze testy szukały usuniętego przycisku „Strona dla gości” i linku „Komunikat, stół i życzenia”. Po zmianie na
    „Strona gościa” zaktualizowane i zielone na dev (13/13) i buildzie produkcyjnym (29/29 z nowymi testami);
  - te 3 testy przekroczyły czas, więc ich tymczasowe wesela zostały w bazie E2E — usunięte (zostało tylko „Wesele demo”);
  - start aplikacji 142,8 KB gzip.
