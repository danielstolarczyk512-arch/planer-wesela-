"""Szablon zadań przygotowań do polskiego wesela (wersjonowany razem z kodem).

Terminy to liczba dni względem daty ślubu (ujemne = przed). Wartości są orientacyjne:
formalności (USC, parafia) para musi potwierdzić u źródła, bo zasady i terminy ważności
dokumentów mogą się zmieniać. Wskazówki (`tip`) to nasze własne, krótkie podpowiedzi —
nie porada prawna.

Kodów istniejących zadań nie zmieniamy: po nich „uzupełnianie z szablonu” rozpoznaje,
czego weselu brakuje.
"""

from dataclasses import dataclass, field

TEMPLATE_VERSION = "2027.1"

RELIGIOUS = ("concordat", "religious_other")
WITH_WITNESSES = ("civil", "concordat", "religious_other")
ALL = ("civil", "concordat", "religious_other", "humanist", "undecided")


@dataclass(frozen=True)
class TaskTemplate:
    code: str
    title: str
    category: str
    offset_days: int
    priority: int = 2  # 1 = najważniejsze, 4 = opcjonalne
    ceremony_types: tuple[str, ...] = ALL
    depends_on: tuple[str, ...] = field(default=())
    tip: str | None = None
    vendor_category: str | None = None  # kategoria usługodawcy (skrót „Dodaj usługodawcę”)
    parent: str | None = None  # podzadanie (np. pozycja listy dokumentów)


def _docs(
    parent: str, offset: int, ceremony: tuple[str, ...], *items: tuple[str, str, str]
) -> tuple[TaskTemplate, ...]:
    """Pozycje listy dokumentów jako podzadania (kod, tytuł, wskazówka)."""
    return tuple(
        TaskTemplate(code, title, "formalnosci", offset, 1, ceremony, tip=tip, parent=parent)
        for code, title, tip in items
    )


TEMPLATES: tuple[TaskTemplate, ...] = (
    # --- początek: 18-12 miesięcy -------------------------------------------------------------
    TaskTemplate(
        "date_and_ceremony",
        "Wybierzcie datę i rodzaj ceremonii",
        "formalnosci",
        -560,
        1,
        tip="Najpierw sprawdźcie wolne terminy w 2-3 wymarzonych salach i w parafii lub USC — "
        "dopiero wtedy ustalajcie datę. Piątki i niedziele bywają tańsze niż soboty.",
    ),
    TaskTemplate(
        "budget_initial",
        "Ustalcie wstępny budżet wesela",
        "budzet",
        -540,
        1,
        tip="Zacznijcie od kwoty, którą możecie wydać bez zadłużania się, i od razu odłóżcie "
        "10-15% rezerwy na niespodziewane koszty. Zwykle największą pozycją jest sala z menu.",
    ),
    TaskTemplate(
        "guest_list_draft",
        "Spiszcie wstępną listę gości",
        "goscie",
        -510,
        1,
        tip="Spiszcie wszystkich, a potem podzielcie listę na „muszą być” i „chcielibyśmy”. "
        "Liczba gości decyduje o wielkości sali i większości kosztów. Liczcie też dzieci.",
    ),
    TaskTemplate(
        "wedding_style",
        "Ustalcie charakter przyjęcia (całonocne, kameralne, poprawiny?)",
        "inne",
        -500,
        2,
        depends_on=("guest_list_draft",),
        tip="Od tej decyzji zależy wybór sali, menu i muzyki. Poprawiny to zwykle osobna cena "
        "za osobę i inna liczba gości — zapiszcie je jako osobne wydarzenie.",
    ),
    TaskTemplate(
        "venue_book",
        "Zarezerwujcie salę weselną (umowa i zadatek)",
        "miejsce",
        -480,
        1,
        depends_on=("budget_initial", "guest_list_draft"),
        tip="Przed podpisaniem sprawdźcie w umowie: cenę za osobę i co obejmuje, minimalną liczbę "
        "gości, ceny dla dzieci, napoje i korkowe, godziny i nadgodziny, poprawiny, posiłki dla "
        "obsługi, zasady rezygnacji oraz czy wpłata to zadatek, czy zaliczka.",
        vendor_category="venue",
    ),
    TaskTemplate(
        "church_book",
        "Ustalcie termin ślubu w parafii",
        "formalnosci",
        -480,
        1,
        RELIGIOUS,
        tip="Termin rezerwujecie zwykle w parafii jednego z narzeczonych. Ślub w innym kościele "
        "wymaga zgody (licencji) z waszej parafii — zapytajcie o to od razu.",
    ),
    TaskTemplate(
        "music_book",
        "Zarezerwujcie zespół lub DJ-a",
        "uslugodawcy",
        -420,
        1,
        depends_on=("venue_book",),
        tip="Zapytajcie o liczbę godzin grania, przerwy, posiłek dla muzyków, cenę nadgodziny, "
        "sprzęt i oświetlenie oraz o zastępstwo, gdy ktoś zachoruje.",
        vendor_category="dj",
    ),
    TaskTemplate(
        "photo_book",
        "Zarezerwujcie fotografa",
        "uslugodawcy",
        -420,
        1,
        depends_on=("venue_book",),
        tip="Obejrzyjcie całe reportaże, nie tylko najlepsze kadry. Ustalcie godziny pracy, "
        "plener, termin oddania zdjęć, ich liczbę i formę (galeria, pendrive, album).",
        vendor_category="photographer",
    ),
    TaskTemplate(
        "color_theme",
        "Ustalcie kolorystykę i styl dekoracji",
        "uslugodawcy",
        -400,
        3,
        tip="Wybierzcie 2-3 kolory i jeden styl. Ułatwi to rozmowy z florystą, wybór zaproszeń "
        "i dodatków — i chroni przed zakupami „bo ładne”.",
    ),
    TaskTemplate(
        "video_book",
        "Zarezerwujcie kamerzystę",
        "uslugodawcy",
        -390,
        3,
        depends_on=("venue_book",),
        tip="Zapytajcie, czy w cenie jest teledysk, pełny film, nagranie z drona i jak długo "
        "czeka się na montaż.",
        vendor_category="videographer",
    ),
    TaskTemplate(
        "usc_book",
        "Zarezerwujcie termin w urzędzie stanu cywilnego",
        "formalnosci",
        -365,
        1,
        ("civil",),
        tip="Zapytajcie w USC o wolne terminy i o ślub poza urzędem (dodatkowa opłata). "
        "Datę potwierdza się po złożeniu zapewnienia o braku przeszkód.",
    ),
    TaskTemplate(
        "celebrant_book",
        "Wybierzcie celebranta ślubu humanistycznego",
        "formalnosci",
        -365,
        1,
        ("humanist",),
        tip="Ślub humanistyczny nie ma skutków prawnych — jeśli chcecie być małżeństwem także "
        "w świetle prawa, zaplanujcie dodatkowo krótki ślub cywilny.",
    ),
    TaskTemplate(
        "witnesses",
        "Poproście świadków",
        "formalnosci",
        -330,
        2,
        WITH_WITNESSES,
        tip="Świadkowie muszą być pełnoletni i mieć przy sobie dowód osobisty w dniu ślubu. "
        "Dobrze, gdy jedno z nich zgodzi się pomóc w koordynacji dnia.",
    ),
    # --- 12-6 miesięcy ----------------------------------------------------------------------
    TaskTemplate(
        "accommodation",
        "Zarezerwujcie noclegi dla gości",
        "miejsce",
        -300,
        2,
        depends_on=("guest_list_draft",),
        tip="Zarezerwujcie pulę pokoi z możliwością bezpłatnej rezygnacji do określonej daty. "
        "W aplikacji zaznaczcie przy gościach, kto potrzebuje noclegu.",
        vendor_category="accommodation",
    ),
    TaskTemplate(
        "engagement_session",
        "Sesja narzeczeńska (opcjonalnie)",
        "uslugodawcy",
        -300,
        4,
        depends_on=("photo_book",),
        tip="Dobra okazja, żeby oswoić się z fotografem przed ślubem. Zdjęcia przydadzą się "
        "na zaproszenia lub informację dla gości.",
        vendor_category="photographer",
    ),
    TaskTemplate(
        "dress",
        "Wybierzcie suknię ślubną",
        "stroj",
        -270,
        2,
        tip="Szycie lub sprowadzenie sukni trwa często kilka miesięcy. Zapytajcie o liczbę "
        "przymiarek w cenie i o koszt poprawek.",
        vendor_category="dress",
    ),
    TaskTemplate(
        "decor",
        "Wybierzcie florystę i dekoracje",
        "uslugodawcy",
        -240,
        2,
        depends_on=("venue_book",),
        tip="Ustalcie, co dekorator robi w kościele/USC, a co na sali, kto montuje i demontuje "
        "dekoracje i co zostaje po weselu.",
        vendor_category="florist",
    ),
    TaskTemplate(
        "makeup_book",
        "Zarezerwujcie makijaż i fryzurę na dzień ślubu",
        "stroj",
        -240,
        2,
        tip="Zapytajcie o dojazd, godzinę rozpoczęcia, cenę dla mamy lub świadkowej i termin "
        "próby.",
        vendor_category="makeup",
    ),
    TaskTemplate(
        "attractions",
        "Zaplanujcie atrakcje (fotobudka, słodki stół, barman)",
        "uslugodawcy",
        -210,
        3,
        tip="Mniej znaczy więcej: 1-2 przemyślane atrakcje cieszą bardziej niż pięć naraz. "
        "Sprawdźcie, czy sala ma na nie miejsce i prąd.",
        vendor_category="attractions",
    ),
    TaskTemplate(
        "ceremony_music",
        "Wybierzcie oprawę muzyczną ceremonii",
        "uslugodawcy",
        -200,
        3,
        tip="W kościele repertuar warto uzgodnić z organistą lub parafią. W USC zapytajcie, czy "
        "można przynieść własną muzykę.",
        vendor_category="musician",
    ),
    TaskTemplate(
        "guest_info",
        "Przygotujcie informacje dla gości (dojazd, nocleg, plan dnia)",
        "goscie",
        -200,
        2,
        tip="Uzupełnijcie stronę dla gości w ustawieniach wesela — goście zobaczą ją razem "
        "z formularzem potwierdzenia obecności.",
    ),
    TaskTemplate(
        "transport",
        "Zarezerwujcie transport (auto do ślubu, bus dla gości)",
        "uslugodawcy",
        -180,
        2,
        tip="Policzcie gości bez samochodu i tych, którzy wracają w nocy. Ustalcie godziny "
        "kursów busa i miejsce odbioru.",
        vendor_category="transport",
    ),
    TaskTemplate(
        "premarital_course",
        "Ukończcie nauki przedmałżeńskie",
        "formalnosci",
        -180,
        1,
        RELIGIOUS,
        tip="Obejmują zwykle kurs i spotkania w poradni rodzinnej. Zapiszcie się wcześnie — "
        "terminy kursów bywają ograniczone.",
    ),
    TaskTemplate(
        "invitations_list",
        "Ustalcie ostateczną listę zaproszonych",
        "goscie",
        -160,
        1,
        depends_on=("guest_list_draft",),
        tip="Jedno zaproszenie to jedna rodzina lub para. Zdecydujcie, kto przychodzi "
        "z osobą towarzyszącą i czy zapraszacie dzieci.",
    ),
    TaskTemplate(
        "invitations_order",
        "Zamówcie zaproszenia",
        "goscie",
        -150,
        2,
        depends_on=("invitations_list",),
        tip="Zamówcie kilka sztuk więcej. Na zaproszeniu podajcie termin odpowiedzi i link lub "
        "kod QR do potwierdzenia obecności.",
        vendor_category="invitations",
    ),
    TaskTemplate(
        "suit",
        "Wybierzcie garnitur",
        "stroj",
        -150,
        2,
        tip="Szycie na miarę trwa zwykle kilka tygodni. Zostawcie czas na poprawki.",
        vendor_category="suit",
    ),
    TaskTemplate(
        "dance_course",
        "Kurs tańca lub przygotowanie pierwszego tańca (opcjonalnie)",
        "inne",
        -150,
        4,
        tip="Kilka lekcji wystarczy, by poczuć się pewnie. Zacznijcie, gdy znacie już piosenkę.",
    ),
    # --- 6-3 miesiące -----------------------------------------------------------------------
    TaskTemplate(
        "rings",
        "Kupcie obrączki",
        "stroj",
        -120,
        1,
        tip="Grawer i dopasowanie rozmiaru trwają. Przymierzajcie obrączki po południu — "
        "palce bywają wtedy nieco grubsze.",
        vendor_category="jeweler",
    ),
    TaskTemplate(
        "shoes_accessories",
        "Kupcie buty, bieliznę i dodatki do stroju",
        "stroj",
        -120,
        3,
        depends_on=("dress",),
        tip="Rozchodźcie buty w domu przed ślubem i przygotujcie drugą, wygodną parę na wesele.",
    ),
    TaskTemplate(
        "children_care",
        "Zaplanujcie atrakcje lub opiekę dla dzieci",
        "uslugodawcy",
        -120,
        3,
        tip="Animator lub osobny kącik z zabawami pozwala rodzicom bawić się spokojnie. "
        "Policzcie dzieci w liście gości.",
        vendor_category="attractions",
    ),
    TaskTemplate(
        "honeymoon",
        "Zaplanujcie podróż poślubną (opcjonalnie)",
        "inne",
        -120,
        4,
        tip="Sprawdźcie ważność paszportów. Bilety kupione z wyprzedzeniem są zwykle tańsze.",
    ),
    TaskTemplate(
        "docs_concordat",
        "Skompletujcie dokumenty do ślubu konkordatowego",
        "formalnosci",
        -120,
        1,
        ("concordat",),
        tip="Wymagania różnią się między parafiami — listę potwierdźcie w swojej kancelarii "
        "parafialnej. Część dokumentów ma ograniczony termin ważności.",
    ),
    *_docs(
        "docs_concordat",
        -120,
        ("concordat",),
        (
            "docs_concordat_baptism",
            "Świadectwa chrztu",
            "Parafie zwykle wymagają świadectw wydanych w ostatnich miesiącach — zapytajcie "
            "o termin ważności.",
        ),
        (
            "docs_concordat_confirmation",
            "Zaświadczenia o bierzmowaniu",
            "Często jest adnotacja na świadectwie chrztu — sprawdźcie, czy wystarczy.",
        ),
        (
            "docs_concordat_catechesis",
            "Świadectwo ukończenia katechezy (jeśli parafia wymaga)",
            "Wystarcza zwykle świadectwo szkolne z oceną z religii.",
        ),
        (
            "docs_concordat_course",
            "Zaświadczenia z nauk przedmałżeńskich i poradni rodzinnej",
            "Wydaje je prowadzący kurs i poradnia.",
        ),
        (
            "docs_concordat_usc",
            "Zaświadczenie z USC o braku przeszkód",
            "Jest ważne przez ograniczony czas (obecnie 6 miesięcy) — nie składajcie wniosku "
            "za wcześnie.",
        ),
        (
            "docs_concordat_banns",
            "Zapowiedzi (i zaświadczenie z innej parafii, jeśli dotyczy)",
            "Zapowiedzi głosi się w parafiach zamieszkania narzeczonych.",
        ),
        (
            "docs_concordat_licence",
            "Licencja na ślub w innej parafii (jeśli dotyczy)",
            "Wydaje ją wasza parafia, gdy ślub odbędzie się w innym kościele.",
        ),
        (
            "docs_concordat_ids",
            "Dowody osobiste narzeczonych i świadków",
            "Świadkowie muszą mieć dowody przy sobie w dniu ślubu.",
        ),
    ),
    TaskTemplate(
        "docs_civil",
        "Skompletujcie dokumenty do ślubu cywilnego",
        "formalnosci",
        -100,
        1,
        ("civil",),
        tip="Polskie akty stanu cywilnego USC sprawdza w rejestrze. Dokumenty z zagranicy "
        "wymagają zwykle tłumaczenia — zapytajcie w USC o aktualną listę.",
    ),
    *_docs(
        "docs_civil",
        -100,
        ("civil",),
        (
            "docs_civil_ids",
            "Dowody osobiste narzeczonych",
            "Potrzebne przy składaniu zapewnienia i w dniu ślubu.",
        ),
        (
            "docs_civil_witnesses",
            "Dane i dowody osobiste świadków",
            "Świadkowie okazują dowody w dniu ślubu.",
        ),
        (
            "docs_civil_foreign",
            "Dokumenty z zagranicy z tłumaczeniem (jeśli dotyczy)",
            "Dotyczy np. aktu urodzenia sporządzonego za granicą lub cudzoziemca "
            "(zaświadczenie o zdolności prawnej).",
        ),
        (
            "docs_civil_fee",
            "Opłata skarbowa za akt małżeństwa",
            "Kwotę i numer konta podaje USC; ślub poza urzędem ma dodatkową opłatę.",
        ),
    ),
    TaskTemplate(
        "invitations_send",
        "Wręczcie lub wyślijcie zaproszenia",
        "goscie",
        -100,
        1,
        depends_on=("invitations_order",),
        tip="Rodzinie zaproszenia wręcza się zwykle osobiście. Przy każdym zaproszeniu w "
        "aplikacji zaznaczcie „wręczone” — zobaczycie, kogo jeszcze brakuje.",
    ),
    TaskTemplate(
        "menu_tasting",
        "Degustacja i wybór menu",
        "miejsce",
        -90,
        2,
        depends_on=("venue_book",),
        tip="Zapytajcie o dania wegetariańskie, bezglutenowe i dla dzieci oraz o menu dla "
        "obsługi (muzycy, fotograf).",
        vendor_category="venue",
    ),
    TaskTemplate(
        "cake",
        "Zamówcie tort",
        "uslugodawcy",
        -90,
        3,
        tip="Sprawdźcie, czy tort lub słodki stół nie jest już w pakiecie sali i czy sala "
        "pozwala na wypieki z zewnątrz.",
        vendor_category="cake",
    ),
    TaskTemplate(
        "groom_accessories",
        "Dodatki pana młodego (koszula, buty, spinki)",
        "stroj",
        -90,
        3,
        depends_on=("suit",),
    ),
    TaskTemplate(
        "first_dance_song",
        "Wybierzcie piosenkę na pierwszy taniec",
        "inne",
        -90,
        3,
        tip="Przekażcie wybraną wersję utworu muzykom — wersje studyjna i koncertowa różnią się "
        "długością i tempem.",
    ),
    TaskTemplate(
        "parish_protocol",
        "Spiszcie protokół przedmałżeński w parafii",
        "formalnosci",
        -90,
        1,
        RELIGIOUS,
        tip="Na spotkanie zabierzcie dokumenty z listy dokumentów. Termin ustalcie w kancelarii.",
    ),
    TaskTemplate(
        "usc_documents",
        "Złóżcie w USC dokumenty (zapewnienie o braku przeszkód)",
        "formalnosci",
        -75,
        1,
        ("civil", "concordat"),
        tip="Zapewnienie składacie osobiście, oboje. Zaświadczenie do ślubu konkordatowego ma "
        "ograniczoną ważność — sprawdźcie, by obejmowało datę ślubu.",
    ),
    # --- 3-1 miesiąc ------------------------------------------------------------------------
    TaskTemplate(
        "after_party",
        "Ustalcie szczegóły poprawin",
        "miejsce",
        -60,
        3,
        tip="Zapiszcie poprawiny jako osobne wydarzenie: inna liczba gości, inne menu i cena.",
    ),
    TaskTemplate(
        "alcohol",
        "Zaplanujcie alkohol i napoje (jeśli nie ma ich w pakiecie)",
        "miejsce",
        -60,
        2,
        depends_on=("venue_book",),
        tip="Sprawdźcie w umowie korkowe i zasady zwrotu nieotwartych butelek. Pamiętajcie "
        "o napojach dla kierowców i niepijących.",
    ),
    TaskTemplate(
        "dress_fittings",
        "Przymiarki i odbiór sukni",
        "stroj",
        -60,
        2,
        depends_on=("dress",),
        tip="Na ostatnią przymiarkę zabierzcie buty i bieliznę ze ślubu.",
    ),
    TaskTemplate(
        "coordinator_pick",
        "Wybierzcie osobę koordynującą dzień ślubu",
        "dzien_slubu",
        -60,
        2,
        tip="To ktoś, kto w dniu ślubu odbiera telefony od usługodawców i pilnuje godzin, "
        "żebyście nie musieli. Dodajcie tę osobę do wesela z rolą „koordynator dnia”.",
    ),
    TaskTemplate(
        "guest_gifts",
        "Podziękowania dla gości (opcjonalnie)",
        "inne",
        -60,
        4,
    ),
    TaskTemplate(
        "rsvp_collect",
        "Zbierzcie potwierdzenia obecności",
        "goscie",
        -45,
        1,
        depends_on=("invitations_send",),
        tip="Wyślijcie gościom link do potwierdzenia. Do osób bez odpowiedzi zadzwońcie "
        "tydzień przed terminem podanym w zaproszeniu.",
    ),
    TaskTemplate(
        "hair_makeup_trial",
        "Próbna fryzura i makijaż",
        "stroj",
        -45,
        3,
        depends_on=("makeup_book",),
        tip="Zróbcie zdjęcia w świetle dziennym i z lampą błyskową.",
    ),
    TaskTemplate(
        "music_list",
        "Ustalcie z muzykami listę utworów (i czego nie grać)",
        "dzien_slubu",
        -45,
        2,
        depends_on=("music_book",),
    ),
    TaskTemplate(
        "games",
        "Ustalcie zabawy i oczepiny",
        "dzien_slubu",
        -45,
        3,
        depends_on=("music_book",),
        tip="Powiedzcie prowadzącemu, czego nie chcecie (np. zabaw angażujących konkretne osoby).",
    ),
    TaskTemplate(
        "parents_thanks",
        "Przygotujcie podziękowania dla rodziców",
        "inne",
        -45,
        3,
    ),
    TaskTemplate(
        "usc_certificate_to_parish",
        "Dostarczcie zaświadczenie z USC do parafii",
        "formalnosci",
        -30,
        1,
        ("concordat",),
        depends_on=("usc_documents",),
    ),
    TaskTemplate(
        "accommodation_list",
        "Przekażcie miejscu noclegu listę gości",
        "miejsce",
        -30,
        2,
        depends_on=("accommodation", "rsvp_collect"),
    ),
    TaskTemplate(
        "plan_b",
        "Przygotujcie plan B (pogoda, opóźnienia)",
        "dzien_slubu",
        -30,
        2,
        tip="Przy punktach harmonogramu zapiszcie wariant awaryjny: miejsce na zdjęcia przy "
        "deszczu, parasole, kogo powiadomić przy opóźnieniu.",
    ),
    TaskTemplate(
        "vows",
        "Przygotujcie teksty na ceremonię (przysięga, przemowy)",
        "dzien_slubu",
        -30,
        3,
        ("humanist", "undecided"),
    ),
    TaskTemplate(
        "leave_work",
        "Zgłoście urlop w pracy",
        "inne",
        -30,
        3,
        tip="Pracownikowi na umowie o pracę przysługują dwa dni wolne z okazji własnego ślubu "
        "— zgłoście to pracodawcy z wyprzedzeniem.",
    ),
    TaskTemplate(
        "final_guest_count",
        "Przekażcie sali ostateczną liczbę gości",
        "miejsce",
        -21,
        1,
        depends_on=("rsvp_collect",),
        tip="Podajcie osobno dorosłych, dzieci według progów cenowych sali, diety i posiłki "
        "dla obsługi.",
    ),
    TaskTemplate(
        "seating_plan",
        "Przygotujcie plan stołów",
        "goscie",
        -14,
        2,
        depends_on=("final_guest_count",),
    ),
    TaskTemplate(
        "day_schedule",
        "Ustalcie harmonogram dnia z usługodawcami",
        "dzien_slubu",
        -14,
        1,
        tip="Zacznijcie od stałych godzin (ceremonia, obiad), a resztę ułóżcie wokół nich "
        "z zapasem 15-30 minut na przejazdy i zdjęcia.",
    ),
    TaskTemplate(
        "confirm_vendors",
        "Potwierdźcie godziny i adresy ze wszystkimi usługodawcami",
        "dzien_slubu",
        -14,
        1,
        depends_on=("day_schedule",),
    ),
    TaskTemplate(
        "blessing",
        "Ustalcie przebieg błogosławieństwa i wyjścia z domu",
        "dzien_slubu",
        -14,
        3,
    ),
    TaskTemplate(
        "gifts_person",
        "Wybierzcie osobę, która zajmie się prezentami i kopertami",
        "dzien_slubu",
        -14,
        3,
        tip="Przyda się zamykane pudełko na koperty i ktoś, kto zapisze, od kogo jest prezent "
        "— ułatwi to podziękowania.",
    ),
    TaskTemplate(
        "final_payments",
        "Przygotujcie dopłaty dla usługodawców",
        "budzet",
        -7,
        1,
        tip="Przygotujcie podpisane koperty z kwotami do wręczenia po weselu albo zaplanujcie "
        "przelewy. Sprawdźcie płatności w zakładce budżetu.",
    ),
    TaskTemplate(
        "seating_to_venue",
        "Przekażcie sali plan stołów i listę diet",
        "dzien_slubu",
        -7,
        1,
        depends_on=("seating_plan",),
        tip="Wydrukujcie plan stołów dla sali z planu stołów (z dietami i dziećmi przy stołach).",
    ),
    TaskTemplate(
        "schedule_to_vendors",
        "Wyślijcie harmonogram dnia usługodawcom",
        "dzien_slubu",
        -7,
        1,
        depends_on=("day_schedule",),
    ),
    TaskTemplate(
        "emergency_kit",
        "Spakujcie koszyk ratunkowy",
        "dzien_slubu",
        -7,
        3,
        tip="Igła z nitką, agrafki, plastry, tabletki przeciwbólowe, chusteczki, ładowarka, "
        "zapasowe rajstopy, dezodorant, przekąska i woda.",
    ),
    TaskTemplate(
        "day_essentials",
        "Przygotujcie obrączki, dokumenty i koperty na dzień ślubu",
        "dzien_slubu",
        -1,
        1,
    ),
    # --- po ślubie ----------------------------------------------------------------------------
    TaskTemplate(
        "returns",
        "Zwróćcie wypożyczone rzeczy",
        "po_slubie",
        7,
        3,
    ),
    TaskTemplate(
        "settle_vendors",
        "Rozliczcie ostatnie płatności z usługodawcami",
        "budzet",
        7,
        1,
    ),
    TaskTemplate(
        "thanks",
        "Podziękujcie gościom i usługodawcom",
        "po_slubie",
        14,
        4,
    ),
    TaskTemplate(
        "marriage_certificate",
        "Odbierzcie odpis aktu małżeństwa",
        "po_slubie",
        14,
        2,
        ("civil", "concordat"),
        tip="Po ślubie konkordatowym parafia przekazuje dokumenty do USC, który sporządza akt "
        "— zapytajcie w USC, kiedy odpis będzie gotowy.",
    ),
    TaskTemplate(
        "documents_after",
        "Zaktualizujcie dokumenty po ślubie (zmiana nazwiska)",
        "po_slubie",
        30,
        3,
        tip="Dowód osobisty, prawo jazdy, paszport, bank, pracodawca, ubezpieczenia, lekarz.",
    ),
    TaskTemplate(
        "reviews",
        "Oceńcie usługodawców (opcjonalnie)",
        "po_slubie",
        30,
        4,
    ),
    TaskTemplate(
        "photos_backup",
        "Odbierzcie zdjęcia i film, zróbcie kopię zapasową",
        "po_slubie",
        60,
        3,
    ),
)

BY_CODE: dict[str, TaskTemplate] = {t.code: t for t in TEMPLATES}
ORDER: dict[str, int] = {t.code: i for i, t in enumerate(TEMPLATES)}


def templates_for(ceremony_type: str) -> list[TaskTemplate]:
    return [t for t in TEMPLATES if ceremony_type in t.ceremony_types]


def tip_for(code: str | None) -> str | None:
    template = BY_CODE.get(code) if code else None
    return template.tip if template else None


def vendor_category_for(code: str | None) -> str | None:
    template = BY_CODE.get(code) if code else None
    return template.vendor_category if template else None
