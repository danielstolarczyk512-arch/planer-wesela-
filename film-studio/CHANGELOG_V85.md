# Nasz Dzień Film Studio V8.5 — lista zmian

**Źródło:** V8.4, bez odinstalowywania wcześniejszych modułów. **Nowy styl:** dostarczony 1122×1402 px Golden Master.

- Podmiana STYLE na nowy portret w `assets/style/visual_reference.png` i `assets/style/MASTER_GOLDEN_STORYBOOK_V85.png`.
- Stare materiały STYLE przeniesione do `assets/style/archive_do_not_use`.
- Poprawiony domyślny opis ubioru mężczyzny na ciemny T-shirt; wspólny opis stylistyki odwołuje się do nowego zatwierdzonego obrazu.
- Wysyłanie do Sogni ponownie wymaga synchronizacji, gdy hash lokalnego wzorca różni się od zapisanego w czasie uploadu.
- `studio/timeline_v85.py`: lokalne WAV PCM 16-bit, bezpieczne ścieżki, ręczny odsłuch i akceptacja, hash, invalidacja lip-sync i MP4 po zmianie nagrania, J/L-cut przez offset ±2 s, SRT z kontrolą nakładania.
- `montaz.py`: opcjonalna separacja głosu od oryginalnego audio + opcjonalna muzyka, jeden wspólny miks i eksport SRT; stary tryb pozostaje dla starszych projektów.
- `qc/continuity_v85.py`: ręczna ocena MASTER + 3 klatki prawdziwego wideo, brak fałszywej deklaracji rozpoznania twarzy.
- `studio/quality_v85.py`: wczesne UI, zbyt długie portrety, monotonia, zbyt długi end card, kontrola głosów.
- `server.py`: API V8.5 do WAV, odsłuchu, zatwierdzania, przeglądu, SRT, kontaktów wideo i wyboru trybu miksu; integracja zatwierdzonego WAV z istniejącym V7 IA2V.
- `web/app.js`: nowy interfejs „V8.5 · styl, dubbing i montaż”, aktualizacje PWA cache.
- `studio/portable_v83.py`: archiwizacja WAV V8.5 i ponowna weryfikacja po przywróceniu.
- `MIGRUJ_Z_V84.ps1`: migruje tylko dane i przypina wybrany styl. Stare projekty z dawnymi przypięciami wymagają ponownej akceptacji.

**Zakres bez zmian:** zewnętrzne funkcje Sogni wymagają zgody i dostępności w abonamencie. Nie zainstalowano TTS ani nie wygenerowano klipów w chmurze. System nie potrafi sam udowodnić spójności twarzy ani dokładnego lip-sync.
