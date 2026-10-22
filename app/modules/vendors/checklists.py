"""Standardowe listy przy usługodawcy: pytania przed rezerwacją i lista kontrolna umowy.

Treści są nasze, krótkie i praktyczne. Lista umowy sprawdza tylko, czy dany zapis JEST
w umowie — nie ocenia go prawnie (to rola prawnika, zob. docs/znane-ograniczenia.md).
Kody są stałe: po nich dodawanie standardowej listy nie tworzy duplikatów.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ChecklistTemplate:
    code: str
    text: str


_MUSIC = (
    ChecklistTemplate("music_hours", "Ile godzin gracie i ile jest przerw?"),
    ChecklistTemplate("music_overtime", "Ile kosztuje każda dodatkowa godzina?"),
    ChecklistTemplate("music_host", "Czy prowadzicie zabawy i oczepiny? Czego nie robicie?"),
    ChecklistTemplate(
        "music_gear", "Jaki sprzęt i oświetlenie zapewniacie? Czy nagłośnicie ceremonię?"
    ),
    ChecklistTemplate("music_list", "Czy możemy ustalić listę utworów i czego nie grać?"),
    ChecklistTemplate("music_backup", "Co się dzieje, gdy ktoś z zespołu zachoruje?"),
    ChecklistTemplate("music_meals", "Ile osób potrzebuje posiłku i miejsca przy stole?"),
)
_PHOTO = (
    ChecklistTemplate("photo_hours", "Ile godzin pracy obejmuje pakiet i od której godziny?"),
    ChecklistTemplate("photo_session", "Czy w cenie jest plener lub sesja w innym dniu?"),
    ChecklistTemplate("photo_delivery", "Ile zdjęć oddajecie, w jakiej formie i w jakim terminie?"),
    ChecklistTemplate("photo_backup", "Czy macie zastępstwo w razie choroby?"),
    ChecklistTemplate("photo_meals", "Czy potrzebujecie posiłku i miejsca przy stole?"),
    ChecklistTemplate(
        "photo_publish", "Czy publikujecie nasze zdjęcia (portfolio, media społecznościowe)?"
    ),
)
_VIDEO = (
    ChecklistTemplate("video_hours", "Ile godzin nagrania obejmuje pakiet?"),
    ChecklistTemplate(
        "video_product", "Co dostaniemy: teledysk, pełny film, nagranie z drona? Jak długie?"
    ),
    ChecklistTemplate("video_delivery", "W jakim terminie oddajecie film i w jakiej formie?"),
    ChecklistTemplate("video_music", "Jakiej muzyki używacie w filmie?"),
    ChecklistTemplate("video_meals", "Czy potrzebujecie posiłku i miejsca przy stole?"),
)
_DECOR = (
    ChecklistTemplate(
        "decor_scope", "Co obejmuje oferta: kościół lub USC, sala, auto, bukiet, butonierki?"
    ),
    ChecklistTemplate("decor_setup", "Kto i kiedy montuje oraz demontuje dekoracje?"),
    ChecklistTemplate("decor_return", "Co zostaje po weselu, a co trzeba oddać?"),
    ChecklistTemplate("decor_travel", "Czy dojazd jest w cenie?"),
)
_BEAUTY = (
    ChecklistTemplate("beauty_travel", "Czy dojeżdżacie i od której godziny zaczynacie?"),
    ChecklistTemplate("beauty_trial", "Czy próba jest w cenie?"),
    ChecklistTemplate("beauty_people", "Ile osób zdążycie przygotować (mama, świadkowa)?"),
)

QUESTIONS: dict[str, tuple[ChecklistTemplate, ...]] = {
    "venue": (
        ChecklistTemplate("venue_date", "Czy termin jest wolny i jak długo możecie go trzymać?"),
        ChecklistTemplate(
            "venue_price", "Co obejmuje cena za osobę (menu, napoje, tort, obsługa, dekoracje)?"
        ),
        ChecklistTemplate(
            "venue_min_guests", "Jaka jest minimalna liczba gości i jak liczone są dzieci?"
        ),
        ChecklistTemplate("venue_hours", "Do której trwa przyjęcie i ile kosztuje nadgodzina?"),
        ChecklistTemplate("venue_drinks", "Czy możemy przywieźć własny alkohol? Ile korkowe?"),
        ChecklistTemplate(
            "venue_after", "Ile kosztują poprawiny i posiłki dla obsługi (muzycy, fotograf)?"
        ),
        ChecklistTemplate(
            "venue_extras", "Czy są noclegi, parking i dostęp bez schodów dla gości?"
        ),
        ChecklistTemplate("venue_final_count", "Do kiedy trzeba podać ostateczną liczbę gości?"),
        ChecklistTemplate("venue_cancel", "Jakie są zasady rezygnacji i zmiany terminu?"),
    ),
    "catering": (
        ChecklistTemplate("catering_menu", "Co obejmuje menu i ile jest ciepłych posiłków?"),
        ChecklistTemplate(
            "catering_diets", "Czy przygotujecie dania wegetariańskie, bezglutenowe, dla dzieci?"
        ),
        ChecklistTemplate("catering_service", "Czy obsługa kelnerska i naczynia są w cenie?"),
        ChecklistTemplate("catering_final_count", "Do kiedy podajemy ostateczną liczbę gości?"),
    ),
    "photographer": _PHOTO,
    "videographer": _VIDEO,
    "dj": _MUSIC,
    "band": _MUSIC,
    "musician": (
        ChecklistTemplate("musician_repertoire", "Jaki repertuar proponujecie na ceremonię?"),
        ChecklistTemplate("musician_rules", "Czy uzgadniacie utwory z parafią lub urzędem?"),
        ChecklistTemplate("musician_gear", "Czy potrzebujecie prądu lub nagłośnienia?"),
    ),
    "florist": _DECOR,
    "decorations": _DECOR,
    "makeup": _BEAUTY,
    "hairdresser": _BEAUTY,
    "transport": (
        ChecklistTemplate("transport_seats", "Ile miejsc i ile kursów obejmuje cena?"),
        ChecklistTemplate("transport_times", "Gdzie i o której odbieracie gości?"),
        ChecklistTemplate("transport_extra", "Ile kosztuje dodatkowy kurs lub godzina?"),
        ChecklistTemplate("transport_decor", "Czy dekoracja auta jest w cenie?"),
    ),
    "cake": (
        ChecklistTemplate("cake_portions", "Ile porcji, jakie smaki i jakie alergeny?"),
        ChecklistTemplate("cake_delivery", "Kto dowozi tort i jak ma być przechowywany?"),
        ChecklistTemplate("cake_venue", "Czy sala pozwala na tort z zewnątrz (opłata)?"),
    ),
    "sweet_table": (
        ChecklistTemplate("sweet_portions", "Na ile osób i co dokładnie jest w zestawie?"),
        ChecklistTemplate("sweet_setup", "Kto przygotowuje stół i sprząta po weselu?"),
    ),
    "attractions": (
        ChecklistTemplate("attr_space", "Ile miejsca i prądu potrzebujecie?"),
        ChecklistTemplate("attr_hours", "W jakich godzinach działa atrakcja?"),
        ChecklistTemplate("attr_included", "Co jest w cenie (wydruki, materiały, obsługa)?"),
    ),
    "photobooth": (
        ChecklistTemplate("booth_space", "Ile miejsca i prądu potrzebujecie?"),
        ChecklistTemplate("booth_prints", "Czy wydruki są bez limitu? Jak dostaniemy pliki?"),
    ),
    "bartender": (
        ChecklistTemplate("bar_included", "Czy alkohol i lód są w cenie, czy zapewniamy je sami?"),
        ChecklistTemplate("bar_hours", "W jakich godzinach działa bar?"),
    ),
    "accommodation": (
        ChecklistTemplate("acc_rooms", "Ile pokoi możecie zarezerwować i w jakiej cenie?"),
        ChecklistTemplate("acc_cancel", "Do kiedy można bezpłatnie zrezygnować z pokoi?"),
        ChecklistTemplate("acc_breakfast", "Czy śniadanie jest w cenie i o której?"),
    ),
    "dress": (
        ChecklistTemplate("dress_fittings", "Ile przymiarek jest w cenie?"),
        ChecklistTemplate("dress_pickup", "Kiedy odbiór i ile kosztują poprawki?"),
    ),
    "suit": (
        ChecklistTemplate("suit_time", "Ile trwa szycie i ile przymiarek jest w cenie?"),
        ChecklistTemplate("suit_alter", "Ile kosztują poprawki?"),
    ),
    "jeweler": (
        ChecklistTemplate("rings_time", "Ile trwa wykonanie i grawer?"),
        ChecklistTemplate("rings_size", "Czy zmiana rozmiaru po ślubie jest w cenie?"),
    ),
    "invitations": (
        ChecklistTemplate("inv_proof", "Czy przed drukiem dostaniemy projekt do korekty?"),
        ChecklistTemplate("inv_time", "Ile trwa druk i czy koperty są w cenie?"),
    ),
    "wedding_planner": (
        ChecklistTemplate("wp_scope", "Co obejmuje usługa i ile jest spotkań?"),
        ChecklistTemplate("wp_day", "Czy jesteście z nami w dniu ślubu i w jakich godzinach?"),
    ),
}

_CONTRACT_BASE = (
    ChecklistTemplate("c_date", "Data, godziny i miejsce usługi"),
    ChecklistTemplate("c_price", "Cena i dokładny zakres usługi"),
    ChecklistTemplate("c_deposit", "Wysokość wpłaty i czy to zadatek, czy zaliczka"),
    ChecklistTemplate("c_schedule", "Terminy i kwoty kolejnych płatności"),
    ChecklistTemplate("c_cancel", "Zasady rezygnacji i zmiany terminu (dla obu stron)"),
    ChecklistTemplate("c_backup", "Co, jeśli usługodawca nie może przyjechać (zastępstwo)"),
    ChecklistTemplate("c_party", "Dane firmy (nazwa, adres, NIP) i podpisy obu stron"),
)
_CONTRACT_EXTRA: dict[str, tuple[ChecklistTemplate, ...]] = {
    "venue": (
        ChecklistTemplate("c_min_guests", "Minimalna liczba gości i termin podania ostatecznej"),
        ChecklistTemplate(
            "c_venue_costs", "Ceny dla dzieci, napoje, korkowe, nadgodziny, poprawiny"
        ),
        ChecklistTemplate("c_crew_meals", "Cena posiłków dla obsługi (muzycy, fotograf)"),
    ),
    "photographer": (
        ChecklistTemplate("c_delivery", "Termin i forma oddania zdjęć"),
        ChecklistTemplate("c_image", "Zasady publikacji zdjęć z naszym wizerunkiem"),
    ),
    "videographer": (
        ChecklistTemplate("c_delivery", "Termin i forma oddania filmu"),
        ChecklistTemplate("c_image", "Zasady publikacji nagrań z naszym wizerunkiem"),
    ),
    "dj": (ChecklistTemplate("c_hours", "Liczba godzin grania i cena nadgodziny"),),
    "band": (ChecklistTemplate("c_hours", "Liczba godzin grania i cena nadgodziny"),),
}

GENERIC_QUESTIONS = (
    ChecklistTemplate("gen_scope", "Co dokładnie obejmuje cena?"),
    ChecklistTemplate("gen_extra", "Jakie mogą być dodatkowe koszty (dojazd, nadgodziny)?"),
    ChecklistTemplate("gen_payment", "Jaka wpłata na start i kiedy reszta?"),
)


def standard(kind: str, category: str) -> tuple[ChecklistTemplate, ...]:
    if kind == "contract":
        return _CONTRACT_BASE + _CONTRACT_EXTRA.get(category, ())
    return QUESTIONS.get(category, GENERIC_QUESTIONS)
