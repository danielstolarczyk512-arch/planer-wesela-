"""Kontrola dostępu na poziomie wesela: rola członka → dozwolone akcje.

Brak członkostwa zawsze kończy się 404 (nie ujawniamy, że wesele istnieje).
"""

from enum import StrEnum
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import Forbidden, NotFound
from app.modules.workspace.models import WeddingMember


class Action(StrEnum):
    READ = "wedding:read"
    WRITE = "wedding:write"
    DELETE = "wedding:delete"
    MANAGE_MEMBERS = "members:manage"
    EXPORT = "wedding:export"
    RUN_AI = "ai:run"
    # Dzień ślubu: program, wydarzenia, kontakty do usługodawców (bez budżetu i gości).
    DAY_READ = "day:read"
    # Prowadzenie dnia: przesuwanie programu, gdy coś się opóźnia.
    DAY_RUN = "day:run"
    # Podstawowe dane wesela (nazwa, data, moja rola): każdy członek.
    BASIC = "wedding:basic"
    # Sponsor (np. rodzice): tylko własny wkład — obiecane, wpłacone, płatności do zrobienia.
    FUNDER_SELF = "funder:self"


ROLE_ACTIONS: dict[str, frozenset[Action]] = {
    "owner": frozenset(Action),
    "coorganizer": frozenset(
        {
            Action.READ,
            Action.WRITE,
            Action.EXPORT,
            Action.RUN_AI,
            Action.DAY_READ,
            Action.DAY_RUN,
            Action.BASIC,
        }
    ),
    "viewer": frozenset({Action.READ, Action.DAY_READ, Action.BASIC}),
    # Koordynator dnia (np. świadek): tylko to, co potrzebne w dniu ślubu. Nie widzi budżetu,
    # listy gości (diety to dane o zdrowiu) ani ofert.
    "coordinator": frozenset({Action.DAY_READ, Action.DAY_RUN, Action.BASIC}),
    # Sponsor (np. rodzice dokładający się do wesela): tylko swój wkład, bez gości i reszty budżetu.
    "sponsor": frozenset({Action.BASIC, Action.FUNDER_SELF}),
}


def authorize(db: Session, user_id: UUID, wedding_id: UUID, action: Action) -> WeddingMember:
    member = db.get(WeddingMember, (wedding_id, user_id))
    if member is None:
        raise NotFound("Nie znaleziono wesela.", code="wedding.not_found")
    if action not in ROLE_ACTIONS[member.role]:
        raise Forbidden("Twoja rola nie pozwala na tę operację.", code="wedding.forbidden")
    return member
