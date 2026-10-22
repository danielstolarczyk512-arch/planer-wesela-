# Lista odbioru GUI

To lista do wykonania po implementacji. Obecność pozycji nie oznacza, że test został przeprowadzony.

## Wygląd i responsywność
- [ ] Oba motywy obejmują wszystkie 10 modułów, dialogi, panele i stany błędów.
- [ ] Motyw nie zmienia routingu, kolejności informacji ani pól formularza.
- [ ] Nie ma przypadkowo białych elementów w ciemnym motywie; podgląd papierowego PDF może pozostać jasny.
- [ ] Widoki 320, 390, 768 i 1280 px nie tracą działań; nie mieszczą treści kosztem pomniejszania fontów.
- [ ] Tekst 200%, długie nazwiska i kwota 1 250 000,50 zł nie zasłaniają kontrolek.
- [ ] Wszystkie główne cele dotykowe mają 48 × 48 px; bezpieczne obszary systemowe i klawiatura są uwzględnione.
- [ ] Kontrast tekstu, fokusu i obrysów pól zmierzony także dla disabled/error/selected i warstw nakładanych.

## Ruch i nawigacja
- [ ] Pięć szybkich dotknięć różnych zakładek kończy się na ostatniej, bez kolejki starych animacji.
- [ ] Lista → szczegóły → wstecz przywraca przewinięcie i filtr.
- [ ] Zmiana motywu podczas wpisywania nie kasuje tekstu ani zaznaczenia i nie zamyka klawiatury.
- [ ] Ograniczenie ruchu usuwa przesunięcia, skalowanie, kaskady i shared elements.
- [ ] Panel można otworzyć i zamknąć dotykiem, przyciskiem, wstecz/Escape; fokus wraca do wywołującej kontrolki.
- [ ] Gest zamykania i przewijanie panelu nie kolidują; niezapisane zmiany są chronione.
- [ ] Nagranie / profil na rzeczywistym telefonie nie wykazuje powtarzalnych zacięć. Złożone efekty mają wariant uproszczony.

## Dane i zaufanie
- [ ] 5000 zł umowy − 1500 zł wpłaty = 3500 zł pozostałej należności.
- [ ] Minimum 100 osób nie zmienia się automatycznie po zejściu do 90 gości.
- [ ] Brak odpowiedzi, odmowa i potwierdzenie są odrębnymi stanami.
- [ ] Rodzina może mieć inne RSVP na wesele i poprawiny.
- [ ] Brak wyceny nie jest prezentowany jako 0 zł.
- [ ] AI wymaga potwierdzenia danych umowy; nieczytelna kwota nie trafia jako pewna do budżetu.
- [ ] Błąd zapisu zachowuje formularz i jasno oznacza brak zapisu.
- [ ] Podwójne dotknięcie zapisu nie tworzy dwóch identycznych rekordów.
- [ ] Równoczesne zmiany pary nie nadpisują się bez informacji.
- [ ] Stary pakiet PDF zostaje oznaczony jako nieaktualny po zmianie danych.
- [ ] Kurs 01:30 po weselu 1 lipca pokazuje 2 lipca.
- [ ] Gość nie może przejść do cudzej odpowiedzi lub panelu pary.
- [ ] Czytnik ekranu odczytuje statusy i błędy; dekoracje są pomijane.
