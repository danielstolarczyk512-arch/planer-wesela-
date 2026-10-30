# Audyt przesłanych materiałów do V7

## Pliki źródłowe

- `1.mp4`: 28,70 s, 1080x1920, 24 fps, H264 + AAC; reklama z częstymi zmianami scen, kadrami kuchni i planszą końcową.
- `jm8Jkf-Icit-aOHkigGL4w.mp4`: 28,70 s, dokładnie ten sam SHA-256 co `1.mp4`; nie należy liczyć jako osobnego renderu.
- `3.mp4`: 5,875 s, 1344x1536, 24 fps, H264 **bez ścieżki audio**; zestawienie dwuczęściowego kadru pary przy laptopie. Nie jest dowodem poprawnego ruchu ust.
- `u6I5_awNw7L7EDipU44L7w.mp4`: 21,30 s, 1080x1920, 24 fps, H264 + AAC; materiał typu turnaround kobiety na neutralnym tle — przydatny do referencji, lecz nie pokazuje filmowej pracy kamery w realnym wnętrzu.
- `orbit.zip`: rzeczywista wersja programu V6, 8 PNG kątów, `angles_sheet.png`, skrypt i log `angles.log` oraz biblioteka referencji. Log zawiera co najmniej jeden błąd HTTP 409 przy generowaniu kąta; nie należy traktować prób jako wszystkich bezbłędnych.

## Krytyczne problemy

1. **Brak skutecznego lip sync**. Nie ma przewidzianego przepływu dla użycia finalnego polskiego audio jako wejścia do generacji twarzy. Dołożenie audio w montażu nie zmienia ust w już istniejącym obrazie.
2. **Polski głos**. W dotychczasowym raporcie produkcji użyto Piper w zastępstwie nieczytelnej mowy H3; jego brzmienie zostało ocenione jako syntetyczne. ASR wykrywające 14 kwestii nie dowodzi naturalności ani synchronizacji fonemów.
3. **Kolaże w klipach**. Ujęcie `3.mp4` zawiera dwa poziome panele, co może wyglądać jak animowany storyboard, nie filmowa scena.
4. **Kamera 360**. Nowe syntetyczne widoki nie rozwiązują geometrii ani tożsamości, szczególnie przy dwóch postaciach i przesłanianiu twarzy.
5. **Montaż**. Bez ujęć reakcji i close-upów na mówiącego historia traci filmowy rytm. Zalecane coverage: plan wspólny → mówiąca twarz → reakcja drugiego bohatera.
6. **QC**. Sam `ffprobe` i zakres rozdzielczości nie sprawdzają polskiej mowy, ruchu ust ani błędów twarzy.

## Zalecenia reżyserskie

| Sytuacja | Plan | Kamera | Głos |
|---|---|---|---|
| Pierwsze zdanie narzeczonej | duże zbliżenie | stabilna na wysokości oczu | polski WAV jako wejście IA2V |
| Reakcja narzeczonego | close-up | statyczna, cięcie | bez mowy, usta nieruchome |
| Dialog z obojgiem | dwa osobne półzbliżenia | reguła osi 180 stopni | jeden speaker na klip |
| Odkrycie aplikacji | nad ramieniem → insert UI | subtelny ruch boczny | dźwięk bez wymuszonego ruchu ust |
| Wejście do sali | szeroki plan | lekki orbit 30–45° | bez mowy |
| Puenta | zbliżenie | powolny najazd i cut do reakcji | 1 krótka fraza, audio-first |

## Co wdrożono

Zobacz `README_V7.md`, nowy panel „Reżyser V7”, pliki `studio/dialogue_v7.py`, `studio/cinematic_v7.py`, `studio/voice_cli_v7.py`, `qc/lips_v7.py` i testy.

**Rzeczywisty odsłuch polskiej mowy oraz finalna zgodność ust po nowym renderze wymagają testu na komputerze użytkownika z aktywnym Sogni.**
