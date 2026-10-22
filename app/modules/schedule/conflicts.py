"""Wykrywanie konfliktów w harmonogramie dnia. Czysta logika, bez bazy i bez AI.

Przedział zajętości punktu = [start - bufor_przed, koniec + bufor_po]. Bufory modelują
dojazd i przygotowanie, więc nakładanie się przedziałów tej samej osoby lub tego samego
usługodawcy oznacza, że fizycznie nie zdąży.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import combinations
from uuid import UUID


@dataclass(frozen=True)
class Item:
    id: UUID
    title: str
    starts_at: datetime
    duration_minutes: int
    buffer_before_minutes: int = 0
    buffer_after_minutes: int = 0
    vendor_id: UUID | None = None
    vendor_booked: bool = True
    person: str | None = None  # id użytkownika lub imię (znormalizowane)
    event_window: tuple[datetime | None, datetime | None] | None = None
    depends_on: tuple[UUID, ...] = field(default_factory=tuple)

    @property
    def ends_at(self) -> datetime:
        return self.starts_at + timedelta(minutes=self.duration_minutes)

    @property
    def busy_from(self) -> datetime:
        return self.starts_at - timedelta(minutes=self.buffer_before_minutes)

    @property
    def busy_to(self) -> datetime:
        return self.ends_at + timedelta(minutes=self.buffer_after_minutes)


@dataclass(frozen=True)
class Conflict:
    code: str
    severity: str  # "error" | "warning"
    item_ids: tuple[UUID, ...]
    message: str


def _overlap(a: Item, b: Item) -> bool:
    return a.busy_from < b.busy_to and b.busy_from < a.busy_to


def _hhmm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def detect(items: list[Item]) -> list[Conflict]:
    found: list[Conflict] = []
    by_id = {i.id: i for i in items}
    for a, b in combinations(sorted(items, key=lambda i: i.starts_at), 2):
        if not _overlap(a, b):
            continue
        if a.vendor_id and a.vendor_id == b.vendor_id:
            found.append(
                Conflict(
                    "vendor_double_booked",
                    "error",
                    (a.id, b.id),
                    f"Ten sam usługodawca w „{a.title}” ({_hhmm(a.starts_at)}) i „{b.title}” "
                    f"({_hhmm(b.starts_at)}) — czasy (z buforami) nachodzą na siebie.",
                )
            )
        if a.person and a.person == b.person:
            found.append(
                Conflict(
                    "person_double_booked",
                    "error",
                    (a.id, b.id),
                    f"Ta sama osoba odpowiada za „{a.title}” i „{b.title}” w tym samym czasie.",
                )
            )
    for item in items:
        for dep_id in item.depends_on:
            dep = by_id.get(dep_id)
            if dep is None:
                continue
            ready = dep.ends_at + timedelta(
                minutes=dep.buffer_after_minutes + item.buffer_before_minutes
            )
            if item.starts_at < ready:
                found.append(
                    Conflict(
                        "dependency_order",
                        "error",
                        (dep.id, item.id),
                        f"„{item.title}” zaczyna się o {_hhmm(item.starts_at)}, a powinno po "
                        f"zakończeniu „{dep.title}” (najwcześniej {_hhmm(ready)}).",
                    )
                )
        if item.event_window:
            start, end = item.event_window
            if (start and item.starts_at < start) or (end and item.ends_at > end):
                found.append(
                    Conflict(
                        "outside_event",
                        "warning",
                        (item.id,),
                        f"„{item.title}” wychodzi poza godziny przypisanego wydarzenia.",
                    )
                )
        if item.vendor_id and not item.vendor_booked:
            found.append(
                Conflict(
                    "vendor_not_booked",
                    "warning",
                    (item.id,),
                    f"Usługodawca w „{item.title}” nie jest jeszcze zarezerwowany.",
                )
            )
    return found


def shifted(items: list[Item], start_from: datetime, minutes: int) -> dict[UUID, datetime]:
    """Nowe godziny po przesunięciu wszystkiego od `start_from` o `minutes` minut."""
    delta = timedelta(minutes=minutes)
    return {i.id: i.starts_at + delta for i in items if i.starts_at >= start_from}
