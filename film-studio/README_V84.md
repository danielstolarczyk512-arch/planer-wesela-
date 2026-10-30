# Nasz Dzień AI Film Director Studio V8.4 — Production Director

## Co jest naprawdę wdrożone

- **Scenariusz 180 s z polskimi kwestiami** i wskazaniem mówcy, emocji, lokacji, garderoby oraz zasad ciągłości. Projekt zawiera 46 ujęć; scenariusz i dialogi można edytować. Wybrana koncepcja wpływa na tematykę i tekst, ale nie zastępuje pracy dramaturga.
- **Scenariusz Doctor offline dla filmów >60 s**: analizuje dramaturgię, długość wypowiedzi i czas wejścia produktu **bez wysyłania żądań do Sogni**. Dla reklam do 60 s pozostawiono dotychczasowe działanie.
- **Studio dialogów na kartach ujęć**: edytowanie tekstu/mówcy/emocji unieważnia zatwierdzenie starego nagrania i ruchu ust. Rzeczywiste nagranie i kontrola lip-sync pozostają obowiązkowe.
- **Production Planner**: lista nowych renderów i materiałów do ponownego użycia, priorytety, oszacowanie sekund generowanego materiału. To nie jest wycena dostawcy.
- **Scene Bible i kontrola ciągłości**: regułowy audyt statusów wzorca, klatek, akceptacji i dialogów. Program **nie potrafi automatycznie potwierdzić tożsamości twarzy ani dokładnego ruchu ust**.
- **Kolejka Sogni**: blokada lokalnie jednoczesnego wysłania nowego zadania dla aktywnego/niepewnego ujęcia. Nie ma samoczynnego powtarzania operacji. Nie oznacza to atomowego zarządzania zadaniami pomiędzy różnymi instancjami serwera.
- **Backup+restore**: rzeczywisty katalog `data/v7_renders` uwzględniony w backupie. Bezpieczny import ZIP jako **nowy projekt**: SHA256, walidacja ścieżek, odrębny ID, brak nadpisania innych projektów, brak wznawiania starych workflow. Import wymaga ponownego przypięcia i zatwierdzenia Master Visual Lock.
- Zachowane: Golden Master V8.2, 60 referencji PNG, V8.3 generowanie obrazów z referencji, Voice Studio V8, Audio-first V7, Camera 360, edycja ujęć i FFmpeg.

## Windows — nowa instalacja

1. Rozpakuj `Nasz_Dzien_AI_Film_Director_Studio_V8_4_FULL.zip` do nowego folderu, np. `D:\film-studio\V8.4`.
2. Wejdź do `Nasz_Dzien_Film_Studio_V8_4`.
3. Uruchom `start_windows.bat` (Python 3.10+). Przy montażu wymagany FFmpeg w PATH.
4. Otwórz `http://127.0.0.1:8765` i zakładkę **Produkcja V8.4**.
5. W projektach 180 s przeczytaj dialogi, odsłuchaj każdą kwestię, ręcznie zatwierdź Master Visual Lock, klatki i gotowe klipy.

## Migracja danych z V8.3

**Wariant A: kopia obecnego stanu V8.3 (zalecany dla trwających projektów).**

Zamknij obie aplikacje. W PowerShell z katalogu V8.4 uruchom:

```powershell
.\MIGRUJ_Z_V83.ps1 -Source "D:\film-studio\V8.3\Nasz_Dzien_Film_Studio_V8_3"
```

Skrypt wymaga wpisania `TAK`, zachowuje kopię dotychczasowego katalogu `data` V8.4 i kopiuje dane z V8.3. Nie usuwa pierwotnej instalacji. Windows może wymagać ręcznego zezwolenia na lokalny skrypt.

**Wariant B: import jednej kopii projektu.**

W V8.3 pobierz przenośny ZIP projektu. W V8.4 otwórz **Produkcja V8.4 → Przywróć przenośny ZIP**. Import tworzy osobny projekt. Uwaga: starszy eksport V8.3 mógł nie zawierać `v7_renders`, dlatego do pełnej migracji lepszy jest wariant A.

## Zakres testów

Wszystkie testy automatyczne można uruchomić:

```powershell
py -3 -m unittest discover -s tests -q
```

Możesz sprawdzić składnię JS przez `node --check web/app.js`, jeśli masz Node.js. Testy jednostkowe i HTTP korzystają z lokalnych danych i nie wykonują generacji Sogni.

## Ograniczenia i koszty

- V8.4 nie zawiera gotowego filmu ani nowych głosów: konieczne są rzeczywiste pliki audio i MP4.
- Synteza Chatterbox nadal wymaga lokalnej instalacji i weryfikacji na docelowym GPU; poprawy jakości języka polskiego nie uznano za potwierdzoną.
- Automatyczna identyfikacja postaci i dokładna ocena fonem–usta nie są obecnie zaimplementowane.
- Nie uruchamiano żadnej płatnej generacji Sogni. Obsługa operacji wymaga świadomego potwierdzenia i zachowuje `subscription`.
- Panel pełnej jakości w Chromium nie został zweryfikowany w tym środowisku z powodu blokady nawigacji lokalnej.

**Główna zasada:** najpierw potwierdzony scenariusz i nagrania audio, następnie zaakceptowane klatki ze stałą tożsamością, później animacja i montaż.
