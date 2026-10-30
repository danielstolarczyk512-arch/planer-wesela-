# Raport testów — Film Studio V4

Data: 28 października 2026.

## Wykonano

- `python -m unittest discover -s tests -v`: **41/41 testów PASS** (33 dotychczasowe testy V2/V3 + 8 nowych testów V4).
- `node --check web/app.js`: **PASS** — kontrola składni interfejsu JavaScript.
- `python -m compileall -q .`: **PASS** — kompilacja kodu Python.
- Przez serwer HTTP i bazę SQLite: tworzenie projektu, Director v4, 10 ujęć, audyt historii, wysyłanie lokalnego MP4, podgląd MP4, próba zatwierdzenia fałszywego UI (odrzucenie), akceptacja deklarowanego realnego UI, unieważnienie akceptacji po ponownym wgraniu.
- Rzeczywisty FFmpeg: przetworzenie 10 lokalnych **syntetycznych wyłącznie testowych** klipów w MP4 z audio; kontrola poprawności dźwięku i czasu przez FFprobe. Nie są to klipy Sogni ani gotowa reklama.
- Bezpieczeństwo: wymuszenie `billing_mode=subscription`, odrzucanie modeli premium i braku aktywnego abonamentu (testy mock).

## Nie przeprowadzono / ograniczenia

- Realna autoryzacja konta i prawdziwa generacja Sogni: **NIEPRZETESTOWANE ONLINE**. Żaden klucz nie trafił do ZIP.
- Automatyczny pomiar naturalności mimiki i anatomii: **NIEIMPLEMENTOWANY**; kontrola wymaga oględzin klipu przez człowieka.
- Pełna automatyczna produkcja bez ręcznego zatwierdzania: **NIEIMPLEMENTOWANA**.
- Test wizualny przeglądarki Chromium/Playwright: **ZABLOKOWANY** przez środowisko (`net::ERR_BLOCKED_BY_ADMINISTRATOR` dla `127.0.0.1`). Test API w lokalnym serwerze działa; test frontendu w rzeczywistej przeglądarce wymaga uruchomienia na komputerze użytkownika.
- Upscale źródła nie jest automatycznie wykonywany; eksport 1080p nie dodaje detali do obrazu 720p.
- Podkład muzyczny z duckingiem jest obsługiwany w `montaz.py`, ale pełny test akceptacyjny jakości odsłuchowej z muzyką nie został wykonany.

## Testy do wykonania przed reklamą produkcyjną

1. Uruchomić V4 na Windows i sprawdzić działanie UI w Chrome.
2. Wykonać test `/api/sogni/test` z nowym kluczem przez bezpieczne środowisko.
3. Sprawdzić aktywny Unlimited i wysłać żądanie tylko po świadomej akceptacji.
4. Wygenerować jedno ujęcie H3, obejrzeć i zatwierdzić je.
5. Nagrać prawdziwy ekran produktu, a następnie wgrać go i potwierdzić źródło.
6. Zweryfikować cały gotowy MP4 wzrokowo i słuchowo w odtwarzaczu oraz w telefonie.
