# CLAUDE CODE — DOKOŃCZ PRAWDZIWY PILOT V7: POLSKA MOWA + SYNCHRONIZACJA UST + FILMOWE KADRY

Jesteś liderem zespołu: senior full-stack developer, operator i reżyser animacji, dialog editor, sound designer i QA engineer. Otrzymujesz `Nasz_Dzien_Film_Studio_V7_FULL.zip` oraz pliki wideo. **Masz naprawdę uruchomić naszą aplikację, wykonać pilot i naprawić ujawnione błędy.** Nie oddawaj tylko promptów i fikcyjnych testów.

## Zadanie

1. Rozpakuj V7, przeczytaj `AUDYT_FILMOW_I_ORBIT_V7.md`, uruchom aplikację i sprawdź testy. Zachowaj istniejące projekty i kompatybilność V6.
2. Przeanalizuj nagrania `1.mp4`, `3.mp4`, `u6I5_awNw7L7EDipU44L7w.mp4` oraz `orbit.zip`. Zauważ, że `jm8Jkf-Icit-aOHkigGL4w.mp4` to ta sama zawartość co `1.mp4`.
3. Stwórz jedną **15-sekundową** komediowo-romantyczną próbkę w stylu Golden Storybook 3D z wcześniej zatwierdzonymi postaciami. Oboje mają zachować tożsamość, a nie tylko podobny wygląd. Scena: para w kuchni planuje wesele, kobieta mówi, mężczyzna reaguje, następnie krótki kadr z aplikacją Nasz Dzień. Nie używaj fikcyjnego UI.
4. **Polski dialog audio-first**: przed generacją nagraj lub uzyskaj zgodną z prawami osobistymi i licencją autentyczną polską próbkę głosu każdej mówiącej osoby. Jeśli głosy nie są dostarczone, użyj wyłącznie zweryfikowanego, lokalnego i legalnego narzędzia, ale przedstaw próbki do odsłuchu przed produkcją. Nie deklaruj, że polszczyzna jest naturalna, jeśli nie została odsłuchana. Nie używaj klonowania prawdziwego głosu bez uprawnienia.
5. Dla każdej wypowiedzi uruchom przez V7 **FastH3 IA2V** z `--ref` zatwierdzoną klatką, `--ref-audio` realnym WAV/MP3, `-m minimax-h3-fasth3-ia2v-turbo`, i **`--billing-mode subscription`**. Przed wysłaniem sprawdź rzeczywisty aktywny Unlimited. Żadne Spark, premium, płatne TTS i fallback. Dodatkowy koszt = zakaz. Nie wykonuj chmurowego renderu przy niepewnym rozliczeniu. Sprawdź status po każdym renderze.
6. Dla dialogu realizuj filmowy plan: close-up na twarz mówiącej postaci, cut do reakcji słuchającego, przez ramię przy kolejnej kwestii. Nie stosuj orbitu podczas ruchu ust. Jeśli mówca ma dwie kwestie, dopilnuj tego samego głosu i wyglądu.
7. Sogni 360: z ośmiu widoków `orbit.zip` przygotuj maks. 45° przejście podczas niemego ujęcia. Zawsze sprawdź spójność sylwetki, zgodność zegarka / ubrania / włosów, parallax tła. Jeśli kamera wygląda jak obracająca się figurka, wróć do normalnego planu. Nie nazywaj crop/zoom prawdziwym 360.
8. Po każdej generacji obejrzyj i odsłuchaj kompletny klip. Zaznacz dokładne sekundy, w których usta nie reagują na słowa lub twarz się deformuje. Wymień jedynie wadliwą scenę; nie regeneruj filmu bez przyczyny.
9. Program ma pozwolić zapisać `speaker`, ścieżkę audio, `language=pl-PL`, klatkę master, wybrany kadr, wynik lip-sync QC i decyzję człowieka. Jeżeli któryś etap nie działa, napraw w kodzie i dopisz test regresji.
10. Wykonaj końcowy MP4, a następnie raport z oceną naturalności dialogów, timingu, jakości mowy, ust, pracy kamery i braku dodatkowych kosztów. Odróżnij testy lokalne od realnych generacji.

## Kryteria akceptacji

- Wideo zawiera **rzeczywisty** ruch ust związany z polską wypowiedzią; nie wystarczy przyłożony lektor.
- Mężczyzna i kobieta są zgodni z zatwierdzonymi obrazami; brak przeskoków twarzy.
- Kamera pokazuje plan wspólny, usta mówiącej osoby oraz reakcję partnera, nie jest nieustanną panoramą/turntable.
- Polskie dialogi nie są mechanicznym, przypadkowym TTS; potwierdź to odsłuchem.
- Widoczny ekran produktu jest autentyczny.
- Sogni pracuje w potwierdzonym trybie abonamentowym; brak opłat poza Unlimited, nie omijaj fair-use.
- Eksport H264 + AAC prawidłowy, bez błędów obrazu.
- Działający kod programu V7 i projekt pilotowy zostają spakowane do ZIP.

Wymagane pliki: `V7_PILOT_15S.mp4`, `TEST_REPORT_LIPSYNC_V7.md`, `CAMERA_SHOTLIST_V7.md`, `SOGNI_COST_PROOF_V7.md` oraz `V7_FIXED_CODE.zip`. Jeśli prawdziwa generacja jest zablokowana, nie twórz pozornego MP4 — oddaj faktyczny kod, wyniki testów i precyzyjną diagnozę blokady.
