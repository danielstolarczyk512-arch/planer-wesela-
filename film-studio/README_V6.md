# Nasz Dzień — AI Film Director Studio V6 / Camera 360 Lab

## Jak uruchomić

1. Rozpakuj ZIP na Windows. Wymagany Python 3.10+. Uruchom `start_windows.bat` (offline) lub `start_full_windows.bat` (Sogni). Do montażu: FFmpeg.
2. W przeglądarce: http://127.0.0.1:8765.
3. **Referencje V6** → wczytaj bibliotekę → obejrzyj i zatwierdź obrazy → przydziel referencje ujęciom → włącz `Identity Lock` jeśli chcesz blokować generacje bez zatwierdzonych zdjęć.
4. **Kamera 360** → wybierz projekt i preset. Najbezpieczniejsze: `Portret z trzech stron`, `Filmowe odkrycie pary`, `Odsłonięcie telefonu`.
5. Przed generowaniem jednego nowego kąta: zainstaluj Node.js 22.11+, `npm install -g @sogni-ai/sogni-creative-agent-skill`, skonfiguruj aktualny `SOGNI_API_KEY`. Aktywne Unlimited jest wymagane i sprawdzane. Każde zadanie musi być jawnie zatwierdzone.
6. Obejrzyj PNG nowego kąta. Dopiero potem przypisz do sceny, a w Storyboardzie osobno zsynchronizuj klatkę i animuj przez H3 I2V. Do filmu wstaw realny ekran aplikacji Nasz Dzień na etapie montażu.

## Co nowego względem V5

- Import 60 PNG z checkpointu (25 kobieta, 25 mężczyzna, 10 wspólnych), bez wymazywania statusów jakościowych.
- Rozdzielenie statusów `pending_final_review`, `pending_correction`, `approved`, `rejected` oraz ręczne zatwierdzanie w programie. Cztery obrazki oznaczone do poprawki pozostają niezatwierdzone.
- Ranking referencji pod kąt kamery / mimikę / akcję, z ręcznym wyborem do trzech obrazów per ujęcie.
- `Identity Lock`: blokuje wysyłkę scen bez wymaganych zaakceptowanych i zsynchronizowanych referencji.
- `Camera 360 Lab`: lokalne darmowe planowanie z 6 presetami, 96 kątami w przestrzeni 8×4×3, ostrzeżenia o zmianie perspektyw / ryzyku deformacji.
- **Pojedynczy** rzeczywisty kąt przez oficjalny `sogni-agent` CLI po zgodzie; komenda zawiera `--billing-mode subscription`, bez płatnego fallbacku. Bez zbiorczych generacji w tle.
- Zatwierdzony obraz 360 można przypisać jako pierwszą klatkę ujęcia H3.
- Opcjonalna heurystyczna kontrola fragmentów o bardzo małym ruchu i zduplikowanych połówek (Pillow + FFmpeg, nie jest to sztuczna inteligencja ani analiza identyczności twarzy).

## Ważne

- Pełne 360 z obrazu 2D NIE jest prawdziwą geometrią 3D i może wymyślić tył postaci. W scenach z dwiema osobami używaj krótkiego ruchu 45°.
- Plan 360 jest lokalny i darmowy; *generacje w Sogni wymagają konta i obowiązujących uprawnień*. W tej sesji nie potwierdzono ich na żywo.
- Żaden klucz API nie znajduje się w archiwum. Użyj nowego klucza, nie starego ujawnionego w rozmowie.
- Biblioteka V6 jest **CHECKPOINTEM**. Obrazy nie są automatycznie zatwierdzane przez program.
- Do prawidłowej publikacji należy obejrzeć i odsłuchać gotowy film. 360 nie zastępuje reżyserii ani dobrej fabuły.

Testy: `python -m unittest discover -s tests -v`.
Więcej: `INSTRUKCJA_V6_360.md` oraz `REPORT_V6.md`.

## Wersja LIGHT (mały ZIP)

Jeżeli pobranie paczki 109 MB jest trudne, użyj wydania `V6_LIGHT_KOD.zip` (sam program + indeks) i posiadanego już checkpointu. Rozpakuj LIGHT i uruchom w katalogu programu:

`python tools/install_checkpoint.py "C:\\ścieżka\\NASZ_DZIEN_CHARACTER_REFERENCE_LIBRARY_V6_CHECKPOINT(1).zip"`

Skrypt sprawdza SHA256 każdego z 60 PNG i odrzuca brakujące lub zmienione pliki. Bez tego program LIGHT nie będzie miał zdjęć referencyjnych.
