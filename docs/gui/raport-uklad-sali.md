# Raport: układ sali i numery miejsc — plan dalszej pracy, A3

Data: 2026-10-21. Zawęża znane ograniczenie nr 29.

## Backend
- Migracja `7f3c1d5a9b02`: stół ma `pos_x`, `pos_y` (środek w metrach od lewego górnego rogu sali)
  i `rotation` (0–359°); nowa tabela `seating_rooms` (wymiary sali w metrach i elementy stałe:
  parkiet, scena, bar, wejście, bufet, inne — środek i wymiary w metrach), wersjonowana `If-Match`.
- `GET/PUT /weddings/{id}/seating/room`; plan stołów (`GET …/seating`) zwraca `room` i pozycje stołów.
- **Numery miejsc** (`engine.number_seats`, `POST …/seating/seat-numbers`): rodzina siedzi w ciągłym
  bloku krzeseł — najpierw dorośli (para obok siebie), potem dzieci (obok rodzica); stół okrągły
  „zawija się” (miejsce ostatnie sąsiaduje z 1). Ręcznie wpisane numery są zachowywane
  (`keep_existing`), można też ponumerować od nowa; `dry_run` = podgląd. Zapis bez kolizji
  z unikalnym indeksem (stół + miejsce).
- **„Blisko stołu pary / parkietu”** w automacie (`near_groups`, `near_target`): grupy gości
  (etykiety zaproszeń, np. „Rodzina Ani”) płacą w modelu CP-SAT za odległość stołu od celu
  (ranga odległości z planu sali, waga 3 na osobę i stopień). Gdy cel albo stoły nie mają pozycji —
  reguła pominięta, odpowiedź `near_applied: false` (GUI to wyjaśnia).
- Testy: jednostkowe numerowania (para, dzieci, zachowane numery, zawinięcie stołu, za dużo osób,
  zdublowane numery), API (sala z wersją i walidacją, pozycje stołów, numerowanie z podglądem,
  „blisko” z pozycjami i bez), IDOR dla nowych tras.

## GUI (`RoomLayout.tsx`, `SeatingView.tsx`, `PrintView.tsx`)
- Sekcja **„Układ sali”**: plan SVG w skali (stoły okrągłe/prostokątne/kwadratowe o rozmiarze
  z liczby miejsc, elementy sali). Stoły bez pozycji ustawiane wstępnie w siatce.
- Przeciąganie stołów myszą/palcem oraz **dostępna alternatywa**: wybór stołu z listy i przyciski
  „W lewo / W prawo / W górę / W dół” (co 0,5 m) i „Obróć” (45°), z ogłaszanym położeniem.
  Zmiany w szkicu → „Zapisz układ” (albo „Cofnij zmiany”).
- „Wymiary i elementy sali”: szerokość i długość, dodawanie/przesuwanie/usuwanie parkietu,
  sceny, baru, wejścia, bufetu.
- „Ponumeruj miejsca” w akcjach planu; numer miejsca przy osobie na karcie stołu.
- Automat: sekcja „Blisko (wg planu sali)” — wybór grup i celu (stół pary / parkiet).
- Wydruk **„Plan sali”** (`/druk/sala`: plan + liczba osób przy stołach) i **winietki z numerem
  miejsca**.
- Vitest `room.test.ts` (rozmiar stołu, domyślna siatka); E2E „Układ sali…” na 390 i 1280
  (jasny/ciemny, axe, bez poziomego przewijania): przesunięcie i obrót z klawiatury, zapis,
  parkiet, numery miejsc, wydruki.
- Uwaga z E2E: przycisk dodawania elementu nazywał się „Dodaj” jak inny na stronie — zmieniony na
  „Dodaj na plan” (jednoznaczny także dla czytnika ekranu).
