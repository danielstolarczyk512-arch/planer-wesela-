# Plan stołów wg wzoru z paczki grafik

Układ strony Goście → „Plan stołów” przerobiony na wzór `wzor_nowej_strony_plan_stolow.png`.

- Nagłówek: „Usadź automatycznie” i „Dodaj stoły” po prawej, podsumowanie z separatorami.
- Rząd 3 kafelków: liczba stołów, wolne miejsca, osoby bez przypisania (klik przewija do listy).
- Kafelki stołów z ikonami i plakietką „0 z 10”; stół pary młodej wyróżniony (obrączki, narożniki).
- Układ sali: podwójna ramka, okna, rośliny w rogach, krzesła wokół stołów (okrągłe — po okręgu,
  prostokątne — po długich bokach, kwadratowe — po 4 bokach), łuk kwiatowy nad stołem pary młodej.
- Kształt (okrągły/prostokątny/kwadratowy) i liczba miejsc (= wielkość stołu na planie) edytowalne:
  przycisk „Kształt i wielkość stołu” pod planem sali albo klik w nazwę stołu na kafelku.
- Grafiki: `frontend/public/media/plan-stolow/*.webp` (źródło: ZRODLA.md).

Sprawdzone: `tsc`, `eslint`, vitest, E2E „Układ sali” i „Plan stołów” (1280 jasny, 390 ciemny, axe).
Niesprawdzone: pełne 8 profili, build produkcyjny i `check-budget.mjs`.
Świadome różnice od wzoru: brak ikon obrączek w środku stołu pary młodej, gdy go nie ma w danych; gałązka
tylko od 1500 px szerokości.

## Poprawka: stoły z grafik właściciela

Na planie sali stoły okrągłe i kwadratowe (zwykłe i pary młodej) to grafiki od właściciela
(`stol-goscie-*`, `stol-mlodych-*`); grafiki bez napisów (arkusz właściciela z 26.10),
nazwa stołu nakładana przez aplikację. Rozmiar grafiki wynika z rozmiaru blatu (`TABLE_ART` w `RoomLayout.tsx`).
Ograniczenia: na grafikach jest zawsze 8 krzeseł (niezależnie od liczby miejsc); stół prostokątny
rysowany wektorowo w kolorach grafik, bo kwadratowa grafika by się zniekształciła.

## Ozdoby sali i nazwy stołów

Tło planu sali to grafika właściciela `sala-tlo.webp` (podłoga z parkietem, ściany, kwiaty, światła),
rozciągnięta na wymiar sali; wcześniejsze osobne ozdoby, ramka i okna usunięte.
Nazwa stołu na planie widoczna dopiero po najechaniu myszą albo wybraniu stołu (CSS; nazwa jest też w `<title>`).

Stoły bez pozycji (`defaultPositions`) stoją domyślnie wokół parkietu z grafiki tła, z dala od ścian; para młoda
na środku nad parkietem; najpierw rząd przy górnej i dolnej ścianie. Plan sali zajmuje całą szerokość karty.
