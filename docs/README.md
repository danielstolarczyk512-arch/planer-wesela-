# Dokumentacja: Wedding Planner AI

Status: **Etapy 0–5 zakończone (z harmonogramem dnia i planem stołów). Etap 6 (stabilizacja, dokumentacja wdrożeniowa) wykonany; czeka decyzja o hostingu.** Instrukcja uruchomienia: [../README.md](../README.md).

| Dokument | Zawartość |
|---|---|
| [etap-6-raport.md](etap-6-raport.md) | raport Etapu 6: bezpieczeństwo kont, retencja, rotacja klucza, S3, limity, testy obciążeniowe, staging produkcyjny |
| [wdrozenie.md](wdrozenie.md) | runbook: wdrożenie, aktualizacje, kopie i próba odtworzenia, rotacja klucza, monitorowanie, incydenty RODO |
| [hosting.md](hosting.md) | **do decyzji:** warianty hostingu i AI, wymagania z testów |
| [gui/raport-krok-3.md](gui/raport-krok-3.md) | **GUI krok 3:** 5 zakładek, widoki Dziś, Plan, Budżet, Goście, Więcej |
| [gui/raport-krok-1-2.md](gui/raport-krok-1-2.md) | **GUI kroki 1–2:** szkielet PWA, tokeny, motywy, komponenty bazowe, logowanie z bezpieczną sesją, testy (axe, 4 szerokości, CSP) |
| [gui/GUI-SPEC-v1.1.md](gui/GUI-SPEC-v1.1.md) | **GUI:** analiza paczki „Nasz dzień” v1.0 i ulepszenia (kontrast, zgodność z API, brakujące ekrany, stos, narzędzia); projekt i podgląd w [../design/](../design/README.md) |
| [etap-5-raport.md](etap-5-raport.md) | raport Etapu 5: odczyt ofert przez lokalny model, walidacja, ewaluacja; harmonogram dnia; plan stołów |
| [ai-ewaluacja.md](ai-ewaluacja.md) | wyniki ewaluacji modeli na korpusie ofert (generowane: `task ai:eval`) |
| [etap-4-raport.md](etap-4-raport.md) | raport Etapu 4: dokumenty i OCR, usługodawcy, oferty, porównanie kosztów, wyniki kontroli |
| [etap-3-raport.md](etap-3-raport.md) | raport Etapu 3: planer, budżet, goście, RSVP, poprawione błędy, wyniki kontroli |
| [etap-2-raport.md](etap-2-raport.md) | raport Etapu 2: fundament backendu |
| [znane-ograniczenia.md](znane-ograniczenia.md) | znane ograniczenia i plan ich usunięcia |
| [tools-report.md](tools-report.md) | Etap 0 + zależności Etapu 2: narzędzia, licencje, pluginy Claude Code, laptop vs Synology |
| [licenses.md](licenses.md) | raport licencji zależności (generowany: `task licenses`) |
| [openapi.json](openapi.json) | specyfikacja API (generowana: `task openapi`) |
| [analysis/01-rynek-i-konkurencja.md](analysis/01-rynek-i-konkurencja.md) | rynek, konkurencja (ze źródłami), proces polskiego wesela, hipotezy |
| [analysis/02-iteracje-i-mvp.md](analysis/02-iteracje-i-mvp.md) | 4 iteracje optymalizacji, koncepcja MVP, redukcja agentów AI |
| [architecture.md](architecture.md) | architektura i diagramy Mermaid |
| [adr/](adr/README.md) | decyzje architektoniczne 0001–0007 |
| [data-model.md](data-model.md) | model danych (docelowy; Etap 2 implementuje identity, workspace, audit, jobs) |
| [api.md](api.md) | konwencje API v1, lista endpointów i status implementacji |
| [plan-koszty-ryzyka.md](plan-koszty-ryzyka.md) | plan etapów, koszty, rejestr ryzyk |
