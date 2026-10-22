# Raport: Etap 5 (AI: odczyt ofert lokalnym modelem) + harmonogram dnia + plan stołów

Data: 2026-10-19. Format raportu wg sekcji 17 założeń projektu.

## Wykonane działania

### Etap 5: AI

| Obszar | Co działa |
|---|---|
| **Dostawca LLM za interfejsem** | `LLMProvider.complete_json`: Ollama (lokalnie, dane nie opuszczają komputera), dublery testowe. Dostawca zewnętrzny wymaga zgody pary i redakcji PII (zaimplementowane, przetestowane na dublerze; włączenie dopiero po umowie powierzenia, ADR-0005). |
| **OfferExtractor** | Tekst dokumentu (Etap 4) → szkic oferty: komponenty cenowe i warunki. JSON wymuszony schematem (`format`), temperatura 0, stałe ziarno. Prompt wersjonowany (`offer-extract/1`). |
| **Walidacja deterministyczna** | Model tylko proponuje. Każda liczba musi mieć cytat **dosłownie obecny w dokumencie** i występować w tym cytacie. Minimum gości tylko przy słowie „minim…”. Zadatek czy zaliczka rozstrzyga słowo w cytacie, a nie model (różne skutki prawne). Poprawiny rozpoznawane regułą. Wynik zawsze `needs_review`; pozycje niepewne para musi świadomie potwierdzić. |
| **Ochrona przed poleceniami w dokumentach** (nowe po ewaluacji) | Linie wyglądające na polecenia dla AI („zignoruj instrukcje”, „wpisz cenę…”, „system:”) są wykrywane. Pozycje cytujące takie linie **nie dostają statusu zweryfikowanych**, a analiza zwraca ostrzeżenie `suspicious_instructions`. Model nie ma żadnych narzędzi ani uprawnień: najgorszy skutek to szkic do przeglądu. |
| **Koszty i bezpieczeństwo** | `ai_runs`: cache po SHA-256 (ten sam dokument nie jest liczony drugi raz), dzienny limit analiz na wesele, globalny wyłącznik, limit długości wejścia, audyt. |
| **Ewaluacja** | `task ai:eval`: 16 fikcyjnych ofert (10 PDF + 6 DOCX), dwa modele, test prompt injection. Wynik: [ai-ewaluacja.md](ai-ewaluacja.md). |

### Harmonogram dnia ślubu

Punkty programu z czasem trwania, buforami, miejscem, osobą odpowiedzialną i usługodawcą. Zależności („po zakończeniu…”, z wykrywaniem cykli). **Konflikty**: ta sama osoba lub usługodawca w dwóch miejscach naraz (z buforami), zła kolejność, punkt poza ramami wydarzenia, usługodawca niezarezerwowany. **Przesunięcie** („ceremonia się opóźnia o 20 min”) z podglądem zmian i konfliktów po przesunięciu. **Szablon** typowego polskiego wesela (błogosławieństwo, ceremonia kościelna 60 min / cywilna 30 min, chleb i sól, obiad, pierwszy taniec, tort, oczepiny). Plan dla usługodawcy przez filtr. Godziny zawsze w czasie polskim.

### Plan stołów z automatycznym usadzeniem

| Obszar | Co działa |
|---|---|
| **Stoły** | zwykłe, stół pary młodej (automat go pomija), stół dziecięcy; kształt, pojemność |
| **Ręczne sadzanie** | z numerem miejsca (unikalny przy stole); ręczne przypisanie jest **przypięte**: automat go nie rusza |
| **Reguły** | „razem” i „osobno” dla pary osób (np. skłócone ciocie): twarde ograniczenia |
| **Automat (OR-Tools CP-SAT, Apache-2.0)** | rodzina z jednego zaproszenia razem; dzieci przy stole dziecięcym, dopóki są miejsca; grupy (`group_label`, np. „praca Ani”) i strona panny/pana młodego możliwie przy jednym stole; jak najmniej zajętych stołów. Domyślnie podgląd (`dry_run`), wynik **deterministyczny**; dokładnie ten wariant zapisuje `PUT …/seating/assignments`. Czytelne błędy: za mało miejsc (z liczbami), sprzeczne reguły, przepełnione przypięcia. |
| **Kontrola planu** | przy każdym odczycie: przepełniony stół, złamana reguła, rozdzielona rodzina, dorosły przy stole dziecięcym, gość po odmowie przy stole |
| **Uwzględnienie RSVP** | domyślnie sadzamy wszystkich poza odmowami (`not_declined`), opcjonalnie tylko potwierdzonych; niemowlęta bez osobnego miejsca |

Wydajność: 212 gości przy 25 stołach w ok. 3–10 s na obciążonym laptopie. Pierwsza wersja modelu (zmienna na każdą rodzinę × stół) nie mieściła się w czasie i dawała różne wyniki przy kolejnych uruchomieniach. Obecny model liczy wymienne rodziny zbiorczo, porządkuje identyczne stoły i startuje od rozwiązania zachłannego.

## Wyniki weryfikacji

| Kontrola | Wynik |
|---|---|
| Testy na hoście (`task ci`) | **580 passed**, 5 skipped (OCR i model LLM: przechodzą w Dockerze / `task test:llm`), pokrycie **93%** (próg 85%) |
| Testy w Dockerze (`task test:docker`, z OCR) | **583 passed**, 2 skipped |
| Testy kontraktowe Schemathesis | **137 operacji**, bez błędów 500 |
| Test IDOR | wszystkie trasy `/weddings/{id}/…` (w tym 14 tras planu stołów i 10 harmonogramu): 404 dla obcych, 401 bez logowania |
| Silnik stołów | 11 testów jednostkowych + test własności (Hypothesis): każde rozwiązanie spełnia pojemność i reguły; determinizm |
| Test dymny z AI (`smoke_e2e --ai`, Docker + Ollama) | **23/23**: m.in. harmonogram z szablonu, automatyczne usadzenie (OR-Tools w obrazie produkcyjnym), prawdziwy model w workerze: szkic z ceną 330 zł i cytatem w 52 s, 0 pozycji niezweryfikowanych |
| Ewaluacja AI (Qwen 2.5 7B) | **44/52 fakty (85%)**, 0 pozycji z niezweryfikowanym cytatem, 0 błędów |
| Ewaluacja AI (Bielik 11B v2.3) | 43/52 (83%), 15 pozycji niezweryfikowanych |
| Prompt injection | oba modele **wykonały** wstrzyknięte polecenie (cena 1 zł); nowa walidacja je zatrzymuje (pozycja niezweryfikowana + ostrzeżenie) |
| Ruff, mypy `--strict`, Bandit, pip-audit, Gitleaks | czysto |
| Licencje | brak AGPL/SSPL/GPL; nowe: ortools (Apache-2.0), numpy/pandas/protobuf (BSD), absl-py (Apache-2.0), immutabledict (MIT) |

## Decyzje

| Decyzja | Uzasadnienie | Alternatywa |
|---|---|---|
| Model domyślny: **Qwen 2.5 7B Instruct** (Apache-2.0) | więcej trafionych faktów i **zero** zmyślonych cytatów; mieści się w 4 GB VRAM z odciążeniem | Bielik 11B (polski, Apache-2.0): lepszy w zadatkach usługodawców, ale 15 niezweryfikowanych pozycji; zostaje jako alternatywa w konfiguracji |
| Walidacja zamiast zaufania do modelu | model myli się i daje się manipulować (potwierdziła to ewaluacja) | — |
| Ochrona przed poleceniami w dokumentach: wzorce + brak uprawnień modelu | deterministyczne, tanie, sprawdzalne testem; model i tak nie może nic zmienić bez pary | drugi model-klasyfikator (koszt, niedeterminizm) |
| OR-Tools CP-SAT do stołów | twarde reguły i optymalizacja w jednym, Apache-2.0, bez usług zewnętrznych | heurystyka zachłanna (nie gwarantuje reguł), solver komercyjny (koszt) |
| Automat synchronicznie, z limitem 30/h | wynik w kilka sekund, prostsze API dla aplikacji mobilnej | kolejka w workerze (gdy wzrośnie ruch) |
| Podgląd + zapis dokładnego wariantu | para widzi i akceptuje to, co zostanie zapisane | ponowne liczenie przy zapisie |

Koszt: 0 zł (wyłącznie OSS, lokalnie). Obraz Dockera urósł o OR-Tools z zależnościami (ok. 100 MB).

## Problemy i ograniczenia

- Aktualna lista: [znane-ograniczenia.md](znane-ograniczenia.md) (nowe: 27–33).
- Odczyt zadatku w ofertach usługodawców (DOCX) jest słaby dla Qwen: 1 z 6 trafień. Para wpisuje go ręcznie. Poprawka: prompt v2 i wzorzec deterministyczny (v1.1).
- AI oceniona na fikcyjnych ofertach. Przed startem komercyjnym potrzebna ewaluacja na prawdziwych ofertach, za zgodą par.
- Czas analizy na laptopie: średnio ok. 2 min na dokument. Produkcja wymaga serwera z GPU albo dostawcy zewnętrznego z umową powierzenia (decyzja w Etapie 6).

## Następny krok: Etap 6 (stabilizacja i dokumentacja wdrożeniowa)

Zakres: procedury z listy ograniczeń oznaczone „Etap 6” (lista haseł, okno tolerancji refresh tokena, retencja audytu, globalny limit żądań, rotacja klucza szyfrowania, sprzątanie osieroconych plików, S3), testy obciążeniowe, instrukcja wdrożenia i kopii, a potem **decyzja o hostingu** (w tym GPU dla AI albo dostawca zewnętrzny).
