# Raport: strażnik waloryzacji cen

Data: 2026-10-22. Propozycja 1 z `docs/analysis/05-propozycje-nowych-funkcji.md`.
Migracja `b8d0f2a4c6e7` (kolumny `indexation`, `indexation_cap_percent`, `price_fixed_on`, `price_review_on`
w `budget_items`).

## Problem

Salę i zespół rezerwuje się 1,5–2 lata wcześniej. Umowy mają często klauzulę „cena wg wskaźnika inflacji GUS”
albo „wg cennika z roku wesela”, a para dowiaduje się o podwyżce na kilka miesięcy przed ślubem. Inne aplikacje
pokazują kwotę „na dziś”.

## Co zrobiono

- **Przy wydatku** (Budżet → wydatek → „Podwyżka ceny w umowie (waloryzacja)”): rodzaj klauzuli
  (cena stała / wg inflacji GUS / wg cennika z roku wesela / z limitem), limit łącznie w %, data ustalenia ceny
  i termin aneksu lub potwierdzenia ceny.
- **W budżecie karta „Podwyżki cen w umowach”**: trzy kwoty (dziś / z prognozowaną podwyżką / w najgorszym
  razie), lista pozycji z klauzulą i zakresem podwyżki („+4 100 zł … +8 400 zł”), ostrzeżenie o terminie aneksu
  w ciągu 30 dni. Założenia inflacji można zmienić (prognoza 3/5/7%, najgorszy przypadek 8/10/15% rocznie).
  Bez pozycji z klauzulą widać tylko podpowiedź, gdzie ją ustawić.
- **Podsumowanie e-mail**: sekcja „Ceny w umowach” z terminami aneksów w horyzoncie podsumowania.

## Model liczenia (`app/modules/budget/indexation.py`)

- Podwyżka obejmuje tylko **niezapłaconą** część pozycji (szacunek minus wpłaty).
- Lata = od daty ustalenia ceny (domyślnie dnia dodania pozycji) do dnia ślubu (albo 1. dnia planowanego miesiąca).
- Inflacja i cennik: `(1 + r)^lata − 1` (procent składany), r = założenie pary (domyślnie 5% i 10%).
- Limit: prognoza = mniejsza z dwóch wartości (inflacja albo limit), najgorszy przypadek = pełny limit (traktowany
  jako łączny, opisany tak w GUI).
- **Inflacja to założenie, nie dane GUS**. Nie pobieramy danych z zewnątrz (bez płatnych i zewnętrznych usług).
  W GUI jest prośba, by sprawdzić aktualny wskaźnik i zapis w umowie.

## API

- `GET /weddings/{id}/budget/indexation?expected_rate=0.05&worst_rate=0.10` (stopy 0–0,5).
- Pola waloryzacji w tworzeniu, edycji (PATCH z `If-Match`) i odczycie pozycji budżetu. Limit bez procentu
  daje 422 `budget.indexation_cap`.

## Weryfikacja

- Backend: `tests/api/test_indexation.py` (lata, procent składany, limit, brak daty, trzy warianty z zapłaconym
  zadatkiem, terminy aneksów, założenia, walidacja), trasa w `test_idor.py`.
- Frontend: `indexation.test.ts`. E2E „Budżet: podwyżka ceny w umowie i trzy warianty kosztu” zielony na 8 profilach.
- Całość: backend **864 passed**, vitest **112**, E2E dev **305 passed**, 1 niestabilny w pełnym przebiegu
  („Frekwencja…” na 768-light; po `--repeat-each=5` na 8 profilach 40/40 zielonych). Do obserwacji.
- Baza dev: kopia przed migracją `backups/wedding-20261022-011535-przed-waloryzacja.dump`.

## Pomysły na dalej

- Odczyt klauzuli waloryzacji z umowy przez AI (szkic do zatwierdzenia), gdy AI zostanie włączone.
- Wpisywanie przez parę aktualnego wskaźnika GUS (np. z komunikatu GUS) jako domyślnej prognozy dla wesela.
