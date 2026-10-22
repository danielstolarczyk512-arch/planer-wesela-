# Raport: po weselu

Data: 2026-10-22. Propozycja 10 z `docs/analysis/05-propozycje-nowych-funkcji.md`.
Nowy moduł `app/modules/aftercare`, migracja `e2a4c6d8f0b1` (tabele `deliverables`, `after_checks`).

## Problem

Po weselu aplikacje „się kończą”, a zostaje sporo spraw: dopłaty, termin oddania zdjęć i filmu z umowy
(fotografowie się spóźniają), zmiana nazwiska w dokumentach i instytucjach, podziękowania.

## Co zrobiono — Więcej → „Po weselu” (`/w/:id/po-weselu`, `AfterWeddingView.tsx`)

- **Rozliczenie:** niezapłacone płatności z terminami (oznaczenie „po terminie”) i link do płatności.
- **Od usługodawców:** zdjęcia, film i inne z terminem z umowy i usługodawcą. Stan: czeka / **spóźnienie
  N dni** / odebrane. Przy spóźnieniu przycisk **„Kopiuj przypomnienie”** z gotową, uprzejmą wiadomością
  („Dzień dobry, Foto Jan! Piszemy w sprawie: Zdjęcia… Zgodnie z umową termin minął…”). Aplikacja nic
  nie wysyła sama.
- **Zmiana nazwiska:** lista do odhaczenia (dowód osobisty, prawo jazdy, paszport, bank, pracodawca,
  ubezpieczenia, umowy i rachunki, inne konta). **Terminy tylko tam, gdzie podaje je gov.pl:** dla dowodu
  „orientacyjnie do” 120 dni po ślubie, bo dowód z nieaktualnym nazwiskiem jest unieważniany 120 dni od zmiany
  w PESEL (gov.pl, sprawdzone 2026-10-22). Prawo jazdy: obowiązek wymiany (gov.pl), bez terminu, bo strona
  go nie podaje. Przy pozycjach link do źródła.
- **Podziękowania:** postęp „Podziękowania za prezenty: 3 z 5” z listy gości.
- **Archiwum wesela:** pobranie wszystkich danych (JSON), z informacją o anonimizacji gości po 90 dniach.
- **Podsumowanie e-mail:** sekcja „Od usługodawców po weselu” z pozycjami po terminie.
- Przed ślubem strona działa z komunikatem, że przyda się później, a terminy z umów można wpisać od razu.

## API

`GET /weddings/{id}/after-wedding`; `POST /weddings/{id}/deliverables`, `PATCH|DELETE …/deliverables/{d}`
(PATCH z `If-Match`, także „odebrane”); `PUT /weddings/{id}/after-checks/{code}` `{done}`.

## Weryfikacja

- Backend: `tests/api/test_aftercare.py` (spóźnienie, rozliczenie, podziękowania, termin dowodu, odebrane
  z `If-Match`, odhaczanie, digest), trasy w `test_idor.py`. Eksport wesela zawiera nowe tabele.
- Frontend: `afterWedding.test.ts` (treść przypomnienia, zakładka). E2E „Po weselu: …” zielony na 8 profilach
  (axe, bez poziomego przewijania).
- Data „odebrane” liczona w czasie polskim (`todayInWarsaw`), nie w UTC.
- Całość: backend **926 passed**, vitest **120**, E2E dev **329 passed** + 1 niestabilny istniejący test
  („Harmonogram dnia…” 768-light; po `--repeat-each=5` 40/40).
- Baza dev: kopia przed migracją `backups/wedding-20261022-030121-przed-po-weselu.dump`.

## Do przeglądu przez prawnika

Lista zmiany nazwiska i teksty o terminach (`app/modules/aftercare/service.py`, `NAME_CHANGE`) razem z innymi
informacjami prawnymi (etap B).
