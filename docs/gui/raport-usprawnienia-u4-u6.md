# Raport: usprawnienia U4 i U6 z analizy 06

Data: 2026-10-22. Plan: `docs/analysis/06-analiza-po-rozbudowie.md`. Migracja `a4c6e8f0b2d3`
(kolumna `status` w `funder_contributions`).

## U4. Sponsor zgłasza przelew, para potwierdza

- Widok sponsora „Nasz wkład”: formularz **„Zgłoś przelew dla pary”** (kwota, notatka). Zgłoszenie ma status
  `reported` i **nie liczy się do „przekazane parze”**, dopóki para go nie potwierdzi. Sponsor widzi „Zgłoszone
  przelewy czekają na potwierdzenie pary: 3 000 zł” i znacznik przy wpłacie.
- Para (Budżet → Kto płaci): w karcie sponsora „Zgłosili przelew … — potwierdźcie po otrzymaniu”, a przy wpłacie
  przycisk **„Potwierdź”**. Odrzucenie to usunięcie wpłaty (istniejący przycisk).
- „Wymaga uwagi” na ekranie Dziś: „Rodzice: zgłoszony przelew 4 000 zł — potwierdźcie po otrzymaniu”.
- API: `POST /weddings/{id}/my-contribution/reports` (rola sponsor; para bez przypisanego wkładu dostaje 404),
  `POST /weddings/{id}/funders/{f}/contributions/{c}/confirm` (para; sponsor dostaje 403). W podsumowaniu
  sponsora nowe pole `reported`.
- Testy: `test_sponsor_reports_transfer_couple_confirms`. Ręcznie (środowisko E2E, testowe konto sponsora,
  posprzątane): zgłoszenie 3 000 zł widoczne z „Czeka na potwierdzenie”.

## U6. Kurs i pokój przy gościu

- W edycji gościa (lista gości) wiersz: „Kurs: Autokar z dworca. Pokój: Hotel przy sali, 12.” albo „Bez kursu.
  Bez pokoju.” i link do Transportu i noclegów. Pokazuje się tylko, gdy wesele ma jakieś kursy lub pokoje.
  Dane z istniejącego `GET /logistics` (wspólny cache z ekranem transportu).

## Weryfikacja

Pełny przebieg: backend **945 passed**, vitest **120**, E2E dev **346 passed** bez błędów.
