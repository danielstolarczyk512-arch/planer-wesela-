# Testy Nasz Dzień Film Studio V8

Data: 2026-10-29

- **90 / 90 testów automatycznych zaliczonych**, obejmujących 80 testów V7 i 10 nowych V8.
- HTTP: `/api/v8` wymaga autoryzacji; logika przygotowania głosu, odmowa bez zgody i zatwierdzenie mockowanego wariantu sprawdzone.
- Lokalny FFmpeg: prawdziwy test montażu i kadrowania obrazu UI 360 × 640 (draft), pełny EDL V7 zachowany.
- Lokalny FFmpeg: analiza klipu statycznego przez `qc/motion_v8.py`.
- API Sogni: **nie wykonywano prawdziwych generacji**, unikając opłat; istniejące zabezpieczenia zostały zachowane.
- Chatterbox: **nie został zainstalowany i nie generowano polskiego audio na GPU**. Funkcja jest opcjonalną integracją wymagającą instalacji i sprzętu; realna jakość do weryfikacji odsłuchowej.
- Lip-sync: nadal wymaga fizycznego renderu audio-driven i ręcznej akceptacji, samo dodanie TTS go nie naprawia.
- Przeglądarka Chromium: próba otwarcia interfejsu przez Playwright została zablokowana przez administratora środowiska (`ERR_BLOCKED_BY_ADMINISTRATOR`). JavaScript przeszedł `node --check`; test przeglądarkowy nie został zaliczony.
- Nie sprawdzono jakości finalnego 180-sekundowego filmu V8, ponieważ go nie generowano.

Zalecany następny krok: 2–8 s polskiego dialogu kobiety i mężczyzny, import/porównanie głosów, render H3 IA2V w zatwierdzonym Unlimited i rzeczywisty odsłuch.
