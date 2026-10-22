# Raport: prognoza frekwencji i lista rezerwowa

Data: 2026-10-21. Propozycja 3 z `docs/analysis/05-propozycje-nowych-funkcji.md`.
Migracja `d4f6b8a0c2e1` (tabela `reserve_entries`).

## Co zrobiono

**Ekran „Goście → Frekwencja”** (`/w/:id/frekwencja`, `AttendanceView.tsx`):

1. **Prognoza na przyjęcie:** „ok. 44 osoby”, a do tego zakres „od 39 do 48 osób (przedział ok. 90%)”,
   podział na potwierdzonych, oczekujących, „może” i odmowy, liczba dzieci, porównanie z planowaną
   liczbą gości. Założenia można zmienić w „Założeniach prognozy” (ile osób bez odpowiedzi
   i ile z odpowiedzią „może” przyjdzie).
2. **Sala i ostateczna liczba:** dla każdej wybranej oferty z minimalną liczbą gości pokazujemy, ilu osób
   brakuje do minimum, i koszt pustych miejsc (wycena oferty z minimum minus bez minimum, więc uwzględnia też
   opłatę serwisową %), w wariancie prognozy i w ostrożnym. Termin pochodzi z zadania z szablonu
   „Przekażcie sali ostateczną liczbę gości” (`final_guest_count`). Jeśli para zmieni termin w planie,
   prognoza go użyje.
3. **Po terminie odpowiedzi:** gospodarstwa po terminie RSVP, które jeszcze nie odpowiedziały (do 20, od najstarszego terminu).
4. **Lista rezerwowa:** osoby do zaproszenia, gdy zwolni się miejsce, w kolejności ustalonej przez parę
   (strzałki „wyżej/niżej”: bez przeciągania, dostępne z klawiatury). Aplikacja podpowiada, kogo można zaprosić
   („Można zaprosić”): kolejne osoby, które mieszczą się w wolnych miejscach liczonych **od górnej granicy
   prognozy**, żeby nie przekroczyć liczby miejsc. „Zaproś” tworzy zwykłe zaproszenie (gospodarstwo z gośćmi)
   w jednej transakcji. Potem można dodać nazwiska i diety oraz wysłać link RSVP.
5. **Alerty:** zbliża się termin ostatecznej liczby (≤ 21 dni), a są osoby bez odpowiedzi; termin minął;
   prognoza poniżej minimum sali (z kwotą); nawet ostrożna prognoza powyżej planu; zaproszenia po terminie RSVP;
   minął zalecany termin zapraszania z rezerwy.

## Model prognozy (bez AI, deterministycznie, `app/modules/guests/forecast.py`)

- Potwierdzeni = 1, odmowy = 0, „bez odpowiedzi” = p (domyślnie 85%), „może” = q (domyślnie 50%).
  **To założenia pary, a nie dane historyczne** — tak jest to opisane w GUI.
- Gospodarstwo decyduje zwykle wspólnie, więc jego oczekujący to jedna decyzja z wagą n:
  wariancja Σ n²·p·(1−p). Przedział ±1,645σ (ok. 90%) przycięty do wartości możliwych.
- Niemowlęta są poza liczbami, a nastolatki liczą się jak dorośli, tak samo jak w wycenie ofert
  (`offers/pricing.py`). Minimum sali porównujemy z dorosłymi, bo tak liczy wycena.
- Gdy wesele ma kilka wydarzeń „przyjęcie”, liczy się „najlepszy” status gościa. Bez przyjęcia brane są
  wszystkie wydarzenia, a bez wydarzeń wszyscy są „bez odpowiedzi”.
- Termin zapraszania z rezerwy: 6 tygodni przed ślubem, ale najpóźniej tydzień przed terminem podania
  ostatecznej liczby. To reguła zwyczajowa, nie przepis.

## API

- `GET /weddings/{id}/attendance-forecast?pending_rate=0.85&maybe_rate=0.5`: prognoza, sala, termin, alerty,
  propozycje z rezerwy (odczyt: także rola „tylko podgląd”).
- `GET|POST /weddings/{id}/reserve`, `PATCH|DELETE /weddings/{id}/reserve/{entry}` (PATCH z `If-Match`,
  `position` przenumerowuje kolejkę), `POST /weddings/{id}/reserve/{entry}/invite` (tworzy gospodarstwo,
  ponowne zaproszenie daje 409 `reserve.already_invited`; Idempotency-Key jak w innych POST).

## Prywatność (RODO)

- Lista rezerwowa to imiona/opisy wpisane przez parę: ten sam zakres co lista gości, bez kontaktów i diet.
- Jest w eksporcie wesela (`reserve_list`) i **usuwana w całości** razem z anonimizacją gości 90 dni po weselu.
- Usunięcie wpisu nie usuwa zaproszonego już gospodarstwa. Audyt zapisuje utworzenie, zmianę (tylko nazwy pól),
  usunięcie i zaproszenie.
- Rezerwowi nie trafiają do budżetu, planu stołów, linku dla sali ani statystyk, dopóki nie zostaną zaproszeni
  (osobna tabela, nie flaga w gospodarstwach, więc żaden istniejący licznik się nie zmienił).

## Weryfikacja

- Backend: `ruff`, `mypy` OK; `pytest` **806 passed**, 6 skipped (nowe: `tests/unit/test_forecast.py`,
  `tests/api/test_reserve_forecast.py`, trasy w `test_idor.py`).
- Frontend: `tsc`, `eslint` OK; `vitest` **103** (nowe `attendance.test.ts`, nawigacja „frekwencja” → Goście);
  budżet startu 141,6 KB gzip (ekran ładowany leniwie); licencje OK (bez nowych zależności).
- E2E: nowy test „Frekwencja: …” zielony na 8 profilach (320/390/768/1280 × jasny/ciemny, axe, bez poziomego
  przewijania). Pełny przebieg E2E dev: **274 passed**, 78 pominiętych (testy przypisane do wybranych profili), bez błędów.
- Ręcznie w przeglądarce (środowisko E2E, tymczasowe wesele usunięte po teście): prognoza, alerty,
  zaproszenie dwóch osób z rezerwy (prognoza wzrosła z 44 do 46), przesuwanie w kolejce, układ na 320 px.
- Baza dev: kopia przed migracją `backups/wedding-20261021-224641-przed-reserve.dump`; migracja tylko dodaje
  tabelę, wesele właściciela nietknięte.

## Ograniczenia i pomysły na dalej

- Domyślne 85% i 50% to założenia. Po pierwszych weselach w aplikacji można by je kalibrować na
  zanonimizowanych, zagregowanych danych, ale **tylko za zgodą i po decyzji prawnej** (dziś nie agregujemy
  danych między weselami).
- Podsumowanie e-mail (digest) nie ma jeszcze alertów frekwencji. Ma już termin zadania „ostateczna liczba”
  i terminy RSVP.
- Pojemność sali (maksimum miejsc) nie jest modelowana osobno: wolne miejsca liczymy od planowanej liczby gości.
- „Dziś” nie pokazuje jeszcze karty frekwencji. Można ją dodać, jeśli właściciel uzna to za ważne.
