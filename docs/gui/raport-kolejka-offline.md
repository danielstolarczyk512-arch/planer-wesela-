# Raport: kolejka przesunięć programu bez sieci — plan dalszej pracy C2

Data: 2026-10-21. Rozszerza tryb dnia ślubu bez sieci (dokończenie v1.1, punkt 2).

## Działanie
- Bez sieci koordynator / para widzi w trybie na żywo „Przesuń bez sieci: „…” i późniejsze”
  (te same kroki: −30, −15, +15, +30, +60 min). Przesunięcie trafia do kolejki w `localStorage`
  (`src/lib/dayQueue.ts`) i **od razu** zmienia godziny na ekranie oraz w kopii programu
  (tak samo jak serwer: punkt i wszystko, co zaczyna się od jego godziny).
- Lista „Czeka na internet” z możliwością usunięcia pojedynczego przesunięcia.
- **Powrót sieci:** kolejka wysyła się po kolei (`POST /schedule/shift`). Przed każdym
  przesunięciem sprawdzamy na serwerze godzinę punktu: wysyłamy automatycznie tylko, gdy jest taka,
  jakiej oczekiwaliśmy (godzina z serwera po wcześniejszych przesunięciach z kolejki).
- **Konflikt** (ktoś w międzyczasie zmienił program albo usunął punkt): wysyłka staje,
  komunikat „Program zmienił się w międzyczasie” z godzinami i wyborem „Wyślij mimo to” /
  „Odrzuć”; po decyzji wysyłka pozostałych wznawia się.
- Błąd sieci przy wysyłce: komunikat i „Spróbuj ponownie” — bez automatycznego ponawiania w pętli.
- Kolejka znika przy wylogowaniu (razem z kopią programu); opis w polityce prywatności.
- Ograniczenie: na ekranie startowym bez sieci (sesja nieprzywrócona) program jest tylko do odczytu.

## Testy
- Vitest `lib/dayQueue.test.ts`: przesuwanie punktu i późniejszych, łańcuch przesunięć,
  zachowany czas trwania, warunek bezpiecznej wysyłki (zmieniona godzina, usunięty punkt),
  osobne wesela, czyszczenie bez ruszania innych kluczy.
- E2E „Dzień ślubu bez sieci: przesunięcie w kolejce…” (390 jasny, 1280 ciemny, axe): kolejka
  offline → automatyczna wysyłka po powrocie sieci (+15 min na serwerze, kolejka pusta);
  konflikt z przesunięciem innej osoby (+30) → „Odrzuć” → na serwerze tylko +30.
