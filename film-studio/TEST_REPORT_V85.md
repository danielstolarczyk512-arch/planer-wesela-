# Testy Film Director Studio V8.5

- Grupa regresyjna V3–V8: **68/68**.
- Grupa regresyjna V8.2–V8.4 oraz core/API: **52/52**.
- Nowe testy V8.5: **15/15**, w tym:
  - Nowy wzorzec 1122×1402 w dwóch lokalnych plikach.
  - Blokada starych URL referencji Sogni po zmianie SHA.
  - WAV PCM 16-bit: import, odsłuch/akceptacja, brak zgody, podmiana, zmiana tekstu, naruszenie hasha, offset.
  - Odwołanie starego zatwierdzenia lip-sync/MP4 po nowej kwestii.
  - Napisy SRT bez nakładania kwestii.
  - Rzeczywisty miks FFmpeg do MP4 H.264 / AAC oraz SRT sidecar.
  - Kontaktsheet z prawdziwego MP4.
  - Backup WAV i restore z ponowną akceptacją.
  - Lokalne HTTP API i połączenie WAV V8.5 z V7 voice-plan bez opłat.

**Łącznie: 135 testów z sukcesem w osobnych grupach.** Wcześniejsza próba wykonania wszystkiego naraz przekroczyła limit czasu środowiska; nie została policzona jako zaliczona. 

Składnia: `python -m compileall ...`, `node --check web/app.js`. Wynik końcowy bezpośrednio poniżej / w logach roboczych.

**Niezweryfikowane:** graficzne działanie GUI w docelowym Windows, faktyczna generacja w Sogni Unlimited, rzeczywista naturalność polskich głosów i zgodność stylizowanych twarzy w nowym wideo. Testy nie są zastępstwem odsłuchu i oględzin filmu.
