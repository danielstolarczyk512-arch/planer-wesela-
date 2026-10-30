# Zmiany V8.2 względem V8

- `studio/visual_lock_v82.py` — nowy lokalny moduł Master Visual Lock: cztery wersjonowane wzorce, SHA-256, stan zatwierdzenia, zmiana obrazu z zachowaniem historii nieużywanych wersji.
- `server.py` — endpointy `/api/v82/masters`, `/api/v82/projects/...` i walidacja projektu, akceptacji oraz lokalnej klatki przed zleceniem generacji. Bezpieczne, ręczne przesyłanie nowego wzorca PNG/JPG.
- `studio/personas.py` — skorygowano zbyt silnie kreskówkowe określenia, wyraźne rozdzielenie stylu/wyglądu postaci/ubrania w trybie V8.2.
- `web/app.js` — nowa zakładka z przeglądem, akceptacją masterów, aktywacją per projekt i kontrolą klatek poszczególnych ujęć.
- `web/sw.js` — nowa wersja pamięci PWA, ogranicza ryzyko wyświetlania starego panelu.
- `tests/test_v82.py` — nowe testy regresyjne i integracyjne bez Sogni.
- Bez zmian w istniejących modelach głosu V8, montażu, bibliotece 60 referencji i metodach abonamentowych Sogni.
