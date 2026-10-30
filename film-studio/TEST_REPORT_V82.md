# Raport weryfikacji — Film Studio V8.2

**Wynik:** 100/100 testów jednostkowych i integracyjnych (`python -m unittest discover -s tests -q`). Wszystkie testy wykonywano lokalnie, bez wywołań zewnętrznego API Sogni i bez płatnych generacji.

- 90 testów odziedziczonych z V8, 10 nowych testów V8.2.
- Testy V8.2 obejmują: początkowo niezatwierdzone kandydatury referencji, ręczną zgodę, niezmienne SHA-256, zmianę pliku wzorca, blokadę ujęcia bez zatwierdzonej klatki, zgodność z wersją ujęcia, odrzucenie podmienionej klatki, bezpieczne ścieżki i MIME obrazu oraz integrację API od wczytania projektu po symulowaną synchronizację pierwszej klatki.
- Sprawdzono składnię Pythona (`compileall`) i JavaScript (`node --check web/app.js`).
- **Niezweryfikowane:** rzeczywiste renderowanie z kontem Sogni, skuteczność kontroli stylu na nowych klatkach, pełne zachowanie spójności postaci podczas animacji, polskie TTS, lip-sync, test UI z prawdziwymi kliknięciami w przeglądarce. Próba użycia Chromium w środowisku testowym zakończyła się blokadą dostępu do lokalnego HTTP `ERR_BLOCKED_BY_ADMINISTRATOR`, dlatego jej nie zaliczono.
- `Master Visual Lock` nie stosuje arbitralnych wyników automatycznego podobieństwa jako gwarancji zgodności. Wymaga ocen użytkownika i wykrywa zmiany bajtowe w *uprzednio zatwierdzonych* obrazach.

## Uwaga jakościowa

`assets/style/visual_reference.png` ma tylko **180×206 px**. Trzy referencje z checkpointu V6 (`woman`, `man`, `couple`) **nie mają domyślnie statusu `approved`**. Użytkownik powinien obejrzeć wszystkie cztery wzorce i zatwierdzić tylko poprawne. Szczegóły: `README_V82.md` i `STYLE_BIBLE_V82.md`.
