# Nasz dzień — specyfikacja GUI premium

Wersja 1.0 · 19 października 2026 · rynek: Polska · nazwa robocza.

## 1. Decyzja projektowa

Jedna aplikacja, dwa pełne motywy: **Jasna elegancja** oraz **Wieczorowy luksus**. Oba korzystają z tych samych komponentów, danych, kolejności informacji i ścieżek. Motyw zmienia materiały, kolory, typografię nagłówków i delikatnie kształt powierzchni. Nie zmienia funkcji ani położenia nawigacji.

Referencjami są dwa wybrane przez użytkownika obrazy w katalogu `referencje/`. Ciemny ekran referencyjny ma bardziej plakatową kompozycję. W zestawie `wizualizacje/` ujednolicono hierarchię ekranów, aby przełączanie motywu nie wymagało ponownego uczenia się aplikacji. Jest to propozycja projektowa do akceptacji, nie decyzja o zmianie zakresu produktu.

Luksus ma wynikać z rytmu, dobrych proporcji, czytelnej typografii, spokojnych reakcji i przewidywalności. Wykluczamy migające złoto, dźwięki przy każdym kliknięciu, konfetti przy zwykłym zadaniu, ciężki paralaks, obracane karty, przewijanie sterowane animacją i sztuczne opóźnianie odpowiedzi.

Makiety są statycznymi wizualizacjami. Nie demonstrują działających animacji, backendu ani zgodności z dostępnością. Pokazana ramka telefonu i podpisy poza telefonem nie należą do GUI. Dane są fikcyjne.

## 2. Hierarchia dokumentów i zawartość

Przy wdrażaniu obowiązuje kolejność: reguły funkcjonalne i dostępność z tej specyfikacji → semantyczne tokeny → referencje stylistyczne → przykładowa kompozycja PNG. Nie kopiuj z PNG zbyt drobnych napisów lub sztywnej wysokości całego ekranu. Produkcja ma przewijać treść i obsługiwać duże fonty, zamiast pomniejszać tekst, aby wszystko zmieściło się naraz.

Paczka zawiera 20 ekranów (10 jasnych i 10 ciemnych), 2 oryginalne referencje, instrukcję, tokeny, listę testów oraz prompt wdrożeniowy. Nie jest gotową aplikacją. Fonty, biblioteki animacji i kod produkcyjny nie są dołączone.

## 3. System wizualny

### Kolory semantyczne

| Rola | Jasna elegancja | Wieczorowy luksus |
|---|---|---|
| Tło aplikacji | `#FAF7F2` | `#19191C` |
| Powierzchnia karty | `#FFFFFF` | `#242428` |
| Podwyższona powierzchnia / panel | `#FFFFFF` | `#2E2B30` |
| Tekst główny | `#242124` | `#F4EFE7` |
| Tekst pomocniczy | `#6F656B` | `#B7AEA5` |
| Akcja główna | `#63364A` | `#D5BA8D` |
| Tekst na akcji głównej | `#FFFFFF` | `#241E18` |
| Delikatna powierzchnia akcentowa | `#F1E8EB` | `#302B2F` |
| Separator dekoracyjny | `#E6DED5` | `#464047` |
| Obrys interaktywnego pola | `#8B7B83` | `#A28D73` |
| Złoto dekoracyjne | `#A88754` | `#D5BA8D` |
| Sukces: tekst / tło | `#315944` / `#EAF2EB` | `#C0DBC8` / `#2B3B32` |
| Ostrzeżenie: tekst / tło | `#78551E` / `#FAF0DA` | `#F1D6A6` / `#403523` |
| Błąd: tekst / tło | `#9B2638` / `#FCECEF` | `#FFC3CA` / `#482A32` |

Złoto jasnego motywu służy głównie dekoracji. Etykiety i linki mają używać koloru akcji lub tekstu, a nie jasnego złota. Obrys karty może być subtelny; obrys pola formularza, checkboxa i zaznaczenie fokusu muszą być widoczne. Status zawsze ma nazwę i ewentualnie ikonę, nigdy sam kolor.

### Typografia

- Jasny: Lora dla nagłówków, DM Sans dla interfejsu.
- Ciemny: Bodoni Moda dla krótkich nagłówków i dużego odliczania; Inter dla interfejsu. Bodoni nie stosować w tabelach, formularzach, etykietach ani małych komunikatach.
- H1: 30/38 px; H2: 22/30 px; tekst i pola: 16/24 px; pomocniczy tekst: 14/20 px; etykiety nawigacji: 12/16 px. Kwoty główne: 32–40 px. Odliczanie: 56–80 px, zależnie od przestrzeni.
- Liczby w zestawieniach mają tablicową szerokość. `86 400 zł`, `1 lipca 2028`, `20 czerwca`, poprawne polskie znaki. Kwota z walutą nie może łamać się przypadkowo.
- Nie używać kapitalików do długich zdań. Długie nazwiska mogą zajmować dwie linie. Pełną nazwę zawsze da się odczytać.
- Font zastępczy ma zbliżone metryki; wczytanie fontu nie może przestawiać kontrolek pod palcem.

### Przestrzeń, powierzchnie i ikony

Skala odstępów: 4, 8, 12, 16, 24, 32, 48 px. Margines telefonu: 20 px; przy szerokości 320 px można zejść do 16 px. Grupy oddzielać 24 px. Karty: jasny promień 16 px, ciemny 12 px. Przyciski: 12/10 px. Dolny panel: górne rogi 24 px w obu motywach. Pojedyncze kontrolki mają co najmniej 48 × 48 px obszaru dotykowego, nawet jeśli sama ikona jest mniejsza.

Ikony liniowe 20–24 px, jedna rodzina ikon, stała grubość około 1,75 px. Aktywna zakładka ma kolor, zaznaczenie i etykietę. Jasny motyw może używać bardzo lekkiego cienia; ciemny rozdziela warstwy kolorem i obrysem. Efekt szkła tylko w małym obszarze nagłówka, opcjonalnie i z pełnym nieprzezroczystym wariantem zastępczym. Nie nakładać rozmycia na całe przewijane listy.

## 4. Nawigacja i responsywność

Na telefonie pięć zakładek: **Dziś / Plan / Budżet / Goście / Więcej**. Dziś pokazuje najbliższe działania, najbliższą płatność i podsumowanie. Plan zawiera zadania. Budżet prowadzi do ofert, wydatków i umów. Goście prowadzą do RSVP, stołów, noclegów i transportu. Więcej zawiera harmonogram dnia, pakiety dla usługodawców oraz ustawienia.

Każda zakładka zachowuje własne przewinięcie i filtry. Ponowne naciśnięcie aktywnej zakładki może przewinąć ją na górę po drugim dotknięciu, ale nie usuwa formularza. Wstecz wraca do rzeczywistego poprzedniego widoku z zachowaną listą. Odnośnik do konkretnego wydatku lub gościa musi działać także po bezpośrednim otwarciu.

Telefon 320–767 px: jedna kolumna; dolna nawigacja uwzględnia bezpieczny obszar systemowy. Klawiatura nie zakrywa aktywnego pola ani przycisku zapisu. W formularzu dolna nawigacja może się schować, ale zamknięcie klawiatury ją przywraca bez skoku treści.

Tablet 768–1023 px: wąska nawigacja boczna i ewentualnie dwie kolumny kart. Od 1024 px: boczna nawigacja i układ lista–szczegóły; treść maksymalnie około 1200 px. To decyzje projektowe do sprawdzenia na treści, nie wymóg wykrywania modelu urządzenia. Zmiana szerokości nie tworzy drugiego formularza i nie kasuje wprowadzonych danych.

## 5. Zachowanie poszczególnych ekranów

| Ekran | Najważniejsze działanie i reguły |
|---|---|
| 01 Dziś | Maksymalnie trzy najbliższe zadania. Dotknięcie płatności otwiera szczegóły, nie wykonuje przelewu. Odliczanie przeliczać według daty wydarzenia w strefie Europe/Warsaw, nie jako przypadkowe 24-godzinne okresy. |
| 02 Budżet | Osobno prognoza, limit, umowy, wpłaty i pozostała należność. Po edycji od razu pokaż poprawną kwotę; żadnego wolnego przewijania cyfr. Brak wyceny to „Brak wyceny”, nie zero. |
| 03 Porównanie ofert | Wspólne założenia, np. 100 osób. Na małym telefonie podsumowanie dwóch ofert, a szczegółowe parametry w rozwijanych sekcjach lub przewijanej tabeli z czytelnymi nagłówkami. Wybór oferty jest szkicem do zatwierdzenia; samo zaznaczenie nie rezerwuje sali. |
| 04 Sprawdzenie umowy | Fragment źródła, pola do korekty, oznaczone braki. Przed zatwierdzeniem wymaganych danych wskazać nieuzupełnione pole. Odczyt AI nie zmienia samodzielnie zobowiązań. Dokument i dane można sprawdzić bez rozmowy z chatbotem. |
| 05 Plan | Checkbox reaguje natychmiast, ale stan zapisu jest jawny. Ukończone zadanie nie znika spod palca: oznaczenie, krótka przerwa, możliwość cofnięcia. Zadania mają właściciela, datę i ewentualne pochodzenie terminu. |
| 06 Goście | Szukanie po każdej osobie, grupowanie zaproszeń, osobny udział w weselu i poprawinach. Brak odpowiedzi nie oznacza odmowy. Ręczna odpowiedź dostępna dla pary. Usunięcie z listy wymaga potwierdzenia zakresu. |
| 07 Stoły | Lista wygodna bez przeciągania; dostępna akcja „Przenieś do stołu”. Kontrola liczby miejsc i podwójnego przypisania. Mapa sali może być drugim widokiem, nie jedyną metodą obsługi. Prywatne reguły rozsadzania nie trafiają do eksportów. |
| 08 Noclegi i transport | Potrzeba, rezerwacja oraz opłacenie to odrębne stany. Osobna noc, pokój, płatnik i kurs. Godzina 01:30 po weselu 1 lipca ma datę 2 lipca. |
| 09 Dzień wesela | Harmonogram i pakiet dla sali z wersją oraz datą. Po zmianie danych stary eksport ma status „Nieaktualny”. „Podgląd PDF” nie wysyła niczego automatycznie. |
| 10 RSVP | Osobny widok gościa bez pięciu zakładek pary. Dostęp przez prywatny link, bez obowiązkowej instalacji. Gość widzi swoje zaproszenie, nie listę wszystkich gości. Po zapisie pokazujemy podsumowanie i możliwość zmiany odpowiedzi. |

Testy poprawności obowiązkowe: umowa 5000 zł i wpłata 1500 zł oznaczają 3500 zł do zapłaty; 100→90 gości przy minimum 100 nie obniża automatycznie zobowiązania; odmowa po zamknięciu zamówienia nie zmienia go samodzielnie. Efekt wizualny nigdy nie zastępuje poprawnej logiki.

## 6. System ruchu — najważniejszy element odczucia premium

Poniższe czasy i krzywe są **naszymi parametrami projektowymi**, nie wymaganiami standardu. Animacja ma tłumaczyć zmianę, zachowywać ciągłość i być przerywalna. Reakcja kontrolki rozpoczyna się od razu; nie czekamy na zakończenie efektu, aby przyjąć kolejne działanie.

| Interakcja | Zachowanie | Czas docelowy |
|---|---|---|
| Naciśnięcie przycisku | Przyciemnienie / zmiana tła i skala 1→0,985. Bez przesunięcia sąsiadów. Powrót po puszczeniu. | 80 ms nacisk, 140 ms powrót |
| Zmiana głównej zakładki | Krótkie przenikanie treści. Pasek nawigacji pozostaje nieruchomy. Brak slajdu sugerującego nadrzędność zakładek. | 160–180 ms |
| Lista → szczegóły | Treść wchodzi z przesunięciem 16–24 px i opacity 0→1. Wstecz w przeciwną stronę. | 240 ms wejście, 200 ms powrót |
| Rozwinięcie karty | Płynne odsłonięcie dodatkowej treści; zachować pozycję nagłówka. Wysokość animować tylko małego bloku, nie całej długiej listy. | 200–220 ms |
| Dolny panel formularza | Panel wysuwa się od dołu, tło przyciemnia się równolegle. Bez sprężystego odbicia. | 280–320 ms otwarcie, 220 ms zamknięcie |
| Dialog potwierdzenia | Przenikanie i delikatna skala 0,98→1. Jednoznaczne przyciski. | 180 ms |
| Zaznaczenie zadania | Zmiana checkboxa i koloru tekstu; oznaczenie gotowości. Nie uruchamiać animacji całej listy. | 140–180 ms |
| Filtrowanie / szukanie | Dane zmieniają się bez przemieszczania aktywnego pola. Krótkie przenikanie wyników tylko gdy pomaga. | 100–140 ms |
| Zmiana kwoty / statusu | Aktualna wartość pojawia się od razu; opcjonalne krótkie podświetlenie lub przenikanie. Bez odometru. | 120 ms |
| Zmiana motywu | Przenikanie dwóch warstw lub natychmiastowa podmiana. Bez fal po całym ekranie i bez przeliczania układu podczas animacji. | 180–220 ms |
| Komunikat sukcesu | Mały komunikat nad nawigacją, bez zasłaniania głównego działania. | 180 ms wejście, 140 ms wyjście |

Krzywe: `standard: cubic-bezier(0.2, 0, 0, 1)`, `enter: cubic-bezier(0.16, 1, 0.3, 1)`, `exit: cubic-bezier(0.4, 0, 1, 1)`. Animować przede wszystkim transformację i opacity. Nie stosować `transition: all`. Wzajemne przenikanie należy kontrolować tak, aby przez cały czas końcowe kontrolki miały poprawny kontrast.

Shared element można dodać tylko dla przejścia konkretna karta→jej szczegóły: ten sam tytuł i obrys, około 260 ms. Funkcja opcjonalna; musi mieć prosty wariant przenikania. Nie animować współdzielonego elementu, jeśli w międzyczasie zmieniły się dane, nieznana jest pozycja celu lub lista jest wirtualizowana bez stabilnej kotwicy.

Nie łączyć wielu pokazowych efektów: jedno przejście nadrzędne oraz lokalna reakcja kontrolki wystarczą. Maksymalnie trzy elementy mogą wejść kaskadowo z odstępem 30 ms przy pierwszym otwarciu pustego, lekkiego widoku; długie listy nie animują każdego wiersza. Brak animacji odliczania co sekundę. Haptics: pojedynczy delikatny impuls przy skutecznym potwierdzeniu, wyłącznie gdy platforma go obsługuje i użytkownik go nie wyłączył. Funkcje muszą działać bez haptics.

### Przerywanie i gesty

Szybkie dotknięcie kolejnej zakładki kieruje do ostatniego wybranego celu, bez kolejki starych przejść. Opóźniona odpowiedź sieciowa z poprzedniego widoku nie może nadpisać aktualnego. Przycisk zapisu blokuje tylko ponowne wysłanie tego samego żądania, nie całe GUI.

Dolny panel ma uchwyt, przycisk zamknięcia i obsługę wstecz/Escape. Przeciągnięcie jest dodatkiem. Po próbie zamknięcia zmienionego formularza: „Zapisać szkic czy odrzucić zmiany?”. Gest nie może przypadkowo kasować danych. Przewijanie zawartości panelu i gest zamykania nie walczą ze sobą: zamykanie gestem zaczyna się z uchwytu, a nie z dowolnego pola. W tle blokujemy przewijanie, po zamknięciu przywracamy pozycję i fokus.

### Ograniczenie ruchu

Respektować preferencję systemową oraz ustawienie aplikacji „Ogranicz animacje”. Gdy którakolwiek wskazuje ograniczenie: brak przesunięć, skalowania, shared elements i kaskad. Pozostają natychmiastowe zmiany albo przenikanie 80–100 ms. Informacja o sukcesie, błędzie lub wyborze jest identyczna w obu trybach. To dodatkowy cel dostępności projektu; nie należy na tej podstawie deklarować zgodności całego produktu z poziomem AAA.

## 7. Stany, formularze i zaufanie

Każdy moduł projektować dla: pierwszego użycia, danych gotowych, ładowania, zapisywania, sukcesu, błędu, braku sieci, braku uprawnień i konfliktu zmiany. Stan pusty ma jedno wyjaśnienie i konkretne działanie, np. „Dodaj pierwszą ofertę”. Nie wyświetlać fikcyjnych kwot jako stanu początkowego.

Szybkie operacje nie potrzebują sztucznego loadera. Szkielet pokazujemy po około 150 ms, jeśli dane nadal nie są dostępne, z wymiarami stabilnymi względem treści. Bez bezustannego błyszczenia. Po dłuższym oczekiwaniu podać prawdziwy etap; jeśli etap jest nieznany, napisać „Wczytywanie”, zamiast wymyślać procenty. Operacja zachowuje możliwość anulowania, jeżeli rzeczywiście można ją anulować.

Optymistyczna zmiana dopuszczalna dla zadania lub lokalnego szkicu, z obsługą błędu i cofnięcia. Nie oznaczamy płatności jako wykonanej, rezerwacji jako potwierdzonej ani wiadomości jako wysłanej bez potwierdzenia odpowiedniego procesu. Po błędzie sieci zachować formularz i jasno pokazać „Nie zapisano — spróbuj ponownie”. Offline nie znaczy pełnej synchronizacji; pokazywać ostatnią aktualizację i rzeczywisty zakres działania.

Walidacja po opuszczeniu pola i przy zapisie. Błąd ma tekst przy polu; sam czerwony obrys nie wystarcza. Po nieudanym zapisie fokus trafia do pierwszego błędu. Przy kwotach klawiatura numeryczna, akceptacja przecinka dziesiętnego i formatowanie po zakończeniu edycji. Szkic można automatycznie zapisywać, ale stan „Szkic zapisany” jest oddzielny od zatwierdzonej umowy.

Komunikat „Cofnij” dostępny co najmniej 6 sekund z możliwością zatrzymania na fokusie oraz przez historię lub ponowną edycję. Błędy nie znikają automatycznie. Współpraca: pokazać „Michał zmienił termin”, a przy sprzecznych edycjach wybór wersji zamiast milczącego nadpisania.

## 8. Dostępność i wydajność jako część luksusu

Cel: WCAG 2.2 AA dla właściwych kryteriów, do potwierdzenia testami. Zwykły tekst co najmniej 4,5:1; duży tekst co najmniej 3:1. Interaktywne granice i fokus sprawdzać niezależnie od dekoracyjnych separatorów. Body 16 px; skalowanie tekstu do 200% bez utraty operacji. Testować klawiaturę, widoczny fokus, VoiceOver/TalkBack, kolejność odczytu i zrozumiałe etykiety ikon.

Preferencje motywu: Jasny / Ciemny / Systemowy. Pierwszy wybór systemowy; zapamiętanie jawnego wyboru. Przy zmianie podczas edycji zachować fokus, zaznaczenie, wpisane wartości i scroll. Dla strony gościa para może wybrać motyw zaproszenia, ale ustawienia ograniczenia ruchu odbiorcy zawsze obowiązują.

Cel płynności: 60 klatek/s na reprezentatywnym telefonie, do zmierzenia. Budżet około 16,7 ms na klatkę jest celem diagnostycznym, nie obietnicą działania każdego urządzenia. Testować średniej klasy Android i iPhone, nie tylko desktop. Jeśli rozmycie, cień albo złożona animacja powodują zacięcia, upraszczać efekt. Nie animować długich list i ciężkich wykresów jednocześnie.

Nie dodawać ciężkiej biblioteki wyłącznie do prostego fade. Dobór technologii zależy od istniejącego stosu: natywne mechanizmy platformy albo lekkie animacje interfejsu webowego. Nawigacja, dane i dostępność nie mogą zależeć od obsługi opcjonalnego efektu wizualnego.

## 9. Kolejność wdrażania

1. Tokeny, typografia, dwa motywy, przyciski, formularze i stany fokusu.
2. Nawigacja oraz cztery bazowe widoki: Dziś, Plan, Budżet, Goście. Najpierw użyteczne i poprawne bez animacji.
3. Szczegóły, dolne panele, walidacja, zapis szkiców i obsługa błędów.
4. Stały zestaw przejść oraz tryb ograniczonego ruchu. Dopiero potem opcjonalne shared elements.
5. Pozostałe moduły, strony gości i eksporty. Testy obu motywów na rzeczywistych urządzeniach.

Nie rozpoczynać od odtwarzania ekranów jako obrazków. Każdy element ma być rzeczywistą kontrolką, tekstem albo semantycznym komponentem.

## 10. Źródła wymagań dostępności

Sprawdzono 19.10.2026. Czasy animacji, kolory, rozmiary kontrolek i kompozycje powyżej są decyzjami projektowymi. Źródła dotyczą wymagań kontrastu i ograniczenia ruchu:

- W3C, Contrast (Minimum): https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- W3C, Animation from Interactions (kryterium AAA, tu przyjęte dodatkowo): https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html
- MDN, prefers-reduced-motion: https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion

Paczka nie potwierdza zgodności produkcyjnej. Oddzielne testy są wymagane po implementacji i integracji z prawdziwymi danymi.
