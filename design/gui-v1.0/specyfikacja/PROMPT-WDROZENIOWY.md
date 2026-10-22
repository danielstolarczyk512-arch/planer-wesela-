# Prompt dla wykonawcy GUI

Pracujesz nad komercyjną aplikacją ślubną „Nasz dzień” dla Polski. Przeczytaj GUI-SPEC.md, design-tokens.json, motion-tokens.json oraz CHECKLISTA-ODBIORU.md. Obejrzyj referencje i odpowiadające im ekrany w obu motywach. Traktuj makiety jako projekt wizualny, a specyfikację i dostępność jako reguły nadrzędne. Nie pomniejszaj tekstu, aby odtworzyć dokładnie wszystkie informacje na jednej wysokości telefonu.

Najpierw przeanalizuj istniejący projekt, architekturę, API, routing i biblioteki. Opisz krótko plan integracji oraz realne braki. Nie zastępuj istniejącego backendu mockami i nie przebudowuj stosu bez uzasadnienia. Nie dodawaj zależności tylko dlatego, że są modne. Nie przyjmuj, że aplikacja ma już płatności, wiadomości, rezerwacje lub pełny offline.

Zbuduj jeden zestaw komponentów z semantycznymi tokenami i dwoma motywami: jasnym ecru/śliwka oraz ciemnym grafit/szampan. Wybór: Jasny, Ciemny, Systemowy. Oba motywy zachowują ten sam układ informacji, routing, formularze i stany. Użyj typografii ze specyfikacji, dbając o polskie znaki, stabilność układu oraz skalowanie tekstu.

Najpierw wykonaj shell, nawigację Dziś/Plan/Budżet/Goście/Więcej, formularze i cztery główne widoki. Następnie szczegóły ofert, przegląd odczytu umowy, stoły, noclegi/transport, plan dnia, pakiet PDF i osobny ekran RSVP bez obowiązku konta gościa. Twórz użyteczne komponenty z semantyką, nie obrazy ekranów ani atrapę klikalności.

Wszystkie widoki mają mieć stany ładowania, pusty, błąd, brak sieci, zapis i konflikt, jeśli dotyczą danego procesu. W demo oznacz fikcyjne dane; w produkcji odczytuj rzeczywisty status. Nie wysyłaj wiadomości, nie wykonuj płatności i nie potwierdzaj rezerwacji na podstawie samego kliknięcia lokalnego przycisku.

Zaimplementuj ruch według motion-tokens.json: krótkie przenikanie zakładek; kierunkowe przejście szczegółów; płynny dolny panel; subtelna reakcja przycisków; natychmiastowe poprawne kwoty; spokojna zmiana motywu. Animacje muszą być przerywalne, zachowywać fokus i stan danych. Zachowaj ostatni zamiar użytkownika przy szybkiej nawigacji. Nie stosuj globalnego transition: all, ciężkiego paralaksu ani automatycznego konfetti.

Respektuj ograniczenie ruchu z systemu i aplikacji. Bez animacji funkcje mają pozostać w pełni dostępne. Dolne panele i dialogi muszą obsługiwać klawiaturę, Escape/wstecz, powrót fokusu i ochronę niezapisanego formularza. Gest nie może być jedyną metodą wykonania akcji.

Sprawdź poprawność budżetu, minima umowne, różne RSVP w rodzinie i wersjonowanie eksportu. Przygotuj sensowne testy tych scenariuszy; nie ograniczaj się do zrzutów ekranu. Zweryfikuj m.in. 320 px, 390 px, 768 px i 1280 px, tekst 200%, oba motywy, słabą sieć, powrót wstecz oraz szybkie przełączanie widoków.

Zakończ konkretnym raportem: co działa, co zweryfikowano, jakie procesy są jeszcze atrapą, jakie pozostały ograniczenia. Nie deklaruj zgodności z WCAG, pełnego offline ani płynności na telefonach bez odpowiednich testów. Zadbaj, aby luksus wynikał z jakości obsługi, a nie z nadmiaru animacji.
