# Zmiany V8 — 2026-10-29

- Nowy `studio/voice_v8.py`: niezależne warianty polskiego dialogu, profile emocji, lokalne generowanie A/B i świadome zatwierdzenie.
- `studio/chatterbox_worker_v8.py`: opcjonalny osobny worker Chatterbox Multilingual V3, bez płatnego API, uruchamiany tylko na żądanie.
- `studio/pace_v8.py`: nieniszczący audyt tempa scen i proponowane punkty skrótów.
- `studio/product_demo_v8.py`: nowe pionowe kadrowanie rzeczywistego nagrania z UI.
- `qc/motion_v8.py`: rzeczywisty pomiar zmian klatek przez FFmpeg.
- Nowe chronione trasy `/api/v8`, kontrola zgody i wymowy, walidacja zmiany głosu przez SHA256.
- Interfejs `Studio V8 · głos i montaż` i nowa wersja cache PWA.
- Integracja wybranego audio z procesem Reżysera V7, weryfikacja referencji i obowiązkowa ręczna kontrola ust.
- Zabezpieczenia odmowy montażu z niezatwierdzonymi wariantami głosu lub UI po nowym kadrowaniu.
- Zachowane moduły V7, 60 grafik referencyjnych i lokalny montaż FFmpeg.
