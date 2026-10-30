# CHANGELOG — V6 CAMERA 360 + CHARACTER CHECKPOINT

- Zaimportowano 60 pojedynczych referencji z ZIP użytkownika, z oryginalnymi statusami QA.
- Dodano zatwierdzanie / odrzucanie i osobny wybór referencji pod kąty ujęć.
- Dodano `Identity Lock` (fail-closed) i oddzielne synchronizowanie referencji do Sogni.
- Dodano kreator planów Sogni 360 (6 presetów / 96 konfiguracji) oraz krytykę ryzyk.
- Dodano opcjonalny render **pojedynczego** kąta przez oficjalny CLI, z `--billing-mode subscription` i osobną zgodą.
- Dodano import nowego kąta jako klatki początkowej do istniejącego workflow H3.
- Dodano lokalne heurystyki kontroli klipów i dodatkowe testy regresyjne.
- Zaktualizowano interfejs, service worker i dokumentację.
- Nie uruchomiono płatnych ani rzeczywistych generacji Sogni w trakcie przygotowania paczki.

## V6.1 — poprawki z weryfikacji pełnego procesu (29.10.2026)

- `studio/camera360_cli.py`: wynik CLI z dopiskiem kąta w nazwie (`<id>-front-right.png`) jest odnajdywany; JPEG/WEBP zapisany pod nazwą `.png` jest konwertowany do prawdziwego PNG (flaga `--output-format png` + kontrola sygnatury);
  rozmiar wyniku zgodny z proporcjami źródła (`-w/-h`, wcześniej CLI renderował kwadrat 512×512); komunikat błędu zawiera bezpieczny ogon wyjścia CLI (klucz i adresy zamaskowane).
- Testy: izolacja od prawdziwych decyzji recenzji (`data/references_v6`), poprawka porównania sumy czasów w `test_v4`, 5 nowych testów regresji. Razem 75 testów.
