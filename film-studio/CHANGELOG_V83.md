# Zmiany V8.3 (2026-10-29)

- `studio/longform_v83.py`: offline scenopis 61–180 s, cztery akty i 46 ujęć dla 180 s; wczesne realne UI.
- `studio/character_bible_v83.py`: jedna kanoniczna obsada dla nowych projektów, stabilne ID postaci.
- `studio/reference_v83.py`: prawdziwy obraz źródłowy + obrazowe referencje, SHA256, czasowe URL, wersjonowanie.
- `studio/sogni.py`: obsługa `edit_image`, `sourceImageIndex`, `referenceImageIndices`, wyłącznie `billing_mode=subscription`. Preflight ceny nie łączy się z endpointem generującym.
- `server.py`: API `/api/v83`, podgląd obsady, referencji, zgody na przesyłanie, przełącznik V8.3, lista zadań, kopia przenośna.
- `studio/portable_v83.py`: archiwum z lokalnymi materiałami i manifestem SHA256; walidacja przed przywróceniem.
- `tools/restore_portable_v83.py`: bezpieczne przywracanie do czystego projektu bez nadpisania danych i z ponowną akceptacją obrazu.
- `web/app.js`: nowy panel V8.3, 90/120/150/180 s w kreatorze, eksport backupu, bezpłatne planowanie obrazów.
- `web/sw.js`: nowa wersja pamięci PWA, ograniczenie problemów z ładowaniem starego panelu.
- `tests/test_v83.py`: testy integracyjne, bibliotek, długiego filmu, zgód i archiwów.

**Zachowano** kod V8.2, całą bibliotekę postaci (60 PNG), Voice Studio, Camera 360, LipSync V7, montaż, FFmpeg oraz stare API projektu.
