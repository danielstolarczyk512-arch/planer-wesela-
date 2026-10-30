# Raport testów V8.4 — 2026-10-29

**PASS: 120/120 testów unittest** (`python -m unittest discover -s tests -q`, czas ostatniego uruchomienia ~24 s).

Nowe testy: 180 sekund i przypisane dialogi; dwa różne scenariusze koncepcyjne; lokalny Script Doctor bez zewnętrznego API; plan renderów i blokada niepewnych zadań; backup prawdziwego katalogu `v7_renders`, restauracja ZIP jako nowe ID, SHA256 i ochrona oryginału; kontrola metadanych, endpointy HTTP oraz edycja dialogu z unieważnieniem dawnej akceptacji głosu i lip-sync.

Potwierdzono również składnię `node --check web/app.js` i `compileall` (Python).

**NIE POTWIERDZONO**: płynności i wyglądu panelu w prawdziwej przeglądarce Windows. Przeglądarka Chromium w dostępnym środowisku zwróciła `ERR_BLOCKED_BY_ADMINISTRATOR` przy otwieraniu lokalnego HTTP. Nie uruchamiano Sogni ani Chatterbox; nie wygenerowano filmu, klatki ani nowych głosów. Regułowy audyt nie udowadnia spójności tożsamości, synchronizacji fonemów ani jakości artystycznej.

**Bezpieczeństwo**: generacje nadal wyłącznie po zgodzie w trybie `subscription`. Stare workflow z backupu nie są automatycznie wznawiane. Blokada jednoczesnego submitu działa w ramach pojedynczego serwera i wspólnego locka SQLite; uruchamianie wielu niezależnych instancji serwera na tej samej bazie nie jest wspierane.
