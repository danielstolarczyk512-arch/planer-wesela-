# Raport: gość wybiera kurs autokaru w RSVP

Data: 2026-10-22. Usprawnienie z analizy (dalszy krok po propozycji 8 „Transport i noclegi”).
Migracja `f3b5d7e9a1c2` (kolumna `show_to_guests` w `transport_runs`).

## Problem

Po wprowadzeniu kursów para musiała sama przydzielać każdego gościa. Gość w RSVP mógł zaznaczyć tylko
„Potrzebuję transportu”, a para potem pytała, którym kursem pojedzie.

## Co zrobiono

- Przy kursie (Goście → Transport i noclegi) przełącznik **„Pokaż gościom w formularzu potwierdzenia”**
  i znacznik „Widoczny dla gości”.
- Na stronie RSVP, gdy gość zaznaczy „Potrzebuję transportu”, widzi sekcję „Przejazd zorganizowany przez parę”
  z udostępnionymi kursami (nazwa, dzień i godzina, trasa, **liczba wolnych miejsc**) i zaznacza swoje.
  Pełny kurs jest wyłączony („brak miejsc”). Po polsku i po angielsku.
- Zapis: wybór zastępuje miejsca gościa **tylko na udostępnionych kursach**. Przydziały pary na kursach
  ukrytych (np. „Bus dla dziadków”) zostają bez zmian. Wybór kursu ustawia też „potrzebuje transportu”.
- Gdy dwie osoby zapisują się jednocześnie na ostatnie miejsce, druga dostaje 409 `rsvp.transport_full`
  z prośbą o wybór innego kursu. Kurs ukryty albo z innego wesela daje 422 `rsvp.invalid_target`.

## Prywatność

Gość widzi tylko liczbę wolnych miejsc, bez nazwisk innych pasażerów. Kursy ukryte są dla gości niewidoczne.

## Weryfikacja

- Backend: `test_guest_picks_run_in_rsvp` w `tests/api/test_logistics.py` (widoczność, wybór, wolne miejsca,
  pełny kurs 409, kurs ukryty 422, przydział pary bez zmian, rezygnacja zwalnia miejsce).
- E2E: „RSVP: gość zapisuje się na kurs autokaru udostępniony przez parę” zielony na 8 profilach (axe, bez
  poziomego przewijania), a para widzi gościa na kursie.
- Całość: backend **933 passed**, vitest **120**, E2E dev **346 passed** bez błędów.
- Baza dev: kopia przed migracją `backups/wedding-20261022-042411-przed-rsvp-kursy.dump`.
