# Raport testów Film Studio V7 — 29.10.2026

## Wykonane testy

- `python -m unittest discover -s tests -q` → **80/80 OK** (24 s), w tym 5 nowych przypadków V7.
- `node --check web/app.js` → składnia poprawna.
- `python -m compileall -q studio qc director server.py montaz.py` → sukces.
- Backend HTTP: tworzenie projektu, zaplanowanie zbliżenia twarzy, upload prawdziwego WAV 5,3 s, przypisanie mowy do mówiącego, żądanie bez zgody odrzucone, ręczna akceptacja ust bez aktualnego klipu odrzucona, gotowość projektu informuje o brakujących etapach V7.
- Model FastH3 IA2V w przepisie CLI: `--ref`, `--ref-audio`, `--billing-mode subscription`; testy offline nie uruchamiają żadnej generacji.
- Kod nie przechodzi automatycznie na płatne modele. Każdy zdalny render wymaga aktywnego Unlimited i wyraźnej zgody.
- Materiały wejściowe: 4 filmiki; `1.mp4` i `jm8Jkf-Icit-aOHkigGL4w.mp4` są dokładnymi duplikatami SHA256.

## Niezweryfikowane lub ograniczone

- **Nie wykonano prawdziwej generacji w Sogni**; brak testu jakości polskiego lip-sync na koncie użytkownika.
- **Nie przeprowadzono wiarygodnego odsłuchu dialogów**; ocena syntetycznego głosu opiera się również na wcześniejszym raporcie produkcji.
- Playwright + Chromium: `ERR_BLOCKED_BY_ADMINISTRATOR` dla lokalnego `http://127.0.0.1:8829`. Dlatego **wizualny test przeglądarkowy jest NIEZALICZONY**.
- Opcjonalny pomiar zmian pikseli w obszarze ust jest wskaźnikiem ruchu, nie wykrywaczem zgodności polskich fonemów.
- Presety kamer i coverage planują pracę kamery, nie generują automatycznie wszystkich nowych kadrów. Prawdziwy orbitalny ruch 360° wymaga dodatkowych, zatwierdzonych kątów i rzeczywistych klipów.
- Kompatybilność importu z kontem Sogni i jakość nowego modelu IA2V muszą zostać sprawdzone na własnym komputerze, bez uruchamiania płatnego fallbacku.

## Bezpieczeństwo

- Żaden klucz API nie jest częścią źródeł lub paczki.
- Archiwum zawiera prywatne projekty i zatwierdzenia dostarczone w `orbit.zip`, nie publikuj go w publicznym repozytorium.
- Generacja zewnętrzna używa wyłącznie `--billing-mode subscription`. Jeśli Sogni nie potwierdza rozliczenia abonamentowego, wynik nie jest traktowany jako poprawnie rozliczony i wymaga ręcznego sprawdzenia.
