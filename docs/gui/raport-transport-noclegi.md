# Raport: transport i noclegi gości

Data: 2026-10-22. Propozycja 8 z `docs/analysis/05-propozycje-nowych-funkcji.md`.
Nowy moduł `app/modules/logistics`, migracja `d1f3b5c7e9a0` (tabele `transport_runs`, `transport_seats`,
`lodging_rooms`, `room_guests`).

## Problem

Autokar z kościoła na salę, kursy powrotne o 1:00 dla starszych i o 4:00 dla reszty, pokoje dla gości z daleka.
Przewoźnik i hotel dostają listy z Excela, które dezaktualizują się po pierwszej zmianie RSVP. Konkurencja zbiera
w RSVP tylko „potrzebuję transportu / noclegu”.

## Co zrobiono

**Goście → „Transport i noclegi”** (`/w/:id/logistyka`, `LogisticsView.tsx`):
- **Kursy:** nazwa, rodzaj (na wesele / powrót / inny), dzień i godzina odjazdu, skąd–dokąd, liczba miejsc,
  przewoźnik (usługodawca z kategorii „Transport”). Lista pasażerów wybierana z gości, na górze ci, którzy
  zaznaczyli potrzebę transportu. Znacznik „12/50 miejsc” albo **„Przepełniony o 3”**.
- **Kurs powrotny a program:** jeśli kurs odjeżdża przed punktami programu dla gości (np. tortem), widać
  ostrzeżenie „Odjeżdża przed: Tort (23:30)…”.
- **Noclegi:** pokoje (obiekt, pokój, miejsca, zameldowanie i wymeldowanie, liczba nocy, kto płaci) i goście
  w pokojach. Nie da się wpisać więcej osób niż miejsc, a przeniesienie gościa usuwa go z poprzedniego pokoju.
- **Kto jeszcze bez przydziału:** „Bez kursu: Ala, Ola” i „Bez pokoju: …” (goście z potrzebą, którzy nie
  odmówili). Przy pasażerach i lokatorach, którzy odmówili, jest dopisek „(odmówił)”.
- **Lista pokoi dla hotelu:** CSV (polski Excel): obiekt, pokój, miejsca, daty, noce, osoby, kto płaci.
  Bez diet i kwot. Pobieranie z tokenem sesji (`downloadAuthorized`), bez tokenu w adresie.
- **Link przewoźnika:** na jego linku z programem dnia (`/dzien/:token`) pojawiają się jego kursy z godziną,
  trasą i **liczbą osób, bez nazwisk**.

## API

`GET /weddings/{id}/logistics`; `POST/PATCH/DELETE /weddings/{id}/transport-runs[/{run}]` (PATCH z `If-Match`),
`PUT …/transport-runs/{run}/guests`; `POST/PATCH/DELETE /weddings/{id}/lodging-rooms[/{room}]`,
`PUT …/lodging-rooms/{room}/guests` (422 `lodging_room.too_many`, `lodging_room.nights`);
`GET /weddings/{id}/lodging/rooming.csv`; `GET /day/{token}` ma nowe pole `transport`.

## Prywatność

- Przewoźnik widzi tylko liczby. Imiona trafiają tylko do listy pokoi, którą para sama pobiera i przekazuje
  hotelowi (audyt `export_rooming`).
- Kursy i pokoje są w eksporcie wesela. Imiona pochodzą z listy gości, więc anonimizują się razem z nią.

## Przy okazji

- **Rejestr modeli (`app/models.py`) uzupełniony** o wszystkie tabele z ostatnich zmian oraz o wcześniej pominięte
  `SeatingRoom`, `SeatingAutoRun`, `UserMfa`, `MfaRecoveryCode`. Bez tego autogenerowana migracja Alembic
  mogłaby uznać te tabele za zbędne. Sprawdzone skryptem: wszystkie zmapowane klasy są w rejestrze.
- Schemat `RoomOut` z noclegów kolidował z planem sali, więc nazwy schematów noclegów to `LodgingRoom*`.

## Weryfikacja

- Backend: `tests/api/test_logistics.py` (przepełnienie, kurs powrotny przed tortem, braki, link przewoźnika bez
  nazwisk, `If-Match`, pokoje: daty, limit miejsc, przeniesienie, CSV, obcy gość 404), trasy w `test_idor.py`.
- Frontend: `logistics.test.ts` (zajętość, czas polski → UTC, zakładka). E2E „Transport i noclegi: …” zielony
  na 8 profilach.
- Uwaga z testów: kliknięcie w pole wyboru w trakcie animacji otwierania panelu nie zaznacza go. Test czeka
  teraz na zaznaczenie. Na tę animację warto zerknąć przy testach z parami.
- Całość: backend **909 passed**, vitest **118**, E2E dev **322 passed**, start 141,6 KB gzip, licencje OK.
- Baza dev: kopia przed migracją `backups/wedding-20261022-022423-przed-logistyka.dump`.

## Ograniczenia i dalej

- Gość nie wybiera kursu w formularzu RSVP: przydziela para. To możliwy kolejny krok: lista kursów
  w RSVP, gdy para je opublikuje.
- Brak osobnego linku dla hotelu: lista pokoi jest jako plik CSV.
