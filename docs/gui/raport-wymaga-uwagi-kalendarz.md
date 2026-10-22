# Raport: „Wymaga uwagi” na ekranie Dziś i przypomnienia w kalendarzu

Data: 2026-10-22. Usprawnienia z analizy po zrobieniu propozycji z `docs/analysis/05`.

## Problem

Nowe funkcje (frekwencja, dokumenty, waloryzacja, potwierdzenia usługodawców, transport, zaproszenia, po weselu)
mają osobne ekrany. Para nie zagląda do wszystkich codziennie, więc ostrzeżenia łatwo przeoczyć. Terminy z nowych
modułów nie trafiały też do kalendarza ani do pliku ICS w telefonie.

## 1. „Wymaga uwagi” (ekran Dziś)

- `GET /weddings/{id}/attention` (`app/modules/overview/attention.py`): zbiera ostrzeżenia z modułów, sortuje
  (pilne, uwaga, do zrobienia) i zwraca do 8 pozycji z linkiem do ekranu:
  - frekwencja: termin ostatecznej liczby, minimum sali, plan przekroczony, RSVP po terminie, rezerwa po terminie;
  - dokumenty do ślubu: straci ważność przed ślubem, po zalecanym terminie;
  - terminy aneksów cenowych w ciągu 30 dni;
  - zdjęcia, film i inne po terminie;
  - na 14 dni przed ślubem: usługodawcy bez potwierdzenia aktualnego programu;
  - przepełnione kursy; braki transportu i noclegu (gdy są kursy lub pokoje);
  - zaproszenia osobiste do wręczenia przy terminie w ciągu 30 dni.
- Karta „Wymaga uwagi” (`AttentionCard.tsx`) pod odliczaniem. Każda pozycja jest linkiem do właściwego ekranu.
  Bez ostrzeżeń karta się nie pokazuje.
- Tylko odczyt, bez nowych danych. Rola z `READ` (koordynator dnia i sponsor nie mają ekranu Dziś, API zwraca 403).

## 2. Przypomnienia w kalendarzu i ICS

Nowy rodzaj wpisu `reminder` („Przypomnienie”, ikona dzwonka) w kalendarzu i pliku ICS:
- dokumenty do ślubu: „Od dziś: …” (najwcześniej) i „Najpóźniej: …”, dla niezałatwionych;
- „Aneks lub potwierdzenie ceny: Sala” (waloryzacja);
- „Termin oddania: Film” (po weselu; po odebraniu oznaczone jako zrobione);
- „Objazd z zaproszeniami (2)”: **liczba zaproszeń, bez nazwisk**. Plik ICS trafia do zewnętrznego kalendarza,
  więc obowiązuje zasada minimum danych.
- W widoku kalendarza przypomnienie jest linkiem do ekranu (np. Dokumenty do ślubu).
- Przy okazji funkcja `documents._overview` dostała publiczną nazwę `summary_for` (używa jej kalendarz).

## Weryfikacja

- Backend: `tests/api/test_attention.py` (zbieranie, kolejność, linki, 403 dla koordynatora),
  `tests/api/test_calendar_reminders.py` (wszystkie rodzaje przypomnień, link, brak nazwisk w kalendarzu i ICS).
- E2E: „Dziś: »Wymaga uwagi« zbiera ostrzeżenia i prowadzi do ekranu” zielony na 8 profilach. Pełny przebieg z tą
  zmianą: backend 931, E2E 338 bez błędów. Po dodaniu przypomnień: backend **932**, vitest **120**, E2E dev **338**
  bez błędów.
