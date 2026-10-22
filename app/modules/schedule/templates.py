"""Szablon typowego dnia polskiego wesela (punkt startowy do edycji, nie norma).

Czasy liczone w minutach względem godziny ceremonii.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Step:
    code: str
    title: str
    offset: int
    duration: int
    event_kind: str | None = None
    buffer_before: int = 0
    buffer_after: int = 0
    depends_on: tuple[str, ...] = field(default_factory=tuple)
    preparations: str | None = None


TEMPLATE_VERSION = "dzien-2026.1"


def steps(ceremony_type: str) -> list[Step]:
    ceremony_minutes = 30 if ceremony_type in ("civil", "humanist") else 60
    place = "urzędu" if ceremony_type == "civil" else "kościoła"
    after = ceremony_minutes
    return [
        Step(
            "bride_prep",
            "Przygotowania Panny Młodej (fryzura, makijaż)",
            -300,
            180,
            preparations="Potwierdź godzinę z fryzjerką i makijażystką",
        ),
        Step("groom_prep", "Przygotowania Pana Młodego", -150, 90),
        Step(
            "blessing",
            "Błogosławieństwo rodziców",
            -75,
            20,
            preparations="Ustal, kto mówi słowa błogosławieństwa",
        ),
        Step(
            "to_ceremony",
            f"Przejazd do {place}",
            -45,
            30,
            buffer_after=10,
            depends_on=("blessing",),
        ),
        Step(
            "ceremony",
            "Ceremonia ślubna",
            0,
            ceremony_minutes,
            "ceremony",
            depends_on=("to_ceremony",),
            preparations="Obrączki, dokumenty, świadkowie",
        ),
        Step(
            "wishes",
            f"Życzenia przed budynkiem {place}",
            after,
            30,
            "ceremony",
            depends_on=("ceremony",),
        ),
        Step(
            "to_venue", "Przejazd na salę", after + 30, 30, buffer_after=10, depends_on=("wishes",)
        ),
        Step(
            "welcome",
            "Powitanie chlebem i solą",
            after + 70,
            15,
            "reception",
            depends_on=("to_venue",),
            preparations="Chleb, sól, kieliszki",
        ),
        Step("dinner", "Obiad", after + 85, 60, "reception", depends_on=("welcome",)),
        Step(
            "first_dance", "Pierwszy taniec", after + 150, 10, "reception", depends_on=("dinner",)
        ),
        Step("cake", "Krojenie tortu", 510, 20, "reception"),
        Step(
            "oczepiny",
            "Oczepiny",
            570,
            45,
            "reception",
            preparations="Ustal z zespołem/DJ-em zabawy i rekwizyty",
        ),
        Step("end", "Zakończenie przyjęcia", 780, 0, "reception"),
    ]
