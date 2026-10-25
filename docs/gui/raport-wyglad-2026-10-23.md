# Ulepszenia interfejsu — 23.10.2026

Wspólne ulepszenia aplikacji „Nasz dzień”, z zachowaniem istniejących zmian i danych.

## Wdrożone

- Trzeci motyw biało-złoty: metaliczny gradient, refleksy, subtelna krawędź i krótki błysk. Bez nieskończonej animacji; ograniczenie ruchu wyłącza błysk. Ciemny tekst na złocie ma co najmniej 4,99:1 dla wszystkich punktów gradientu.
- Panel wyglądu: zmiana i zapis motywu, ograniczenie animacji, zamykanie Escape i kliknięciem poza panelem, przywracanie fokusu. Na telefonie narzędzia znajdują się pod treścią i nie zasłaniają formularzy.
- Komputer od 1100 px: szersza nawigacja, większy obszar pracy, dwukolumnowy pulpit. Telefon: dolna nawigacja i jedna kolumna.
- Przewijane podzakładki na telefonie; aktywna podzakładka staje się widoczna bez przewijania całego dokumentu.
- Lista gości: rzadsze operacje przeniesione pod „Więcej działań”. Eksport, wydruk i wysyłanie e-maili zachowują dotychczasowe funkcje.
- Wyszukiwarka: Ctrl+K / Command+K, czyszczenie zapytania, wskazówka minimalnej długości, ukrycie poprzednich wyników w trakcie zmiany zapytania.
- Poprawione kolory akcentów gościa i wydruków przy motywie złotym i ciemnym ustawieniu systemu.
- Powrót na górę i ponowne wybranie aktywnej zakładki respektują ograniczenie animacji.

## Weryfikacja

- 146 testów interfejsu w 38 plikach: pozytywnie.
- Kompilacja TypeScript i produkcyjny build: pozytywnie.
- Kontrola palet: 0 par poniżej wymaganego progu kontrastu.
- Ręczny podgląd przeglądarki: pulpit komputera, logowanie, motywy, skrót wyszukiwania; widoki pulpitu i gości przy szerokości 390 i 320 px, przycisk czyszczenia wyszukiwania.
- Podgląd szerokości telefonu używał ramki przeglądarki; nie zastępuje testu rzeczywistej klawiatury ekranowej, Safari, instalacji PWA i urządzenia fizycznego.
- Nie wykonano pełnego przeglądu każdego modułu ani testów operacji modyfikujących dane wesela.
- Bez nowych zależności, opłat, publikacji i zmian bazy danych.
