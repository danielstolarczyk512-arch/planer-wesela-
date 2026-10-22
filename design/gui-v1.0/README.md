# Nasz dzień — pakiet GUI premium

Przygotowano 19.10.2026 na podstawie dwóch wybranych stylów: jasnej elegancji oraz wieczorowego luksusu.

## Od czego zacząć

1. Otwórz `INSTRUKCJA-GUI.html` w przeglądarce — czytelna instrukcja z obiema referencjami i odnośnikami do ekranów.
2. Porównaj te same ekrany w `wizualizacje/jasny/` i `wizualizacje/ciemny/`.
3. Wykonawcy przekaż cały ZIP i `specyfikacja/PROMPT-WDROZENIOWY.md`.

## Zawartość

- `referencje/`: 2 wybrane obrazy źródłowe, bez zmian.
- `wizualizacje/`: 20 PNG, po 10 ekranów na motyw. Rozdzielczość: 1200 × 2160 px.
- `specyfikacja/GUI-SPEC.md`: wygląd, układ, logika interakcji, zachowanie, animacje, dostępność.
- `specyfikacja/design-tokens.json`: kolory, typografia, przestrzeń i komponenty.
- `specyfikacja/motion-tokens.json`: czasy, krzywe i wariant ograniczonego ruchu.
- `specyfikacja/CHECKLISTA-ODBIORU.md`: scenariusze do sprawdzenia po wdrożeniu.
- `specyfikacja/PROMPT-WDROZENIOWY.md`: instrukcja dla wykonawcy lub AI piszącego aplikację.
- `specyfikacja/kontrast-tokenow.json`: obliczone kontrasty wybranych par tokenów; nie jest audytem całego GUI.

## Dziesięć ekranów

01 Dziś; 02 Budżet; 03 Porównanie ofert; 04 Sprawdzenie umowy; 05 Plan; 06 Goście; 07 Stoły; 08 Noclegi i transport; 09 Dzień wesela; 10 Zaproszenie / RSVP.

## Jak interpretować projekt

Rekomendacja: dwa motywy jednej aplikacji, przełączane w ustawieniach. To propozycja do akceptacji. Zachowano oba wybrane style, a w rozszerzonym zestawie ujednolicono strukturę informacji. Ramka telefonu nie jest elementem aplikacji.

Wizualizacje są statyczne. Instrukcja opisuje animacje, lecz paczka nie zawiera interaktywnego prototypu ani produkcyjnego GUI. Przy implementacji nie należy kopiować drobnych napisów z PNG: obowiązują rozmiary i wymagania ze specyfikacji, nawet jeśli oznacza to przewijanie ekranu. Nazwa, osoby, firmy i kwoty są przykładowe. Nie dołączono kodu backendu, bibliotek ani plików fontów.
