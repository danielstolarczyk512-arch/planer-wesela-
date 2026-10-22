# Raport: portfel sponsorów i rola „sponsor”

Data: 2026-10-22. Propozycja 6 z `docs/analysis/05-propozycje-nowych-funkcji.md`.
Migracja `f6b8d0a2c4e5` (tabele `funders`, `funder_contributions`; kolumna `funder_id` w `payments`,
`wedding_members`, `wedding_invitations`; rola `sponsor` w ograniczeniach ról).

## Problem

W Polsce wesele często współfinansują rodzice obu stron („moi płacą za salę, twoi za zespół”).
Kto ile obiecał, co już zapłacił i co zostało do wyrównania, to zwykle rozmowy i kartki, a często
źródło napięć. Inne aplikacje znają tylko budżet pary.

## Co zrobiono

**Para: Budżet → „Kto płaci”** (`/w/:id/sponsorzy`, `FundersView.tsx`):
- sponsorzy (np. „Rodzice Panny Młodej”) ze stroną, obiecaną kwotą i notatką;
- dla każdego: obiecane, zapłacone firmom (płatności przypisane), przekazane parze (wpłaty), do zapłaty
  przez nich, pasek „ile obiecanej kwoty dotarło”, stan „Do rozpisania: 8 000 zł” albo „Ponad obietnicę”;
- szczegóły: przypisane płatności (pozycja, rodzaj, termin) i wpłaty z dodawaniem i usuwaniem;
- „Para” na dole: płatności bez sponsora;
- w formularzu płatności nowe pole **„Kto płaci”** (Para / sponsor). Pojawia się, gdy jest jakiś sponsor;
- usunięcie sponsora: jego płatności wracają do pary, wpłaty znikają (z potwierdzeniem).

**Rola „sponsor”** (Ustawienia wesela → osoby z dostępem → zaproszenie):
- przy zaproszeniu trzeba wskazać, czyj wkład osoba zobaczy (bez tego 422 `member.funder_required`);
- sponsor ma tylko zakładki „Nasz wkład” (`MyContributionView.tsx`) i „Więcej” (konto, wygląd, wszystkie wesela).
  Inne adresy przekierowują na „Nasz wkład”;
- sponsor **nie widzi** budżetu wesela (`total_budget` ukryty jak u koordynatora), gości, umów, planu ani
  wkładu innych sponsorów (API: 403). Widzi swoje liczby, płatności i wpłaty;
- e-mail zaproszenia dla sponsora ma osobny tekst: „…zaprasza Cię do podglądu Waszego wkładu…”;
- sponsor może sam opuścić wesele. Zmiana roli na inną usuwa powiązanie z wkładem.

## Zasady liczenia

- Zapłacone firmom = płatności `paid` z `funder_id`. Do zapłaty = `scheduled` z `funder_id`.
  Anulowane i zwrócone płatności się nie liczą.
- Przekazane parze = suma wpłat (`funder_contributions`).
- Do rozpisania = obiecane − (zapłacone + przekazane + do zapłaty). Wartość ujemna oznacza, że sponsorowi
  przypisano więcej, niż obiecał (ostrzeżenie, nie błąd).

## Uprawnienia (zmiana w całej aplikacji)

- Nowe akcje: `BASIC` (podstawowe dane wesela i opuszczenie wesela, każdy członek) i `FUNDER_SELF` (sponsor).
  `GET /weddings/{id}` i opuszczenie wesela wymagają teraz `BASIC` zamiast `DAY_READ`. Dla
  dotychczasowych ról nic się nie zmienia, bo wszystkie mają `BASIC`.
- `GET /weddings/{id}/my-contribution`: wkład przypisany do członkostwa. Bez przypisania 404
  `funder.not_assigned` (także dla pary).

## API

`GET|POST /weddings/{id}/funders`, `GET|PATCH|DELETE /weddings/{id}/funders/{f}` (PATCH z `If-Match`),
`POST /weddings/{id}/funders/{f}/contributions`, `DELETE …/contributions/{c}`, `GET /weddings/{id}/my-contribution`;
`funder_id` w płatnościach (POST/PATCH/odczyt), w zaproszeniach i w zmianie roli członka.

## Prywatność

- Nazwy sponsorów to zwykle opisy („Rodzice Panny Młodej”), kwoty to dane finansowe rodziny: są w eksporcie
  wesela (`budget.funders`, `budget.funder_contributions`) i znikają z weselem.
- Audyt: utworzenie, zmiana i usunięcie sponsora oraz wpłat (bez kwot w opisie zmian).

## Weryfikacja

- Backend: `tests/api/test_funders.py` (sumy, przypisanie płatności z `If-Match`, sponsor z innego wesela,
  usunięcie sponsora, rola sponsor: tylko własny wkład, 403 na budżet, gości, harmonogram i podsumowanie,
  ukryty budżet, zmiana roli wymaga sponsora), trasy w `test_idor.py`, migracja w testach (alembic).
- Frontend: `funders.test.ts` (stan obietnicy, procent, zakładki). E2E „Kto płaci: …” zielony na 8 profilach
  (axe, bez poziomego przewijania).
- Całość: backend **848 passed** (6 pominiętych), vitest **109**, E2E dev **290 passed** (78 pominiętych
  zgodnie z profilami), start aplikacji 141,6 KB gzip.
- Ręcznie w przeglądarce (środowisko E2E): testowe konto sponsora (zaproszenie przez Mailpit) widzi tylko
  „Nasz wkład” i „Więcej”. Próba wejścia do budżetu przekierowuje na wkład. Liczby zgadzają się z danymi.
  Wesele testowe usunięte, a usunięcie konta testowego zgłoszone (karencja jak dla każdego konta).
- Baza dev: kopia przed migracją `backups/wedding-20261022-001039-przed-funders.dump`.

## Ograniczenia

- Sponsor widzi tylko wkład. Nie może sam zgłosić wpłaty (para wpisuje ją po otrzymaniu). Można to dodać
  jako „zgłoś przelew” do potwierdzenia przez parę.
- Rolę sponsora nadaje się przy zaproszeniu. Zmiana roli istniejącego członka na sponsora jest w API, a w GUI
  nie (lista ról przy członku nie pokazuje „sponsor”, bo wymaga wyboru wkładu).

## Aktualizacja 2026-10-22 (później): podsumowanie e-mail dla sponsora i zgłaszanie przelewów

- Sponsor dostaje **własne podsumowanie** („Wesele: Wasze płatności”): tylko płatności przypisane jego wkładowi
  w najbliższych 7 dniach (i po terminie), z linkiem do „Nasz wkład”. Bez zadań, gości i płatności pary.
  Ustawienia (codziennie, co tydzień, wyłączone) jak dla każdego konta. Bez płatności nie ma e-maila.
- Zgłaszanie przelewu przez sponsora i potwierdzanie przez parę: raport `raport-usprawnienia-u4-u6.md`.
- Test: `test_sponsor_digest_only_own_payments` (`tests/api/test_cross_cutting.py`).
- **Kreator nowego wesela** (krok „Budżet i goście”): pola „Rodzice Panny Młodej” / „Rodzice Pana Młodego”
  dokładają się. Po utworzeniu wesela od razu powstają odpowiednie wpisy w „Kto płaci” (bez kwot). Błąd tego kroku
  nie blokuje startu, jak przy podziale budżetu. E2E „Kreator nowego wesela…” sprawdza sponsora.
