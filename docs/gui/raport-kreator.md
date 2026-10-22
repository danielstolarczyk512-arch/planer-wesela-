# Raport: kreator pierwszego uruchomienia — plan dalszej pracy C3

Data: 2026-10-21.

## Co zmieniono
- „Nowe wesele” (i „Utwórz wesele” przy pustej liście) otwiera **kreator w 4 krokach** zamiast
  formularza z samą nazwą (`features/home/WeddingWizard.tsx`):
  1. nazwa i termin — data ślubu albo planowany miesiąc (najbliższe 36 miesięcy) albo „jeszcze
     nie wiemy”;
  2. ceremonia — kościelny, cywilny, inny wyznaniowy, humanistyczny, „jeszcze nie wiemy”
     (z krótką wskazówką, co to oznacza dla formalności);
  3. budżet i liczba gości (opcjonalnie, z walidacją);
  4. podsumowanie i „Utwórz wesele”.
- Po utworzeniu: plan zadań z szablonu `2027.1` dopasowany do ceremonii i terminu (zaległe
  rozkłada istniejący tryb nadrabiania), a przy podanym budżecie od razu **podział na kategorie**
  (`POST /budget/apply-split`). Błąd podziału nie blokuje startu (można go powtórzyć w Budżecie).
- Bez zmian w backendzie — kreator korzysta z istniejących pól wesela i endpointów.
- Każdy krok poza nazwą można pominąć; „Wstecz” zachowuje wpisane dane; zamknięcie z wpisanymi
  danymi pyta o porzucenie zmian (jak dotychczas).

## Testy
- Vitest `wizard.test.ts`: opcje miesięcy, walidacja liczby gości.
- E2E „Kreator nowego wesela…” (390 i 1280, jasny/ciemny, axe, bez poziomego przewijania):
  walidacja nazwy i liczby gości, wybór miesiąca i ceremonii, podsumowanie; po zapisie API
  potwierdza ceremonię, liczbę gości, miesiąc, plan zadań (> 20) i zaplanowane kategorie budżetu.
