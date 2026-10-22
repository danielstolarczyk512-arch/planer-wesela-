# Raport GUI: krok 3 (nawigacja i widoki Dziś, Plan, Budżet, Goście)

Data: 2026-10-20. Zakres według [GUI-SPEC-v1.1](GUI-SPEC-v1.1.md), sekcja 11, krok 3.

## Wykonane działania

| Obszar | Co działa |
|---|---|
| **Nawigacja** | 5 zakładek: Dziś, Plan, Budżet, Goście, Więcej. Na telefonie pasek na dole z uwzględnieniem bezpiecznego obszaru, od 768 px pasek boczny. Aktywna zakładka ma kolor, tło ikony i pogrubienie, a nie sam kolor. Każda zakładka ma własny adres (`/w/{wesele}/plan` itd.): działają linki bezpośrednie, przeładowanie i przycisk Wstecz. Ponowne dotknięcie aktywnej zakładki przewija na górę. Treść przenika się (View Transitions), a pasek stoi w miejscu. |
| **Wejście** | Po zalogowaniu od razu otwiera się ostatnio używane wesele albo jedyne wesele. „Więcej → Wszystkie wesela” pokazuje listę. |
| **Dziś** | Odliczanie wg spec 2.4: dni z poprawną liczbą mnogą; przy samym miesiącu „ok. 9 miesięcy”; w dniu ślubu „Dziś”. Prawdziwy stan zamiast stałego hasła („8 zadań po terminie”). Trzy najbliższe zadania z odhaczaniem, przewidywany koszt („Ponad budżet”, gdy dotyczy), potwierdzeni goście z liczbą zaproszonych, najbliższa płatność (najpierw zaległe; rodzaj, termin, „za 12 dni” albo „Po terminie”). |
| **Plan** | Segmenty Teraz (po terminie i do 30 dni) / Później / Zrobione oraz filtr osoby, oba w adresie (przetrwają powrót). Grupy według miesięcy, pasek postępu, termin z pochodzeniem („z planu przygotowań”), status „Po terminie”. Odhaczenie: zmiana widoczna od razu, zadanie nie znika spod palca, „Cofnij” przez 6 s, a przy błędzie stan wraca z komunikatem. Dodawanie zadania w panelu z kluczem idempotencji. |
| **Budżet** | Przewidywany koszt na tle limitu (pasek z opisem „Wykorzystano 79%”, przekroczenie jako błąd z tekstem), wpłacono i do zapłaty, płatności zaległe i z 30 dni z „Oznacz zapłatę” po potwierdzeniu („aplikacja nie wykonuje przelewów”). Wydatki ze statusem słownym (Szacunek / Umowa / Zapłacone). Nowy wydatek: nazwa, kategoria (lista wyboru), kwota wymagana jako szacunek (wydatek bez kwoty liczyłby się jak 0 zł). |
| **Goście** | Liczby w kolorach statusów: będą, bez odpowiedzi, nie wiedzą, odmowy. „Brak odpowiedzi nie oznacza odmowy.” Wyszukiwanie po każdej osobie i rodzinie bez względu na polskie znaki („zielinska” znajdzie „Zielińska”), filtry w adresie. Karty rodzin rozwijają się do listy osób ze statusem na każde wydarzenie. „Odpowiedz za gościa” osobno na każde wydarzenie, z opcją „Nie wie”. Nowe zaproszenie: nazwa, osoby po przecinku, strona. |
| **Więcej** | Wygląd, wszystkie wesela, wylogowanie, rola użytkownika w weselu. |
| **Role** | Przy roli „Tylko podgląd” akcje zapisu są ukryte albo nieaktywne, z wyjaśnieniem. |
| **Dane demo** | `python -m scripts.seed --content`: fikcyjne zadania, wydatki z płatnościami i 5 zaproszeń z różnymi odpowiedziami (tylko środowisko deweloperskie). |

## Wyniki weryfikacji

| Kontrola | Wynik |
|---|---|
| Testy jednostkowe (Vitest) | **54 passed** (nowe: odliczanie, segmenty planu, terminy, wykorzystanie limitu, wyszukiwanie bez polskich znaków, brak odpowiedzi ≠ odmowa) |
| E2E na serwerze deweloperskim, 4 szerokości × 2 motywy | **112 passed** (nowe: wszystkie zakładki, adresy i Wstecz, odhaczenie z „Cofnij”, walidacja wydatku, wyszukiwanie i filtry gości) |
| E2E na buildzie produkcyjnym z CSP | **80 passed** |
| axe (WCAG 2.2 A/AA) na Dziś, Plan, Budżet (także z otwartym panelem), Goście (z rozwiniętą rodziną) | **0 naruszeń** po poprawkach |
| Bez poziomego przewijania przy 320 px | spełnione po poprawkach |
| Budżet JS na start | **136 KB** gzip (limit 170 KB); każda zakładka ładowana osobno |

**Błędy znalezione przez testy i poprawione:**
- karta płatności i przycisk zapłaty miały nazwę dla czytnika ekranu inną niż widoczny tekst (WCAG 2.5.3);
- długie statusy gości poszerzały ekran (52 px przy 390 px);
- siatka sekcji rosła ponad ekran przy 320 px (7 px);
- przycisk „Zapłacone” wyglądał jak status, więc ma teraz etykietę „Oznacz zapłatę”.

## Ograniczenia i kolejne kroki

- **Ustawienia wesela** (nazwa, data z podglądem przesunięć zadań, typ ceremonii, budżet, członkowie i zaproszenia partnera) nie mają jeszcze ekranu. API jest gotowe: zmianę daty prawdziwego wesela właściciela zrobiłem przez API (26 zadań przesuniętych).
- Edycja i usuwanie zadań, wydatków i gości (z potwierdzeniem zakresu) oraz link RSVP dla rodziny: kolejny krok.
- Krok 4: porównanie ofert z dialogiem skutków, odczyt umowy przez AI, plan stołów z automatem, harmonogram dnia, strona RSVP dla gości.
- Komunikat przeglądarki „Transition was aborted” przy bardzo szybkim przełączaniu zakładek pochodzi z View Transitions. Działanie jest poprawne: wygrywa ostatni wybór.
