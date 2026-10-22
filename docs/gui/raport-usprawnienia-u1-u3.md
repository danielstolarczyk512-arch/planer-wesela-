# Raport: usprawnienia U1–U3 z analizy 06

Data: 2026-10-22. Plan: `docs/analysis/06-analiza-po-rozbudowie.md`.

## U1. Frekwencja w podsumowaniu e-mail

- Nowa sekcja „Frekwencja i sala” w podsumowaniu dziennym lub tygodniowym: termin podania sali ostatecznej
  liczby (zbliża się albo minął), prognoza poniżej minimum sali (z kwotą), ostrożna prognoza ponad plan, zaproszenia
  po terminie RSVP.
- `guests/forecast.py`: obliczenia wydzielone do `compute()` (bez autoryzacji, dla zadania workera), a `build()`
  dalej sprawdza uprawnienia. `digest_lines()` zwraca tylko alerty wymagające działania.
- Test: `test_digest_lists_attendance_alerts` (`tests/api/test_cross_cutting.py`).

## U2. Kursy na ekranie Dzień (także koordynator dnia)

- `GET /weddings/{id}/day-transport` (uprawnienie `DAY_READ`): godzina, nazwa, trasa, liczba osób i miejsc,
  **bez nazwisk**. Świadek prowadzący dzień widzi odjazdy, ale nie listę gości (pełny widok `/logistics` nadal
  wymaga `READ`, dla koordynatora 403).
- Sekcja „Kursy” w Harmonogramie dnia (`DayTransport.tsx`), przy przepełnieniu znacznik błędu.
- Testy: `test_coordinator_sees_day_transport_without_names`, E2E „Transport i noclegi” sprawdza ekran Dzień.

## U3. Wydruk listy objazdu z zaproszeniami

- `/w/:id/druk/objazd`: dla każdej miejscowości tabela z niewręczonymi zaproszeniami (liczba osób, kto wręcza,
  plan) i rubryką ☐ do odhaczenia. Miejscowość nie dzieli się między strony. Przydaje się w trasie bez zasięgu.
- Link „Wydrukuj listę na objazd” na ekranie Zaproszenia, gdy są niewręczone zaproszenia osobiste.
- E2E „Zaproszenia: objazdy…” sprawdza wydruk (po wręczeniu Babci jej wiersza już nie ma).

## Weryfikacja

Testy celowane zielone (backend 358 w modułach transportu i IDOR, E2E 16 na 8 profilach). Pełny przebieg:
backend **938 passed**, vitest **120**, E2E dev **346 passed** bez błędów.
