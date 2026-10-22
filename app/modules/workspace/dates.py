"""Pomocnik wyboru daty ślubu: porównanie kilku terminów bez zgadywania.

Liczymy wszystko lokalnie i deterministycznie, bez zewnętrznych usług:
- święta ustawowo wolne w Polsce (ustawa z 18 stycznia 1951 r. o dniach wolnych od pracy; od 2025 r.
  także Wigilia) — w tym ruchome, liczone od Wielkanocy (algorytm Meeusa/Jonesa/Butchera);
- okresy Adwentu i Wielkiego Postu (przy ślubie w kościele parafie zwykle odradzają huczne wesela —
  zasady ustala parafia, więc tylko podpowiadamy, żeby zapytać);
- godzinę zachodu słońca (algorytm NOAA, dokładność ok. 1-2 min) dla miasta wojewódzkiego —
  ważne przy zdjęciach w plenerze;
- sezon (od czerwca do września: najwięcej wesel, sale rezerwowane najwcześniej).
Wynik to uwagi do rozmowy, a nie „ocena” daty.
"""

import math
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Warsaw")
WEEKDAYS = ("poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela")
MONTHS_GEN = (
    "stycznia",
    "lutego",
    "marca",
    "kwietnia",
    "maja",
    "czerwca",
    "lipca",
    "sierpnia",
    "września",
    "października",
    "listopada",
    "grudnia",
)
# Miasta wojewódzkie (szer., dł. geograficzna); zachód słońca w Polsce różni się do ok. 40 min.
CITIES: dict[str, tuple[float, float]] = {
    "Białystok": (53.13, 23.16),
    "Bydgoszcz": (53.12, 18.01),
    "Gdańsk": (54.35, 18.65),
    "Gorzów Wielkopolski": (52.73, 15.24),
    "Katowice": (50.26, 19.02),
    "Kielce": (50.87, 20.63),
    "Kraków": (50.06, 19.94),
    "Lublin": (51.25, 22.57),
    "Łódź": (51.76, 19.46),
    "Olsztyn": (53.78, 20.49),
    "Opole": (50.67, 17.93),
    "Poznań": (52.41, 16.93),
    "Rzeszów": (50.04, 22.00),
    "Szczecin": (53.43, 14.55),
    "Warszawa": (52.23, 21.01),
    "Wrocław": (51.11, 17.04),
}
DEFAULT_CITY = "Łódź"  # środek Polski
CHURCH = ("concordat", "religious_other")
HIGH_SEASON = (6, 7, 8, 9)
MID_SEASON = (5, 10)
NEAR_DAYS = 3
# Kalendarz liczony dla sąsiednich lat: skrajne daty (rok 1, 9999) wychodzą poza zakres `date`.
MIN_YEAR, MAX_YEAR = 1900, 2200
BOOKING_MONTHS = 12  # popularne sale i usługodawców rezerwuje się zwykle 12-18 miesięcy wcześniej


def match_city(name: str | None) -> str:
    """Miasto wojewódzkie po nazwie (bez względu na wielkość liter); domyślnie środek Polski."""
    key = " ".join((name or "").split()).casefold()
    return next((c for c in CITIES if c.casefold() == key), DEFAULT_CITY)


def easter(year: int) -> date:
    """Niedziela Wielkanocna (kalendarz gregoriański)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month = (h + m - 7 * n + 114) // 31
    day = (h + m - 7 * n + 114) % 31 + 1
    return date(year, month, day)


def holidays(year: int) -> dict[date, str]:
    """Dni ustawowo wolne od pracy w Polsce."""
    e = easter(year)
    out = {
        date(year, 1, 1): "Nowy Rok",
        date(year, 1, 6): "Trzech Króli",
        e: "Wielkanoc",
        e + timedelta(days=1): "Poniedziałek Wielkanocny",
        date(year, 5, 1): "Święto Pracy",
        date(year, 5, 3): "Święto Konstytucji 3 Maja",
        e + timedelta(days=49): "Zielone Świątki",
        e + timedelta(days=60): "Boże Ciało",
        date(year, 8, 15): "Wniebowzięcie NMP",
        date(year, 11, 1): "Wszystkich Świętych",
        date(year, 11, 11): "Święto Niepodległości",
        date(year, 12, 25): "Boże Narodzenie",
        date(year, 12, 26): "Drugi dzień Bożego Narodzenia",
    }
    if year >= 2025:
        out[date(year, 12, 24)] = "Wigilia"
    return out


def church_season(d: date) -> str | None:
    """Adwent (od czwartej niedzieli przed Bożym Narodzeniem do Wigilii) albo Wielki Post."""
    e = easter(d.year)
    if e - timedelta(days=46) <= d < e:
        return "Wielki Post"
    christmas = date(d.year, 12, 25)
    # Czwarta niedziela przed 25 grudnia (gdy 25.12 to niedziela, liczymy od 18.12).
    last_sunday = christmas - timedelta(days=(christmas.weekday() + 1) % 7 or 7)
    if last_sunday - timedelta(weeks=3) <= d < christmas:
        return "Adwent"
    return None


def sunset(d: date, lat: float, lon: float) -> time | None:
    """Zachód słońca (czas polski); None w dniach bez zachodu (nie zdarza się w Polsce)."""
    g = 2 * math.pi / 365 * (d.timetuple().tm_yday - 1)
    eqtime = 229.18 * (
        0.000075
        + 0.001868 * math.cos(g)
        - 0.032077 * math.sin(g)
        - 0.014615 * math.cos(2 * g)
        - 0.040849 * math.sin(2 * g)
    )
    decl = (
        0.006918
        - 0.399912 * math.cos(g)
        + 0.070257 * math.sin(g)
        - 0.006758 * math.cos(2 * g)
        + 0.000907 * math.sin(2 * g)
        - 0.002697 * math.cos(3 * g)
        + 0.00148 * math.sin(3 * g)
    )
    phi = math.radians(lat)
    cos_ha = math.cos(math.radians(90.833)) / (math.cos(phi) * math.cos(decl)) - math.tan(
        phi
    ) * math.tan(decl)
    if not -1 <= cos_ha <= 1:
        return None
    ha = math.degrees(math.acos(cos_ha))
    minutes = 720 + 4 * (ha - lon) - eqtime
    utc = datetime(d.year, d.month, d.day, tzinfo=ZoneInfo("UTC")) + timedelta(minutes=minutes)
    return utc.astimezone(TZ).time().replace(second=0, microsecond=0)


def _fmt(d: date) -> str:
    return f"{d.day} {MONTHS_GEN[d.month - 1]}"


def _months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + end.month - start.month - (end.day < start.day)


def check(d: date, *, ceremony_type: str, city: str, today: date) -> dict[str, Any]:
    lat, lon = CITIES.get(city, CITIES[DEFAULT_CITY])
    weekday = d.weekday()
    feast = {**holidays(d.year - 1), **holidays(d.year), **holidays(d.year + 1)}
    near = sorted(
        (h, name) for h, name in feast.items() if abs((h - d).days) <= NEAR_DAYS and h != d
    )
    season = "high" if d.month in HIGH_SEASON else "mid" if d.month in MID_SEASON else "low"
    church = church_season(d) if ceremony_type in CHURCH else None
    sun = sunset(d, lat, lon)
    months_left = _months_between(today, d)
    notes: list[str] = []
    if d <= today:
        notes.append("Ta data już minęła albo to dziś.")
    if d in feast:
        notes.append(
            f"To dzień ustawowo wolny ({feast[d]}). Zapytajcie w USC lub parafii, czy udzielają "
            "wtedy ślubów; część usługodawców liczy dopłatę świąteczną."
        )
    if near:
        names = ", ".join(f"{name} ({_fmt(h)})" for h, name in near)
        notes.append(
            f"Blisko święta: {names}. Długi weekend ułatwia przyjazd z daleka, ale część gości "
            "może mieć plany wyjazdowe, a noclegi bywają droższe."
        )
    if weekday == 5 and season == "high":
        notes.append(
            "Sobota w szczycie sezonu: najpopularniejszy termin — sale i usługodawcy znikają "
            "najwcześniej, rabatów zwykle brak."
        )
    elif weekday == 4:
        notes.append(
            "Piątek: sale często mają niższe ceny, ale część gości musi wziąć urlop "
            "(zwłaszcza na ślub w ciągu dnia)."
        )
    elif weekday == 6:
        notes.append(
            "Niedziela: często taniej, ale goście wracają do domu przed poniedziałkiem w pracy."
        )
    elif weekday < 4:
        notes.append(
            "Środek tygodnia: najtaniej, ale wielu gości musi wziąć dzień albo dwa urlopu."
        )
    if season == "low":
        notes.append(
            "Poza sezonem: łatwiej o wolną salę i rabat; krótszy dzień i chłodniej — plener "
            "i parking warto zaplanować wcześniej."
        )
    if church:
        notes.append(
            f"To {church}. Przy ślubie w kościele parafie zwykle odradzają w tym czasie huczne "
            "wesela — zapytajcie w parafii, zanim podpiszecie umowę z salą."
        )
    if 0 < months_left < BOOKING_MONTHS and d > today:
        notes.append(
            f"Do ślubu {months_left} mies. Popularne sale i fotografów rezerwuje się zwykle "
            "12-18 miesięcy wcześniej — warto zacząć od nich."
        )
    golden = None
    if sun:
        golden = (datetime.combine(d, sun) - timedelta(hours=1)).time()
    return {
        "date": d,
        "weekday": WEEKDAYS[weekday],
        "season": season,
        "holiday": feast.get(d),
        "holidays_near": [{"date": h, "name": name} for h, name in near],
        "church_season": church,
        "sunset": sun.strftime("%H:%M") if sun else None,
        "golden_hour_from": golden.strftime("%H:%M") if golden else None,
        "months_left": months_left if d > today else 0,
        "notes": notes,
    }
