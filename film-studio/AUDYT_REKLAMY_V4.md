# Nasz Dzień Film Studio v4 — audyt rzeczywistej reklamy

Data: 28.10.2026
Film: `NASZ_DZIEN_REKLAMA_FINAL_30S.mp4`

## Co zweryfikowano
- 30,01 s, 720×1280 (9:16), H.264, AAC stereo 48 kHz.
- Średnia przepływność obrazu ok. 1,28 Mb/s (całego pliku ok. 1,41 Mb/s).
- Poziom zintegrowany wg FFmpeg EBU R128: ok. -16,8 LUFS, LRA ok. 9,8 LU, true peak ok. -0,5 dBTP. Różnice głośności pomiędzy fragmentami wymagają wyrównania. Nie wykonywano subiektywnego odsłuchu dźwięku.
- Ujęcia zostały przejrzane chronologicznie po poprawnym uporządkowaniu klatek. Film nie jest przemieszany, a logo jest na końcu.

## Rzeczywista chronologia i wnioski
1. **0–5 s:** frontalny monolog mężczyzny: „Mamy problem. Ciotka Marianna i wujek Zygmunt. Przy jednym stole.” Długi, przerysowana mimika, bez naturalnego partnera dialogowego, brak wyraźnej akcji.
2. **5–10 s:** para ukrywa się za dekoracją, patrzy na gości. Pojawia się „Nie ruszaj się. Wujek Zygmunt patrzy.” Dowcip jest zrozumiały, ale 5 sekund tej samej pozycji jest zbyt długo.
3. **10–14,5 s:** prawdziwy interfejs planowania stołów, lecz w pionowym filmie elementy są małe. Widać przewijanie, ale nieczytelny jest konkretny ruch rozwiązujący problem.
4. **14,5–19,5 s:** para stoi w innym wnętrzu, narzeczona pokazuje niemal biały ekran telefonu, mówi „Dwa stoły. Czternaście metrów. Dzięki Nasz Dzień.” Komunikat wyjaśnia benefit, ale inscenizacja i tekst są sztywne, zbliżone do reklamy demonstracyjnej.
5. **19,5–25 s:** sala i ponowne spotkanie pary. Plansza „Operacja zakończona.” Nie ma czytelnej, emocjonalnej reakcji skonfliktowanych gości ani wyraźnej puenty.
6. **25–30 s:** dwie statyczne plansze — hasło „Plan stołów, który kończy wojny” i logo „Nasz dzień”. Kolejność jest prawidłowa, ale pięć sekund statycznego zakończenia jest zbyt długie.

## Diagnoza jakości odbioru
- Nie widzimy prawdziwej chemii między bohaterami: stoją lub wyglądają zza kwiatów, zamiast reagować na siebie i aktywnie coś robić.
- Zbyt duża liczba pięciosekundowych ujęć i niemal wyłącznie frontalne kadrowanie dają „demo generatora AI”, nie filmowy rytm.
- Żart jest zapowiadany, ale nie ma właściwego wizualnego „payoff”: starsi goście nie pokazują zabawnej, jednoznacznej reakcji.
- Telefon z pustym ekranem podważa wiarygodność produktu; prawdziwy interfejs jest za drobny i nie pokazuje akcji „przesuń osobę do innego stołu”.
- Lokalizacja i czas akcji zmieniają się bez mostka narracyjnego: sala weselna → interfejs → para w innym wnętrzu → sala.
- Ekstremalnie dopracowana sala i równie „idealne” zachowanie bohaterów obniżają naturalność. Potrzebne drobne spontaniczne ruchy, autentyczne detale i reakcje.
- Jakość kompresji jest ograniczeniem: docelowy montaż w 1080×1920 (jeśli źródło i upscale na to pozwalają), H.264 CRF 18–20 i lepszy preset.

## Wymagania v4 — P0 (obowiązkowe)
1. **Story Director:** czytelny konflikt, dwie krótkie linie dialogu zamiast frontalnego monologu, rozwiązanie pokazane działaniem, wyraźny komediowy payoff.
2. **Shot Composer i ciągłość:** 8–12 efektywnych ujęć po 0,8–3,5 s; minimum jedna reakcja bez słów; plany bliski/średni/szeroki/detal; blokada identyfikatorów aktorów, ubrań, przestrzeni, rekwizytów.
3. **Prawdziwa aplikacja:** nagranie prawdziwego UI, powiększenie wybranego zadania, ujęcie przed i po przesadzeniu gościa; telefon albo otrzymuje zweryfikowany composite ekranu, albo jego ekran nie jest wyświetlany frontalnie.
4. **Bezpieczny montaż:** timeline/EDL jako źródło prawdy z `shot_id`, `start`, `in`, `out`, `shot_role`, `dialogue_id`, `continuity_id`, `assets`, `approved`; zapobieganie ujęciom z nieodpowiednią wersją scenariusza; zachowanie audio; muzyka automatycznie wyciszana pod dialogiem.
5. **Jakość techniczna:** 24 fps CFR, pion 1080×1920 w eksporcie jeżeli da się go uzyskać bez dodatkowych kosztów; CRF 18–20, preset medium/slow; kontrola bitrate, tekstu w safe zones, błędnych klatek, ciszy, poziomu audio i dźwięku na cięciach.
6. **Zatwierdzanie:** storyboard → próbki → QC → finalny montaż; regeneruj tylko słabe ujęcia. Dodatkowe operacje nie mogą omijać sprawdzenia abonamentu.

## Wymagania v4 — P1 (jakość premium)
- Zestaw referencyjny dla każdej osoby: przód, profil, mimika, garderoba, proporcje, kierunki spojrzeń; ustawienia identyczności, zero automatycznej wymiany postaci.
- Projekt lokacji i schemat stołów zachowywany między ujęciami.
- Prompt reżyserski wymusza jedną prostą akcję fizyczną na ujęcie, naturalną mikroekspresję, wiarygodną pracę kamery; ogranicza szerokie uśmiechy, frontalną mowę, nadmiernie zsynchronizowane gesty i nierealne przemiany.
- Kontrola wideo na podstawie faktycznych klatek, nie na podstawie tekstu promptu: twarz, dłonie, tekst, ekran telefonu, zgodność dekoracji i bohaterów, przebieg ruchu.
- Napisy i logo jako oddzielne warstwy w postprodukcji, generowane deterministycznie, nie przez model wideo.
- Lokalny audio mix: dialog, ambient, SFX, muzyka na osobnych ścieżkach, sidechain/ducking, loudness i true peak (cel np. -16 LUFS i <= -1 dBTP).
- Rzetelne model routing: MiniMax H3/H3 Turbo i inne modele planowe, których dostępność faktycznie potwierdzono. Zero Spark.

## Przykładowy storyboard nowej reklamy 30 s
- **0–2 s**: zbliżenie: dwie wizytówki „Ciocia Marianna” i „Wujek Zygmunt” trafiają na sąsiednie miejsca. Krótka pauza.
- **2–5 s**: narzeczona spogląda na narzeczonego: „Nie. Tylko nie obok siebie.” Bez patrzenia w obiektyw.
- **5–8 s**: ciocia i wujek wymieniają nieco zbyt uprzejme, chłodne spojrzenia; mikrogest. Komediowy dźwięk.
- **8–13 s**: na rzeczywistym planie stołów jedna karta gościa zostaje przesunięta. Widać „przed/po”.
- **13–17 s**: narzeczony do narzeczonej półgłosem: „I już?” Ona odpowiada uśmiechem, nie monologiem.
- **17–23 s**: dwie różne części sali, ciocia i wujek rozmawiają z innymi gośćmi, a para z ulgą się rozluźnia. Jeden drobny komediowy akcent.
- **23–26 s**: para w autentycznym spontanicznym śmiechu; pojawia się satysfakcja i ulga.
- **26–30 s**: logo na żywym tle lub płynny przejazd do planszy. „Mniej stresu. Więcej Was. Nasz Dzień.” Wyraźny CTA do produktu.

## Testy akceptacyjne v4
- Brak widocznego pustego telefonu w kadrze, w którym demonstrujemy aplikację.
- Widz rozumie problem w 3 sekundy, produkt i jego zastosowanie do 15. sekundy, komediową puentę przed 26. sekundą.
- Każdy ważny bohater zachowuje identyfikowalny wygląd, ubranie, rekwizyty i lokalizację w ramach sceny.
- Co najmniej 8 sensownych ujęć, bez powielania tej samej pięciosekundowej pozycji aktorów.
- Produkt jest widoczny czytelnie przez co najmniej 2–3 sekundy, z rzeczywistym działaniem.
- Zero nakładania się napisów ze sterowaniem aplikacji społecznościowej.
- Końcowe MP4 ma dźwięk, poprawną kolejność scen i rzeczywiste CTA.
- Lektor/dialogi zweryfikowane odsłuchowo i technicznie; audio nie przekracza -1 dBTP.
- Każda generacja realizowana tylko przy aktywnym abonamencie i potwierdzonym `billing_mode: subscription`; żaden model premium vendor nie jest uruchamiany.

## Zmiany w kodzie v3
- `montaz.py`: dziś ma statyczne 720×1280, `libx264 -preset veryfast -crf 23`, 24 fps oraz opcjonalne miksowanie muzyki stałym poziomem bez automatycznego duckingu. Przenieść do `editor/timeline.py`, `editor/audio.py`, `editor/export.py`, dodać przejścia i nakładki.
- `studio/ai.py`: osobny Story Doctor, Script Director i Creative QA z kontrolą konfliktu, reakcji i payoff.
- `studio/engine.py`: rozszerzyć model ujęcia o akcję, reagującego bohatera, rekwizyty, ujęcie przed/po, continuity_id, dane screen compositing.
- `studio/sogni.py`: modele tylko z abonamentu, klatki start/end i referencje z kontrolą uprawnień; obsługa powtórki wyłącznie pojedynczego ujęcia i log powodu regeneracji.
- Nowe `qc/video.py`, `qc/audio.py`, `qc/story.py`, `product/screen_capture.py`; testy przeglądarkowe i e2e renderu.

Uwaga: w aktualnej dokumentacji Sogni (28.10.2026) MiniMax H3 ma minimum ok. 5,17 s generacji. Można generować dłuższe ujęcia bazowe i wycinać krótsze fragmenty w montażu. Ewentualnego FlashVSR upscalera należy użyć dopiero po potwierdzeniu objęcia planem; nie zakładać tego na podstawie nazwy modelu.
