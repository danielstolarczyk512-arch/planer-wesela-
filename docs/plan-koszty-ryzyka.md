# Plan wdrożenia, koszty i ryzyka

## 1. Plan wdrożenia (Etapy 2–6 dostosowane do MVP)

| Etap | Zakres | Kryteria akceptacji |
|---|---|---|
| **2. Fundament** | repo + `uv`, struktura modułów, `compose.yaml` (postgres, api, worker, mailpit), konfiguracja przez env, Alembic, logowanie JSON, błędy RFC 9457, `identity` (rejestracja, weryfikacja, logowanie, refresh, reset, sesje, zgody), `workspace` (wesela, wydarzenia, członkowie, zaproszenia), audyt, `Taskfile`, pre-commit (Ruff, Gitleaks), CI lokalne | `task up` stawia środowisko na czystej maszynie; migracje up/down/up; testy uprawnień i IDOR dla każdego endpointu; pokrycie ≥ 85% w `identity`/`workspace`; `pip-audit`, Bandit, Gitleaks bez błędów krytycznych; OpenAPI kompletne |
| **3. Planer, budżet, goście** | zadania z szablonu + `reschedule` z `dry_run`, budżet + płatności zadatek/zaliczka, przegląd budżetu, gospodarstwa, goście, RSVP przez link, import CSV, przypomnienia (worker + e-mail dzienny) | testy jednostkowe obliczeń (Hypothesis dla kwot i przesunięć dat); testy RSVP (gość nie widzi innych gospodarstw); retencja gości testowana |
| **4. Dokumenty i oferty** | storage (lokalny/S3), upload z walidacją, wersje, ekstrakcja pypdf/python-docx/Tesseract, oferty + komponenty cenowe, **porównanie**, wybór → budżet; „moi usługodawcy” + wykrywanie duplikatów (pg_trgm) | zestaw ≥ 20 **syntetycznych** ofert (PDF tekstowy, skan, DOCX) z oczekiwanym tekstem; porównanie zgodne z ręcznymi wyliczeniami; złośliwe pliki (zła sygnatura, zip-bomb, zaszyfrowany PDF) odrzucone |
| **5. AI** | `LLMProvider` (Fake, Ollama, opcjonalnie zewnętrzny), `OfferExtractor`, prompt v1, walidacja cytatów, cache, limity, kill-switch, redakcja PII | testy regresji na syntetycznym zbiorze: precyzja pól kwotowych ≥ 95% *dla pól oznaczonych jako pewne*, 0 pól bez cytatu oznaczonych jako pewne; testy prompt injection (dokument z instrukcjami); pomiar tokenów/kosztu |
| **6. Stabilizacja** | testy obciążeniowe (Locust, MIT), test odtwarzania backupu na NAS, testy usuwania/eksportu, audyt licencji, Trivy na obrazie, dokumentacja | backup odtworzony od zera; p95 < 300 ms dla list przy 100 równoległych użytkownikach na laptopie; raport licencji bez AGPL |

Równolegle (właściciel produktu, poza kodem): wywiady z parami (hipotezy z dok. 01, sekcja 6), konsultacja prawna (rola RODO, regulamin, DPIA, granica „porady prawnej”).

## 2. Koszty

| Kategoria | Dev / prototyp | Start komercyjny (szacunek rzędu wielkości) [H] |
|---|---|---|
| Narzędzia i biblioteki | 0 zł (wyłącznie OSS z licencjami komercyjnymi) | 0 zł |
| Infrastruktura | 0 zł (laptop + Synology) | VPS UE + storage + backup: kilkadziesiąt–kilkaset zł/mies. |
| LLM | 0 zł (Fake/Ollama) | zależne od wolumenu; mierzone per uruchomienie; limit w planie Free chroni koszt |
| E-mail | 0 zł (Mailpit) | darmowe progi dostawców na start |
| Prawo (jednorazowo) | — | regulamin, polityka prywatności, DPA, DPIA, opinia ws. porady prawnej: **największy koszt startowy**, wycena u prawnika |
| Domena, sklepy z aplikacjami | — | konto Apple Developer (opłata roczna), Google Play (opłata jednorazowa); dopiero przy GUI |

Konkretne ceny dostawców (VPS, LLM, e-mail) sprawdzę w aktualnych cennikach przy wyborze dostawcy. Nie podaję ich z pamięci.

## 3. Rejestr ryzyk

| # | Ryzyko | P-stwo | Wpływ | Mitygacja | Właściciel |
|---|---|---|---|---|---|
| R1 | **Pary nie zapłacą**, bo lider daje planer za darmo | wysokie | krytyczny | pozycjonowanie na oferty/umowy/płatności; test gotowości do zapłaty przed budową płatności; drugi strumień B2B | produkt |
| R2 | Zbyt mały rynek (ok. 133 tys. ślubów/rok, spada) | wysokie | wysoki | niski koszt stały, B2B, ekspansja (model danych wielowalutowy i wielojęzyczny) | produkt |
| R3 | Jakość ekstrakcji AI z polskich ofert niewystarczająca | średnie | wysoki | zatwierdzanie przez człowieka, cytaty, zestaw regresyjny, wybór modelu po teście, ręczna ścieżka zawsze dostępna | tech |
| R4 | Błąd AI powoduje szkodę finansową (zły zadatek/termin) | średnie | wysoki | brak automatycznego zapisu do budżetu, oznaczenia niepewności, disclaimer, logi `ai_runs` | tech/prawo |
| R5 | Uznanie funkcji za poradę prawną | niskie–średnie | wysoki | tylko ekstrakcja faktów, brak oceny; opinia prawna przed v2 | prawo |
| R6 | Naruszenie RODO (dane gości, zdrowie, umowy) | średnie | krytyczny | minimalizacja, szyfrowanie, retencja, DPA, DPIA, testy usuwania | prawo/tech |
| R7 | Wyciek danych do dostawcy LLM | niskie (domyślnie lokalnie) | wysoki | ADR-0005: zgoda, DPA, UE, redakcja PII | tech |
| R8 | Naruszenie praw do baz danych / regulaminów przy katalogu | niskie (brak scrapingu) | wysoki | katalog tylko z danych od firm (v1.2+), źródło i podstawa prawna w rekordzie | produkt/prawo |
| R9 | Zależność na licencji AGPL trafia do produkcji | niskie | wysoki | ADR-0006 + `pip-licenses` w CI | tech |
| R10 | Konsolidacja globalnych graczy (TKWW + Zola) i wejście z AI do PL | średnie | średni | szybkość, specyfika polska (zadatek/zaliczka, poprawiny, talerzyk) | produkt |
| R11 | Jeden deweloper = bus factor | wysokie | średni | dokumentacja, ADR-y, odtwarzalne środowisko, testy | właściciel |
| R12 | Uprawnienia do `D:\aplikacjaweselna` i niedziałający Docker blokują Etap 2 | rozwiązane (Etap 2) | — | uprawnienia nadane, Docker działa | użytkownik |
| R13 | Koszt AI w produkcji (GPU lub dostawca zewnętrzny) przewyższa przychody | średnie | średni | start z AI wyłączonym, włączenie po potwierdzeniu popytu ([hosting.md](hosting.md)) | właściciel |

## 4. Decyzje wymagające akceptacji użytkownika

1. **Pozycjonowanie**: „oferty, umowy, płatności” zamiast „pełny planer + katalog”. Katalog publiczny dopiero w v2.
2. **Monetyzacja do testu**: Free + jednorazowe Premium za wesele (cena do testu), B2B później. Zamiast „299 zł / 24 mies.”.
3. **Jeden agent LLM w MVP** (`OfferExtractor`), reszta deterministycznie.
4. **Zakres MVP i kolejność etapów** jak w sekcji 1.
5. **Konsultacja prawna** przed udostępnieniem komukolwiek spoza zespołu.
