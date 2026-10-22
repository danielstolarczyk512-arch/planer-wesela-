# 02. Cztery iteracje optymalizacji i finalna koncepcja MVP

Podstawa: [01-rynek-i-konkurencja.md](01-rynek-i-konkurencja.md). Oznaczenia [Z]/[W]/[H] jak w dokumencie 01.

---

## Iteracja 1: analiza produktowa

### Zidentyfikowane problemy

1. **Podstawowy planer jest za darmo u lidera** (zadania, budżet, goście, stoły, współpraca we dwoje, aplikacja mobilna) [Z]. Premium 299 zł za „lepszy planer” nie ma uzasadnienia.
2. **Katalog firm jako fundament MVP jest nierealny.** Lider ma ponad 41 tys. firm [Z]. Legalnie można budować katalog tylko z danych od firm, a to wymaga ruchu, którego na starcie nie mamy. Problem jajka i kury.
3. **Rynek jest mały i się kurczy** (ok. 133 tys. ślubów rocznie [W]). B2C Premium daje w realistycznym scenariuszu ok. 200 tys. zł/rok [H].
4. **13 agentów AI to przerost.** Większość wymienionych „agentów” to zwykła logika (budżet, konflikty, duplikaty, stoły).
5. **Ślub to zdarzenie jednorazowe.** Abonament „24 miesiące” to w praktyce opłata jednorazowa, a słowo „abonament” zniechęca.

### Proponowane poprawki

- **Nowe pozycjonowanie:** nie „kolejny planer”, tylko **„asystent, który rozumie Wasze oferty i umowy i pilnuje pieniędzy oraz terminów”**.
- Rdzeń wartości (przewaga):
  1. wgranie oferty lub umowy (PDF/DOCX/zdjęcie) → ustrukturyzowane dane (cena za osobę, minimum gości, dzieci, napoje, poprawiny, zadatek, terminy płatności) **z cytatem źródła i do ręcznego zatwierdzenia**;
  2. **porównanie realnego kosztu całkowitego** ofert przy tej samej liczbie gości, z rozbiciem;
  3. **harmonogram płatności** (zadatek/zaliczka/dopłata) i przypomnienia;
  4. budżet liczony **dynamicznie z liczby potwierdzonych gości**.
- Funkcje „higieniczne”, czyli prostsze niż u lidera, ale obecne, bo bez nich para nie przeniesie się do nas: zadania z szablonu, goście i RSVP, współpraca we dwoje.
- **Katalog → „Moi usługodawcy”.** Para dodaje firmy, które sama znalazła (nazwa, link, kontakt, oferta). Zero kopiowania i zero ryzyka prawnego. Katalog publiczny dopiero po walidacji, z danych od firm.
- **Monetyzacja (hipoteza):**
  - Free: planer, goście, budżet, ręczne oferty i porównanie, **limit np. 3 analiz dokumentów AI**.
  - Premium **jednorazowo za wesele** (do testu: 99 / 149 / 199 / 299 zł), z wyższym limitem analiz, eksportami i harmonogramem płatności z przypomnieniami SMS w przyszłości.
  - B2B (v2): firmy wystawiają ofertę w **ustrukturyzowanym formacie porównywalnym**. Para dostaje ją bez OCR, a firma pojawia się w porównaniu. To naturalny, legalny sposób budowy katalogu.

### Decyzje projektowe

- D1.1: MVP = oferty i umowy + porównanie + płatności + budżet + goście/RSVP + zadania.
- D1.2: Katalog publiczny poza MVP. Zamiast niego model `Vendor` należący do wesela (prywatny).
- D1.3: Model danych od początku przewiduje `VendorProfile` (publiczny, od firmy), ale bez API publicznego w MVP.

### Odrzucone pomysły

- Własny komunikator z firmami (lider go ma, kosztowny, niewielka przewaga).
- Strona ślubna z szablonami (to GUI; poza zakresem). Zostaje **link RSVP per gospodarstwo**.
- Automatyczne „wyszukiwanie usługodawców w internecie przez agenta”: ryzyko regulaminów i jakości. Poza MVP.
- Rejestr prezentów (model amerykański, w Polsce dominuje koperta [H]).

### Wpływ

- Architektura: dochodzi moduł `documents` i `offers` jako centralne, a `catalog` się kurczy.
- Koszty: mniej pracy przy katalogu, więcej przy ekstrakcji dokumentów (OCR + LLM).
- Narzędzia: potrzebne biblioteki PDF/DOCX/OCR i abstrakcja LLM. Silnik wyszukiwania niepotrzebny.

---

## Iteracja 2: architektura i koszty

### Zidentyfikowane problemy

1. **Licencje „copyleft” w popularnych narzędziach do dokumentów:**
   - **PyMuPDF to AGPL-3.0** (albo licencja komercyjna płatna). W usłudze SaaS AGPL wymusza udostępnienie kodu → **odrzucone**.
   - **OCRmyPDF** jest na MPL-2.0, ale wymaga **Ghostscript (AGPL)** → **odrzucone na MVP**.
   - **MinIO** (popularny S3 lokalnie) jest na AGPL, a edycja community jest ograniczana → **odrzucone**.
2. Redis, broker kolejek i Meilisearch zwiększają koszt utrzymania przy znikomej korzyści na starcie.
3. Koszt LLM rośnie liniowo z liczbą dokumentów, a ten sam dokument bywa analizowany wielokrotnie.
4. Dane gości i umowy nie mogą trafiać do zewnętrznego LLM bez podstawy prawnej i umowy powierzenia.

### Proponowane poprawki

| Obszar | Decyzja | Licencja | Uzasadnienie |
|---|---|---|---|
| Ekstrakcja PDF | **pypdf** (tekst) + **pypdfium2** (render stron do OCR) | BSD-3 / Apache-2.0 i BSD-3 | bez AGPL |
| DOCX | **python-docx** | MIT | standard |
| OCR | **Tesseract** (binarka w kontenerze workera) przez `pytesseract` | Apache-2.0 | lokalnie, bez wysyłki danych; język `pol` |
| Kolejka zadań | **tabela `jobs` w PostgreSQL** + `SELECT … FOR UPDATE SKIP LOCKED`, osobny proces `worker` z tego samego kodu | — | zero nowych usług; wystarczy do tysięcy zadań dziennie |
| Wyszukiwanie | **PostgreSQL FTS + pg_trgm** (duplikaty, wyszukiwanie po nazwie) | PostgreSQL | bez osobnego silnika |
| Wektory | **odłożone** (pgvector dopiero, gdy pojawi się realna potrzeba semantyczna) | — | brak przypadku użycia w MVP |
| Pliki | interfejs `Storage`: **lokalny dysk** (dev), **S3-compatible u dostawcy chmury** (prod) | — | bez MinIO |
| Cache / rate limit | **w procesie** (1 instancja); Redis dopiero przy skalowaniu poziomym | — | prostota |
| LLM | interfejs `LLMProvider` z implementacjami: `FakeProvider` (testy), `OllamaProvider` (lokalny), `ExternalProvider` (np. Claude API, **tylko po zgodzie i z DPA**) | — | brak vendor lock-in |
| Reużycie analiz | cache wyników po `(sha256 pliku, wersja promptu, model)` | — | ten sam plik nie jest analizowany dwa razy |
| E-mail dev | **Mailpit** w Docker Compose | MIT | podgląd maili bez wysyłki |
| Solver stołów (v1.1) | **OR-Tools CP-SAT** | Apache-2.0 | deterministyczny, sprawdzony |

### Koszty (szacunek rzędu wielkości; ceny do sprawdzenia w aktualnych cennikach)

| Pozycja | Dev (laptop) | Staging (Synology DS225+) | Produkcja start |
|---|---|---|---|
| Serwer/API/DB | 0 zł | 0 zł (prąd) | 1 VPS w UE + backup: **rząd kilkudziesięciu–200 zł/mies.** [H] |
| Storage plików | 0 zł | 0 zł | S3-compatible w UE: grosze/GB [H] |
| LLM | 0 zł (Fake/Ollama) | 0 zł (Ollama, jeśli sprzęt wystarczy) | zależnie od dostawcy; szacunek tokenów: oferta 3–5 stron ≈ 3–6 tys. tokenów wejścia + ~1 tys. wyjścia na analizę; przy limicie Free = 3 analizy koszt per para jest mały, ale **musi być mierzony** (tabela `ai_runs` z liczbą tokenów i kosztem) |
| E-mail transakcyjny | 0 zł (Mailpit) | 0 zł | darmowe limity dostawców [H] |
| Narzędzia deweloperskie | 0 zł (wszystkie OSS) | — | — |

Uwaga do DS225+: lokalny LLM (Ollama) wymaga dużo RAM i najlepiej GPU. **Na DS225+ nie planuję uruchamiać LLM.** Ollama może działać na laptopie, jeśli sprzęt pozwoli (do sprawdzenia: RAM/GPU laptopa).

### Decyzje projektowe

- D2.1: Modularny monolit, jedno repo, dwa procesy z jednego obrazu: `api` i `worker` (ADR-0001, ADR-0003).
- D2.2: PostgreSQL jako jedyny stan (dane, kolejka, FTS, audyt) (ADR-0002).
- D2.3: Zakaz zależności AGPL/SSPL w kodzie produkcyjnym (ADR-0006).
- D2.4: LLM za interfejsem. Domyślnie brak wysyłki na zewnątrz (ADR-0005).

### Odrzucone

Mikroserwisy, Kubernetes, Celery+Redis/RabbitMQ, Meilisearch/Typesense, pgvector w MVP, PyMuPDF, OCRmyPDF, MinIO, LangChain (ciężki, szybko zmienne API; prosta własna warstwa wystarcza).

---

## Iteracja 3: doświadczenie użytkownika (przepływy, bez GUI)

### Zidentyfikowane problemy i poprawki

| Proces | Problem | Poprawka |
|---|---|---|
| Rejestracja | długi formularz zniechęca | e-mail + hasło + zgoda na regulamin. Weryfikacja e-mail wymagana dopiero do zaproszenia partnera i wysyłki RSVP |
| Tworzenie wesela | para często **nie zna jeszcze daty** | `wedding_date` opcjonalna; „planowany miesiąc/rok” jako alternatywa; zadania z terminami względnymi aktywują się po ustaleniu daty |
| Budżet | para nie wie, ile to kosztuje | opcjonalny wstępny podział budżetu według wag kategorii (deterministycznie, bez AI); wszystko edytowalne |
| Liczba gości | koszt zależy od RSVP, a RSVP zmienia się do końca | trzy liczby: `planned`, `invited`, `confirmed`. Koszty „za osobę” liczone dla wybranej z nich |
| Dodawanie oferty | OCR/AI może się mylić | wynik ekstrakcji to **szkic** z polami „niepewne” i cytatami; para zatwierdza każde pole; dopiero zatwierdzona oferta trafia do porównania |
| Porównanie ofert | różne struktury cen | normalizacja do wspólnego modelu `PricingComponent` (za osobę / ryczałt / za godzinę / za dziecko / opcjonalne) i wyliczenie przy tej samej liczbie gości; brakujące elementy oznaczone jako „nieznane”, a nie 0 zł |
| Wybór oferty | wybór powinien zasilić budżet | „wybierz ofertę” → tworzy pozycję budżetu i harmonogram płatności z terminami z oferty/umowy (do potwierdzenia) |
| Zmiana daty ślubu | bezrefleksyjne przesunięcie wszystkich terminów | przeliczane tylko zadania **niezakończone, z terminem względnym i nieedytowanym ręcznie**; API zwraca **podgląd zmian** (`dry_run`) przed zatwierdzeniem; terminy płatności z umów **nigdy** nie są przesuwane automatycznie |
| Współpraca we dwoje | równoczesna edycja nadpisuje zmiany | optymistyczne blokowanie (`version`, odpowiedź `409 Conflict`) |
| Goście | rodzina odpowiada zbiorczo | zaproszenie i RSVP **per gospodarstwo** (`Household`), link z tokenem, **bez konta gościa** |
| Przypomnienia | spam | dzienne podsumowanie e-mail zamiast pojedynczych maili; konfigurowalne |
| Mobile | słaby zasięg na sali | API idempotentne (`Idempotency-Key`), małe odpowiedzi, paginacja kursorowa, pole `updated_at` do synchronizacji przyrostowej |

### Sytuacje błędne do obsłużenia

- Ślub w przeszłości lub data poprawin przed ślubem (walidacja).
- Gość w dwóch gospodarstwach (zabronione ograniczeniem).
- Oferta w walucie innej niż PLN (MVP: odrzucamy z komunikatem; model gotowy na waluty).
- Plik nieczytelny lub zaszyfrowany PDF (status `failed` z powodem; możliwość ręcznego wpisania).
- Partner usuwa konto: wesele zostaje u drugiej osoby; jeśli był jedynym właścicielem → wymagane przekazanie lub usunięcie.

### Wpływ

API dostaje `dry_run`, `Idempotency-Key`, `If-Match`/`version`. Model dostaje `Household`, trzy liczniki gości, `PricingComponent`, `PaymentSchedule`.

---

## Iteracja 4: bezpieczeństwo, RODO i gotowość komercyjna

### Zidentyfikowane problemy

1. **Role RODO są nieoczywiste.** Dla danych konta jesteśmy administratorem. Dla danych gości wprowadzanych przez parę najpewniej **podmiotem przetwarzającym** (para przetwarza je w celach osobistych, ale platforma działa komercyjnie) [H]. **Wymaga opinii prawnika.** Od tego zależą regulamin, polityka prywatności i umowa powierzenia.
2. **Alergie to dane o zdrowiu** (art. 9 RODO).
3. **Umowy i oferty** zawierają dane osobowe (PESEL, adresy, numery kont) i treści chronione prawem autorskim (oferty firm).
4. **AI**: halucynacje (zła kwota zadatku = realna szkoda finansowa), prompt injection z treści dokumentu, wyciek danych do dostawcy LLM.
5. **Porada prawna**: „analiza umowy” może być uznana za poradę prawną.
6. **Wykorzystanie ofert innych par** (np. średnie ceny sal) to ryzyko prawne (tajemnica przedsiębiorstwa firmy, prawa autorskie, cel przetwarzania).

### Proponowane poprawki

| Ryzyko | Środek |
|---|---|
| Alergie | brak osobnego pola „alergie” w MVP. Pole `dietary_preference` (enum: standard, wegetariańska, wegańska, bezglutenowa, inna) + opcjonalna krótka `dietary_note` **szyfrowana na poziomie kolumny**, z informacją dla pary o charakterze danych; automatyczne usunięcie po weselu (retencja) |
| Retencja | dane gości: anonimizacja **90 dni po dacie ostatniego wydarzenia** (konfigurowalne); całe wesele: powiadomienie i usunięcie po **24 mies.** od daty; kopie zapasowe rotowane w ≤ 35 dni (usunięte dane znikają z backupów w skończonym czasie) |
| Dokumenty | prywatny storage, brak publicznych URL-i, pobieranie przez API z autoryzacją; limit rozmiaru i typów (PDF, DOCX, JPG, PNG, HEIC), weryfikacja sygnatury pliku (nie rozszerzenia), nazwy plików generowane po stronie serwera; skanowanie antywirusowe (ClamAV jako osobny kontener, GPL-2.0 uruchamiany jako osobna usługa) w v1.1 |
| Halucynacje AI | wyjście LLM walidowane schematem Pydantic; **każde pole z cytatem** (strona + fragment); pola bez cytatu oznaczone `unverified`; **żadna wartość AI nie trafia do budżetu bez zatwierdzenia człowieka**; testy regresji na zestawie syntetycznych ofert |
| Prompt injection | treść dokumentu przekazywana jako dane (wyraźnie oddzielona), model nie ma narzędzi ani dostępu do bazy; wynik to tylko JSON wg schematu; instrukcje w dokumencie ignorowane |
| Wyciek do LLM | domyślnie `OllamaProvider` / `FakeProvider`; zewnętrzny dostawca tylko po: zgodzie użytkownika (per dokument lub per konto), umowie DPA, regionie UE i braku trenowania na danych; **redakcja PESEL/IBAN/telefonów przed wysyłką** (regex + walidacja sum kontrolnych) |
| Porada prawna | brak oceny „czy umowa jest dobra”. Tylko **ekstrakcja faktów** („zadatek: 3000 zł, str. 2”) i **neutralne flagi informacyjne** („w umowie nie znaleziono zapisu o odwołaniu imprezy”) + stały disclaimer; analiza ryzyk w v2 po konsultacji z prawnikiem |
| Dane cudzych ofert | oferty są **prywatne dla wesela**; zakaz agregacji między weselami bez osobnej analizy prawnej |
| Katalog (v2) | tylko dane od firm (self-service) lub z licencją; pola źródła, podstawy prawnej, daty weryfikacji; obsługa żądań usunięcia |
| Konta | Argon2id, limity prób logowania (per konto i per IP), krótkie access tokeny + **rotowane refresh tokeny** z wykrywaniem ponownego użycia, unieważnianie sesji, TOTP jako rozszerzenie |
| IDOR | każde zapytanie domenowe filtrowane przez `wedding_id` z członkostwa użytkownika (warstwa repozytorium), testy uprawnień dla każdego endpointu |
| Narzędzia | Gitleaks w pre-commit, `pip-audit` i Trivy w CI, przypięte wersje (`uv.lock`), lista licencji generowana automatycznie |

### Gotowość komercyjna: brakujące elementy (poza kodem)

Regulamin, polityka prywatności, umowa powierzenia (DPA) dla par, rejestr czynności przetwarzania, ocena skutków (DPIA, prawdopodobnie wymagana przez dane o zdrowiu i AI na dokumentach), opinia prawna dot. „porady prawnej”, forma działalności i fakturowanie, operator płatności (poza MVP).

### Wpływ

- Architektura: moduły `audit`, `privacy` (eksport, usunięcie, retencja), `ai` z rejestrem uruchomień.
- Koszty: konsultacja prawna jest **niezbędnym kosztem przed startem komercyjnym** (do budżetu właściciela).
- Narzędzia: Gitleaks (zainstalowany), pip-audit, Bandit, Trivy (Docker).

---

## Finalna koncepcja MVP

**Wedding Planner AI: asystent, który rozumie oferty i umowy weselne, liczy realny koszt wesela i pilnuje płatności oraz terminów.**

### Zakres MVP (backend + API, bez GUI)

| Moduł | Zakres |
|---|---|
| `identity` | rejestracja, logowanie, weryfikacja e-mail, reset hasła, sesje (refresh tokeny), zgody, usunięcie konta, eksport danych |
| `workspace` | wesele, wydarzenia (ślub, przyjęcie, poprawiny), członkowie (właściciel, współorganizator, współpracownik tylko do odczytu), zaproszenia |
| `planner` | zadania z szablonu (deterministycznie wg typu ceremonii i daty), terminy względne/bezwzględne, zależności, przeliczenie po zmianie daty z podglądem |
| `budget` | kategorie, pozycje (planowane/potwierdzone/rzeczywiste), **płatności z typem (zadatek/zaliczka/dopłata/inna)**, harmonogram, koszt na osobę, rezerwa, historia zmian |
| `vendors` | „moi usługodawcy” (prywatni dla wesela), status (rozważany, zapytany, zarezerwowany, odrzucony) |
| `offers` | oferta z komponentami cenowymi, **porównanie kosztu całkowitego** przy zadanej liczbie gości, wybór oferty → budżet + płatności |
| `documents` | upload, wersje, ekstrakcja tekstu (pypdf/python-docx/Tesseract), powiązanie z ofertą/umową/usługodawcą |
| `ai` | **jeden** proces LLM: ekstrakcja oferty/umowy do schematu z cytatami; rejestr uruchomień, wersje promptów, cache, limity, zatwierdzenie przez człowieka |
| `guests` | gospodarstwa, goście, osoby towarzyszące, dzieci, dieta, nocleg, transport, **RSVP przez link z tokenem** |
| `notifications` | przypomnienia o zadaniach i płatnościach (e-mail, dzienne podsumowanie) |
| `audit` / `privacy` | dziennik zmian, retencja, anonimizacja |

### Poza MVP (kolejność)

1. v1.1: plan stołów (OR-Tools), harmonogram dnia z konfliktami, ClamAV, MFA.
2. v1.2: oferty ustrukturyzowane od firm (B2B) i profil firmy.
3. v2: publiczny katalog z danych od firm, analiza ryzyk umów (po opinii prawnej), płatności Premium.

### Agenci AI: z 13 do 1 + deterministyka

| Proponowany agent | Decyzja w MVP |
|---|---|
| 1. Analiza potrzeb pary | **formularz + reguły** (onboarding) |
| 2. Generowanie planu | **szablon deterministyczny** (wersjonowany) |
| 3. Analiza ofert | **LLM: `OfferExtractor`** (jedyny agent LLM w MVP) |
| 4. Analiza dokumentów | **LLM: ten sam `OfferExtractor`** (umowa = oferta + warunki) |
| 5. Wyszukiwanie usługodawców | poza MVP |
| 6. Normalizacja katalogu | **kod** (normalizacja NIP, telefonu, adresu, URL) |
| 7. Wykrywanie duplikatów | **pg_trgm + reguły** |
| 8. Dopasowanie usługodawców | poza MVP |
| 9. Analiza budżetu | **kod** (przekroczenia, brak rezerwy, płatności po terminie) |
| 10. Ryzyka i konflikty | **kod** (konflikty terminów); ryzyka umów v2 |
| 11. Wsparcie komunikacyjne | v1.1: LLM do szkicu wiadomości (bez wysyłki automatycznej) |
| 12. Koordynator | **kolejka zadań `jobs`** (bez autonomii) |
| 13. Kontrola jakości danych | **walidatory + raport** |
