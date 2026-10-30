# QUALITY REPORT — OPERACJA STÓŁ 7 V2 (29.10.2026)

Status: **wersja do oceny właściciela, nie „finalna zatwierdzona”.** Dźwięku nie odsłuchałem (nie mam takiej możliwości), więc dubbing, muzyka, miks i synchronizacja ust są niezweryfikowane słuchowo.

## Pomiary techniczne (ffprobe / ffmpeg)
- 1080×1920, 24 fps, **480 klatek = 20,000 s**, H.264 yuv420p, BT.709, AAC 48 kHz stereo.
- Głośność całkowita ok. **−15,2 LUFS**, szczyt próbki −1,7 dBFS (cel: ok. −16 LUFS, ≤ −1 dBTP; true-peak nie mierzony osobno).
- Czarne klatki (blackdetect): 0. Głośność po ostatnim eksporcie −15,2 LUFS.

## Oś czasu (klatki)
01 hak 0–29 · 02 M1 29–101 · 03 problem (ekran) 101–125 · 04 K1 125–179 · 05 aplikacja 179–259 · 06 reakcja M 259–279 · 07 reakcja K 279–299 · 08 M2 299–376 · 09 brew+telefon 376–407 · 10 ekran Stół 8 407–419 · 11 logo 419–480.

## Tożsamość postaci (ocena wzrokowa — Claude, nie biometryczna)
- MASTER V8.5 (SHA-256 `de22112e…f7331`) i arkusze tożsamości zgodne ze sobą. Sprawdzone plansze: `QC/keyframes_sheet.png`, `QC/contact_v2.png` (3 klatki z każdego klipu).
- **Problem znaleziony i naprawiony w trakcie pracy:** pierwsze klatki kobiety (v04_a–d, v08_a–d, dwuujęciowe v06) miały inną twarz niż wzorzec (wąska, „męska” twarz) — odrzucone. Poprawka: wycinek twarzy z arkusza jako **pierwszy** obraz referencyjny + master drugi + krótki prompt. Zatwierdzone: v04_g, v08_g, v06_i (kobieta), v02_a, v06m_e, v07_c (mężczyzna).
- Ujęcie dwuosobowe z jej twarzą w średnim planie zrezygnowano (twarz niewiarygodna) — scena 6 to shot/reverse shot w zbliżeniach.
- Ryzyka: w v04 przy mówieniu głowa mocno się pochyla, oczy kobiety wyglądają na większe niż na masterze w niektórych klatkach (v04 klatka 2); mężczyzna w v07 zmienia kąt i wielkość twarzy w trakcie klipu. Wymaga Twojej oceny.

## Synchronizacja ust (IA2V, dźwięk wcześniej)
Heurystyka ruchu ust vs obwiednia audio (ROI dobrane ręcznie do kadru — wynik orientacyjny): v02 korelacja 0,66, v04 0,83, v07 0,80; usta uspokajają się po kwestii. Klatki twarzy `QC/mouths.png`: usta otwierają się w trakcie mowy i zamykają w ciszy. To **nie** dowód zgodności fonemów.

## Dubbing
Supertonic 3 (lokalny, CPU), głosy M5 i F5, po 3–4 warianty każdej kwestii (`POLISH_VOICES/takes`). Wybór: M1_C, K1_C, M2_B — wg rozpoznawania mowy (ASR) i długości; **nie odsłuchane**. ASR: „Stół siódmy. Mamy problem.” poprawnie; „Spokojnie, mam plan.” poprawnie; „A stół ósmy?” ASR czyta „A sto osme” (w każdym wariancie) — możliwy błąd wymowy „stół/ósmy” lub tylko ASR. Emocje sterowane wyłącznie tempem/pauzą (brak sterowania emocją w tym silniku). Nie użyto klonowania ani Pipera.

## Aplikacja (prawdziwe nagranie)
Prawdziwy planer stołów na koncie demo w środowisku E2E (dane fikcyjne): ekran „Plan stołów” (Posadzeni: 3 · bez miejsca: 4), wybór gościa, lista stołów, przypisanie do Stołu 7 (komunikat „Halina Lewandowska → Stół 7”, karta „2 z 10”), na końcu Stół 8 z gościem. Dane demo przywrócone po nagraniu (Posadzeni: 3). **Rewizja 2 (po uwagach):** nagranie powtórzone w 780×1388 (zrzuty ekranu przy DSF 2, ok. 13 kl./s, skalowane do 1080×1920) — tekst wyraźnie ostrzejszy niż wcześniej; dodano J-cut dźwięku napięcia (wchodzi 0,25 s przed cięciem do ekranu aplikacji). J/L-cut dialogów NIE zastosowano (dźwięk jest związany z ruchem ust w klipach). Głosy, klipy AI i muzyka bez zmian. **Pozostałe wady:** ekran „problem” to nagłówek planu z podpisem dodanym w montażu („Czworo gości bez miejsca przy stole” — zgodne ze stanem aplikacji); wizualizacja „konfliktu dwóch gości” nie istnieje w produkcie, więc jej nie wymyślałem. W scenie 8 telefon w AI-klatce ma ekran odwrócony od kamery, a prawdziwy ekran pokazuje wstawka 0,5 s.

## Punktacja (moja, ostrożna; wynik zależy od oceny dźwięku, którego nie słyszałem)
| Kryterium | Max | Moja ocena |
|---|---:|---:|
| Hook | 10 | 7 |
| Humor i czytelność historii | 15 | 10 |
| Spójność postaci i stylu | 20 | 14 |
| Naturalność dubbingu | 10 | 4 (niesprawdzone) |
| Synchronizacja ust | 10 | 6 |
| Animacja i aktorstwo | 10 | 6 |
| Kamera i montaż | 10 | 7 |
| Prawdziwy pokaz aplikacji | 10 | 7 |
| Dźwięk i napisy | 5 | 3 |
| **Razem** | 100 | **ok. 64** — poniżej celu 90 |

## Czego brakuje do 90+
Odsłuch i ewentualna zmiana głosów/wymowy „stół”; wyższej rozdzielczości nagranie aplikacji (np. skala 2× w przeglądarce); numer „7” na winietce w hooku (obecna winietka jest pusta, napis tytułowy w montażu); J-cut/L-cut (nie zrobione); osobne ujęcie przebitki „problemu” w animacji nie powstało; muzyka niesłuchana; piątka z poprzedniej wersji usunięta (zastąpiona spojrzeniem).
