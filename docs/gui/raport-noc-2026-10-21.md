# Raport z pracy samodzielnej — noc 20/21 października 2026

Praca za zgodą właściciela („masz moją zgodę na co potrzebujesz”). Bez decyzji biznesowych
i prawnych (dopłata przy wyborze oferty, ceny Premium, hosting, prawnik) — te czekają na właściciela.
Prawdziwe wesele właściciela nietknięte; testy przeglądarkowe działają od tej nocy na osobnej bazie.

## Co powstało (commity od `42bcc90` do `35683fa`)

| Obszar | Co | Raport |
|---|---|---|
| Porządki (A5) | Usunięto 300 wesel „Obciążenie N” z testów obciążenia (przez API, tylko konta `loadtest-*`, po pełnej kopii `backups/wedding-20261020-223443.dump`); test obciążenia sprząta po sobie; ponowny pomiar: 6826 żądań, 0 błędów | `docs/wdrozenie.md` §9 |
| Bezpieczeństwo danych | **Osobne środowisko E2E** (baza `wedding_e2e`, API 8011) — testy nie logują się już do bazy z Twoim weselem | `CLAUDE.md` |
| Kreator (C3) | „Nowe wesele” w 4 krokach: termin, ceremonia, budżet i goście → plan zadań i podział budżetu | `raport-kreator.md` |
| Dzień ślubu (C2) | Przesunięcia programu bez sieci czekają w kolejce na telefonie i wysyłają się po powrocie sieci; gdy ktoś w międzyczasie zmienił program — pytanie „Wyślij mimo to / Odrzuć” | `raport-kolejka-offline.md` |
| Budżet | Cena dziecięca w pozycjach „za osobę” (ogr. 13) | — |
| Dokumenty | Wyszukiwanie w treści (także skanów), bez polskich znaków, z fragmentem i stroną (ogr. 21) | — |
| Stoły | Nastolatki przy stole dziecięcym na życzenie (ogr. 31); **automat liczy w workerze** zamiast blokować API (ogr. 30) | — |
| AI | Deterministyczny odczyt zadatku/zaliczki, gdy model go pominie (ogr. 32) | — |
| Hasła | Polskie słowa w ocenie siły hasła (ogr. 1) | — |
| Goście | „Zobacz jak gość” — podgląd strony RSVP z fikcyjną rodziną; **lista gości do Excela (CSV)** z opcjonalnymi uwagami dietetycznymi (z audytem); **strona gościa i e-mail RSVP po angielsku** (język zaproszenia) | `raport-strona-gosci-en.md` |
| Dziś | Wygląd odliczania (B3): przełącznik „Pokaż w tygodniach / miesiącach / dniach” na kafelku odliczania; miesiące liczone kalendarzowo w czasie polskim (31.01 + 1 miesiąc = ostatni dzień lutego); wybór w `localStorage` (`wp.countdown`), widoczny tylko przy znanej dacie i ≥ 7 dniach do ślubu | `TodayView.tsx` |
| Wydruki | Kolor przewodni (B2): akcent wybrany dla strony gości zabarwia imiona i górną krawędź winietek oraz kart z kodem QR; na ekranie wersja dla motywu (kontrast AA), w druku zawsze jasna | `PrintView.tsx`, `print.css` |
| Dokumenty | Wyszukiwanie z odmianą słów (ogr. 21): odcięcie typowych końcówek rzeczowników i przymiotników („sali” → „sala”, „złotej jesieni” → tytuł „Złota Jesień”), każde słowo zapytania musi wystąpić, w dowolnej kolejności | `documents/service.py` |
| Budżet | Budżet do Excela (CSV): pozycje kosztowe albo harmonogram płatności, kwoty z przecinkiem (polski Excel liczy sumy), ochrona przed formułami; wspólny moduł `app/core/spreadsheet.py` z eksportem gości | `BudgetView.tsx` |
| Pliki | Sprzątanie osieroconych plików partiami po 500 kluczy (ogr. 20 zamknięte) — bez ładowania listy wszystkich kluczy do pamięci workera | `documents/service.py` |
| Poprawki | Limit RSVP na IP w konfiguracji (`WP_RSVP_RATE_LIMIT`), czytelny komunikat przy 429; automat stołów: rollback sesji przy nieprzewidzianym błędzie solvera | — |

Wcześniej tego dnia (zgodnie z planem dalszej pracy): A1 ClamAV, A4 e-maile HTML, A3 układ sali
i numery miejsc, A2 HEIC (wariant bez zależności), A7 przegląd przed wdrożeniem.

## Weryfikacja
Ostatni pełny przebieg: backend 774 zaliczone, vitest 100, E2E dev 266, E2E produkcyjne (z CSP) 240 —
bez błędów; start aplikacji 141,5 KB gzip (limit 170 KB). Każda funkcja ma testy API/jednostkowe i E2E (axe, brak poziomego przewijania).

## Czeka na Ciebie
1. **A6:** czy „Wybieram tę ofertę” ma liczyć dopłatę jak „co jeśli” (suma − kwoty stałe).
2. **A2:** test na iPhonie — czy zdjęcie z galerii trafia jako JPG.
3. **Etap B:** hosting, prawnik (regulamin, polityka, RODO — w tym nr 37 i 41), ceny i bramka Premium.

## Do obserwacji
- Limit publicznego RSVP na adres IP (60 na 10 minut) jest teraz w konfiguracji
  (`WP_RSVP_RATE_LIMIT`); środowisko E2E ma 2000, bo wszystkie testy idą z jednego adresu.
  Na produkcji warto obserwować, czy goście z jednej sieci (np. sala, hotel) nie trafiają na limit;
  strona pokazuje wtedy czytelny komunikat zamiast „Link nie działa”.
- W buildzie produkcyjnym E2E rzadko (ok. raz na pełny przebieg, nie przy każdym) pierwsze
  wczytanie `/logowanie` nie renderuje formularza w limicie czasu; po powtórzeniu OK. Nie występuje
  w dev. Do sprawdzenia na docelowym serwerze.
