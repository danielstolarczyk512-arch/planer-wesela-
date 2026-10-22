# Raport: Etap 4, dokumenty, usługodawcy, oferty i porównanie kosztów

Data: 2026-10-19. Format raportu wg sekcji 17 założeń projektu.

## Wykonane działania

| Obszar | Co działa |
|---|---|
| **Dokumenty** | Upload PDF, DOCX, JPG i PNG (do 20 MB). Typ rozpoznawany **po zawartości**, nie po rozszerzeniu ani nagłówku klienta. Wersjonowanie. Ten sam plik w weselu nie jest zapisywany ani przetwarzany drugi raz (SHA-256). Limity: 300 dokumentów i 1 GB na wesele. Pobieranie zawsze jako załącznik (`Content-Security-Policy: sandbox`, `nosniff`). Nazwy plików są tylko do wyświetlania; ścieżki generuje serwer. |
| **Bezpieczeństwo plików** | Ochrona przed zip bombą w DOCX (limity liczby elementów, rozmiaru i kompresji), przed bombą dekompresji obrazów (40 Mpx), PDF z hasłem jest odrzucany z czytelnym komunikatem, stary `.doc` też odrzucany z podpowiedzią. Limit rozmiaru żądania jest sprawdzany przed wczytaniem całości (413). |
| **Ekstrakcja tekstu** | W workerze, lokalnie (nic nie wychodzi na zewnątrz): pypdf dla PDF z tekstem (podział na strony z offsetami), python-docx dla DOCX (z tabelami), dla skanów render pypdfium2 i **OCR Tesseract (polski)**. Skan wykrywany automatycznie (mniej niż 30 znaków na stronę). Statusy `pending/processing/done/failed` z komunikatem dla użytkownika i ponowieniem. |
| **Moi usługodawcy** | 25 kategorii z mapowaniem na kategorie budżetu. Normalizacja nazwy, telefonu (format PL), domeny www i NIP (suma kontrolna). **Wykrywanie możliwych duplikatów**: podobieństwo nazw (`pg_trgm`), ten sam telefon, www, e-mail lub NIP. To podpowiedź dla pary, a nie blokada. Wyszukiwanie po nazwie. |
| **Oferty** | Komponenty cenowe: za osobę, za dziecko, ryczałt, za godzinę, za sztukę, procent; „w cenie”, „opcjonalne”, „poprawiny”, „kwota nieznana”. Warunki (fakty, bez oceny prawnej): zadatek/zaliczka, harmonogram płatności (data lub „N dni przed ślubem”), odwołanie, napoje, korkowe, nadgodziny. Oferta wpisana ręcznie jest zatwierdzona od razu, a jej edycja wymaga ponownego zatwierdzenia. Pola niepewne (`low/unverified`) trzeba potwierdzić jawnie. |
| **Cytaty z dokumentów** | Każdy komponent lub warunek może mieć cytat (strona + fragment). **Serwer sprawdza, że fragment naprawdę występuje w tekście dokumentu**, a w przeciwnym razie zwraca 422. To fundament pod Etap 5 (AI musi wskazać źródło każdej liczby). |
| **Porównanie kosztu całkowitego** | Deterministyczny silnik (`offers/pricing.py`): minimalna liczba gości, osobno dzieci (a bez ceny dziecięcej liczone jak dorośli, z ostrzeżeniem), niemowlęta bezpłatne, poprawiny z osobną liczbą gości, procent od sumy, zaokrąglenie do grosza. Pozycje bez kwoty trafiają do „nieznane”, **nigdy nie są liczone jako 0 zł**. Liczba gości: planowana, zaproszeni (z listy, wg wieku) albo potwierdzeni, lub podana ręcznie. Wynik: suma, koszt na dorosłego, różnica do najtańszej, rozbicie, ostrzeżenia i neutralne flagi brakujących warunków (np. „brak warunków odwołania”). |
| **Wybór oferty** | Jednym wywołaniem: pozycja budżetu (właściwa kategoria wg rodzaju usługodawcy), **płatności z warunków oferty** (zadatek i raty z datami liczonymi od daty ślubu), usługodawca „zarezerwowany”, konkurencyjne oferty tej kategorii odrzucone. Wszystko w dzienniku audytu. |
| **Docker** | Obraz z Tesseractem (`tesseract-ocr-pol`). Wspólny wolumen plików dla api i workera. Nowy etap obrazu `test` i `task test:docker`: cały zestaw testów w kontenerze z tymi samymi bibliotekami co produkcja. |
| **Kopie zapasowe** | `task backup` archiwizuje teraz **również pliki dokumentów** (wcześniej tylko bazę). |
| **Eksport RODO** | Eksport wesela zawiera usługodawców, oferty z komponentami i warunkami oraz dokumenty (metadane i tekst). |

### Wyniki weryfikacji

| Kontrola | Wynik |
|---|---|
| Testy w Dockerze (`task test:docker`, z OCR) | **454 passed**, 1 skipped (test zachowania „bez Tesseracta”, sensowny tylko na hoście) |
| Testy na hoście (`task test`) | **451 passed**, 4 skipped (OCR, bo na laptopie nie ma Tesseracta; te 4 przechodzą w Dockerze) |
| Pokrycie | **92%** (próg 85%) |
| Korpus 20 syntetycznych ofert | 10 PDF + 6 DOCX: wszystkie oczekiwane frazy znalezione; 4 skany (PNG, JPG, 2 PDF bez tekstu): OCR rozpoznał ceny, minimum gości i zadatek |
| Porównanie vs ręczne wyliczenia | 6 scenariuszy jednostkowych + 3 API, każdy z wyliczeniem w komentarzu; test własności (Hypothesis): suma nieujemna i rosnąca z liczbą gości |
| Złośliwe/wadliwe pliki | exe, stary .doc, HTML, ZIP nie-DOCX, zip bomba, zaszyfrowany PDF, uszkodzony PDF/PNG: odrzucone lub `failed` z komunikatem, nigdy 500 |
| Test IDOR | 81 tras `/weddings/{id}/…` (w tym upload multipart): 404 dla obcych, 401 bez logowania |
| Schemathesis | 110 operacji bez błędów 500 |
| Ruff, mypy `--strict`, Bandit, pip-audit, Gitleaks | czysto |
| Licencje | brak AGPL/SSPL/GPL (nowe: pypdf BSD, python-docx MIT, pypdfium2 Apache/BSD, pytesseract Apache, Pillow MIT-CMU, python-multipart Apache, dev: reportlab BSD) |
| Trivy (obraz z Tesseractem) | 0 HIGH/CRITICAL |
| `task smoke` (Docker) | 17/17, w tym PDF → tekst i skan → OCR w prawdziwym workerze, oferta z cytatem, porównanie, wybór → budżet + zadatek |
| `task backup` | baza: 31 tabel odtworzonych w próbie; pliki: archiwum tar.gz zweryfikowane |

## Decyzje

| Decyzja | Uzasadnienie | Alternatywa |
|---|---|---|
| OCR: Tesseract w obrazie Dockera, nie na laptopie | instalator Windows wymaga uprawnień administratora; kontener daje identyczne środowisko jak produkcja | instalacja ręczna przez użytkownika (niepotrzebna) |
| `pypdf` + `pypdfium2` zamiast PyMuPDF | PyMuPDF jest na AGPL (ADR-0006) | — |
| Brak OCRmyPDF | wymaga Ghostscript (AGPL) | — |
| Pliki w lokalnym wolumenie z interfejsem `Storage` | zero kosztów w dev; S3-compatible przy wdrożeniu bez zmian w logice | MinIO (AGPL, odrzucone) |
| Usuwanie plików wesela przez kolejkę | baza usuwa się w transakcji, a pliki dopiero po commit (brak usuniętych plików przy wycofanej transakcji) | synchronicznie w żądaniu |
| Duplikaty jako podpowiedź, nie blokada | dwie różne firmy mogą mieć podobne nazwy; decyzja należy do pary | twarda unikalność |
| Oferty prywatne dla wesela | zgodnie z iteracją 4: bez agregacji cen między weselami | — |
| Cytaty weryfikowane przez serwer | „AI nie może zmyślić liczby”: fragment musi istnieć w tekście dokumentu | zaufanie do modelu (odrzucone) |
| `ON DELETE NO ACTION` dla kategorii pozycji budżetu (zamiast RESTRICT) | RESTRICT blokowałby kaskadowe usunięcie wesela z pozycjami budżetu; test regresyjny dodany | — |

Koszt: 0 zł (wyłącznie OSS, lokalnie). Obraz urósł o pakiety Tesseracta, skan nie wykazał podatności.

## Problemy i ograniczenia

- Aktualna lista: [znane-ograniczenia.md](znane-ograniczenia.md) (nowe: brak skanu antywirusowego, HEIC, S3 w produkcji, jakość OCR dla zdjęć z telefonu).
- Pliki zapisywane są przed `commit` transakcji: przy rzadkiej awarii bazy może zostać osierocony plik (sprzątanie okresowe w Etapie 6).
- Jakość OCR sprawdzono na czystych, wygenerowanych skanach. Zdjęcia z telefonu (krzywe, cienie) wymagają testów na prawdziwych materiałach (za zgodą par, w Etapie 5 lub 6).

## Następny krok: Etap 5 (AI)

Warunki rozpoczęcia: akceptacja Etapu 4 oraz **decyzja o dostawcy LLM** (lokalny Ollama czy zewnętrzny z umową powierzenia, zob. ADR-0005).

Zakres: `LLMProvider` (Fake, Ollama, opcjonalnie zewnętrzny), `OfferExtractor`: tekst dokumentu → szkic oferty (komponenty i warunki) **z cytatami weryfikowanymi przez istniejący mechanizm**, status `needs_review`, wersjonowane prompty, cache po SHA-256, limity kosztów, wyłącznik, redakcja PII, testy regresji na korpusie 20 ofert oraz testy prompt injection.
