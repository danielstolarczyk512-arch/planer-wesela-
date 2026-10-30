# Raport testów V8.3

- Python `python -m unittest discover -s tests -q`: **111 testów przeszło** (100 odziedziczonych plus 11 nowych V8.3; wynik z lokalnej kopii źródłowej przed spakowaniem).
- W zakresie nowych testów: długość 180 s, suma czasów, 46 ujęć, pierwsze prawdziwe UI przed 25% filmu, Character Bible, izolacja edycji, obrazowe `edit_image`, brak sieci przy planowaniu kosztów, bezpieczeństwo SHA256 i archiwów, API HTTP z autoryzacją, blokada uploadu bez zgody.
- `node --check web/app.js`: składnia JavaScript poprawna.
- Próbny test HTTP serwera wykonany w testach automatycznych.
- Próba E2E GUI Chromium: **nieukończona**, środowisko zwróciło `ERR_BLOCKED_BY_ADMINISTRATOR` przy nawigacji do `http://127.0.0.1`.
- Sogni: **brak rzeczywistej generacji**, brak weryfikacji listy modeli dostępnych w subskrypcji; testowany tylko kształt żądań i reguły bezpieczeństwa.
- Polskie TTS/Audio-to-Video: nie renderowane i nieodsłuchane na prawdziwym koncie.
- Brak rzeczywistego nowego 180-sekundowego filmu: V8.3 generuje plan produkcji, nie wytwarza samodzielnie zawartości bez generacji w Sogni.
