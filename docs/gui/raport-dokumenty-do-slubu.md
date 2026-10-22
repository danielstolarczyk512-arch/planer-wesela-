# Raport: licznik ważności dokumentów do ślubu

Data: 2026-10-22. Propozycja 7 z `docs/analysis/05-propozycje-nowych-funkcji.md`.
Migracja `a7c9e1b3d5f6` (tabela `ceremony_documents`).

## Problem

Dokumenty do ślubu mają okna ważności. Załatwione za wcześnie tracą ważność przed ślubem, załatwione za
późno nie zdążą. Szablon planu miał już zadania („Złóżcie w USC dokumenty”, lista dokumentów do ślubu
konkordatowego), ale nie liczył okien od daty ślubu ani nie sprawdzał dat wydania.

## Źródła (sprawdzone 2026-10-22)

| Zasada | Źródło |
|---|---|
| Ślub cywilny: ślub można zawrzeć po upływie miesiąca od złożenia zapewnienia; zapewnienie ważne 6 miesięcy | gov.pl „Weź ślub cywilny” |
| Ślub wyznaniowy (konkordatowy): zaświadczenie z USC ważne 6 miesięcy; „udajcie się do USC nie wcześniej niż 6 miesięcy przed ślubem” | gov.pl „Weź ślub wyznaniowy” |
| Świadectwo chrztu nie wcześniej niż 6 miesięcy przed ślubem; zgłoszenie w kancelarii 3 miesiące przed ślubem | przykład: Diecezja Tarnowska (wymagania parafii różnią się) |

## Co zrobiono

**Plan → „Dokumenty do ślubu”** (`/w/:id/formalnosci`, `CeremonyDocsView.tsx`). Lista zależy od rodzaju ślubu:
- **cywilny:** zapewnienie w USC (najwcześniej 6 miesięcy, najpóźniej 31 dni przed ślubem);
- **konkordatowy:** zaświadczenie z USC (6 miesięcy; najpóźniej 30 dni, bo parafia zwykle potrzebuje go
  wcześniej), świadectwo chrztu (domyślnie 6 miesięcy, **ważność do zmiany wg parafii**, np. 3),
  zgłoszenie w kancelarii (najpóźniej 3 miesiące przed ślubem, „Zrobione”);
- **wyznaniowy (inny):** zaświadczenie z USC; pozostałe wymogi zależą od związku wyznaniowego;
- humanistyczny / nieustalony: wyjaśnienie i link do ustawień.

Dla każdej pozycji: okno „Najwcześniej / Najpóźniej”, stan (za wcześnie, teraz, po zalecanym terminie, ważny do,
**straci ważność przed ślubem**, zrobione), wskazówka i **link do źródła**. Po wpisaniu daty wydania aplikacja liczy,
do kiedy dokument jest ważny. Gdy wypada to w dniu ślubu albo wcześniej, pokazuje ostrzeżenie. Gdy znany jest
tylko miesiąc ślubu, terminy liczone są od 1. dnia miesiąca (z komunikatem).

**Podsumowanie e-mail (digest):** nowa sekcja „Dokumenty do ślubu”, tylko gdy trzeba coś zrobić (po terminie
albo straci ważność przed ślubem).

## Poprawka bezpieczeństwa przy okazji (z propozycji 6)

E-mailowe podsumowanie wykluczało tylko koordynatora dnia, więc **sponsor dostałby zadania i płatności całego
wesela**. Teraz pomija też rolę `sponsor` (test `test_digest_skips_sponsor_and_lists_documents`). Inne
miejsca z rolami wymienionymi z nazwy sprawdzone: zostało tylko ukrycie budżetu w `wedding_to_dict`
(już obejmuje sponsora).

## API

- `GET /weddings/{id}/ceremony-documents`: lista dla rodzaju ślubu, okna, stany, źródła.
- `PUT /weddings/{id}/ceremony-documents/{code}` `{issued_on, done, valid_months}`. Ważności z przepisów
  nie można zmienić (422 `ceremony_document.validity_fixed`), a spotkanie w parafii nie ma daty wydania
  (422 `ceremony_document.no_issue_date`).

## Zastrzeżenie

To informacja, nie porada prawna: w GUI jest dopisek, że wymagania parafii się różnią i trzeba je potwierdzić
w USC i kancelarii. Zasady są w kodzie (`app/modules/planner/documents.py`, `RULES`) i trzeba je przeglądać
przy zmianie przepisów. **Do przeglądu przez prawnika razem z regulaminem** (etap B).

## Weryfikacja

- Backend: `tests/api/test_ceremony_documents.py` (miesiące na końcu miesiąca, okna, wygaśnięcie,
  listy cywilny/konkordatowy, ważność wg parafii, błędy 422/404, rola podglądu), digest w
  `test_cross_cutting.py`, trasy w `test_idor.py`.
- Frontend: `ceremonyDocs.test.ts`. E2E „Dokumenty do ślubu: …” zielony na 8 profilach. Na 320 i 390 px
  wychwycił wychodzenie długich etykiet stanu poza ekran, a na 768 px zasłonięty przycisk. Oba poprawione
  (`section-head--wrap`, przycisk w osobnym wierszu).
- Całość: backend **859 passed** (6 pominiętych), vitest **111**, E2E dev **298 passed**, start 141,6 KB gzip.
- Baza dev: kopia przed migracją `backups/wedding-20261022-004114-przed-dokumenty.dump`.
