"""Menu wesela z alergenami: dania, oznaczenia 14 alergenów, ostrzeżenia przy dietach gości.

Ostrzegamy, gdy w danym daniu menu (np. danie główne) nie ma nic dla gości z dietą
wegetariańską, wegańską lub bezglutenową z listy gości. Uwag dietetycznych (szyfrowanych,
mogą dotyczyć zdrowia) nie analizujemy — o alergiach z uwag para rozmawia z salą sama.
Menu można pokazać gościom na ich stronie (bez listy gości i bez ostrzeżeń).
"""

from collections import Counter
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.errors import Conflict, NotFound
from app.modules.audit import service as audit
from app.modules.guests.models import Guest, GuestEventAttendance, GuestInfo
from app.modules.identity.service import Principal
from app.modules.menu.models import ALLERGENS, COURSES, MenuDish
from app.modules.workspace.permissions import Action, authorize

COURSE_LABELS = {
    "starter": "Przystawka",
    "soup": "Zupa",
    "main": "Danie główne",
    "dessert": "Deser",
    "cake": "Tort",
    "hot": "Danie gorące (wieczorem)",
    "cold": "Zimna płyta",
    "other": "Inne",
}
DIET_LABELS = {
    "vegetarian": "wegetariańskiej",
    "vegan": "wegańskiej",
    "gluten_free": "bezglutenowej",
}
# Na te dania menu każdy gość czeka — tu brak opcji dla diety to problem; desery i tort pomijamy.
CHECKED_COURSES = ("starter", "soup", "main", "hot")
_ORDER = {c: i for i, c in enumerate(COURSES)}


def _ordered(db: Session, wedding_id: UUID) -> list[MenuDish]:
    dishes = db.scalars(select(MenuDish).where(MenuDish.wedding_id == wedding_id))
    return sorted(dishes, key=lambda d: (_ORDER[d.course], d.position, d.created_at))


def suits(dish: MenuDish, diet: str) -> bool:
    if diet == "vegetarian":
        return dish.vegetarian
    if diet == "vegan":
        return dish.vegan
    if diet == "gluten_free":
        return "gluten" not in dish.allergens
    return True


def diet_counts(db: Session, wedding_id: UUID) -> Counter[str]:
    """Goście z dietą (bez tych, którzy odmówili wszystkich wydarzeń)."""
    declined_all = (
        select(GuestEventAttendance.guest_id)
        .group_by(GuestEventAttendance.guest_id)
        .having(func.bool_and(GuestEventAttendance.status == "declined"))
    )
    rows = db.execute(
        select(Guest.dietary_preference, func.count())
        .where(
            Guest.wedding_id == wedding_id,
            Guest.dietary_preference.in_(tuple(DIET_LABELS)),
            Guest.id.not_in(declined_all),
        )
        .group_by(Guest.dietary_preference)
    )
    return Counter({diet: n for diet, n in rows})


def warnings(dishes: list[MenuDish], diets: Counter[str]) -> list[str]:
    out = []
    for course in CHECKED_COURSES:
        in_course = [d for d in dishes if d.course == course]
        if not in_course:
            continue
        for diet, n in diets.items():
            # Weganin może zjeść danie wegańskie; wegetarianin — wegetariańskie lub wegańskie.
            if n and not any(suits(d, diet) for d in in_course):
                out.append(
                    f"{COURSE_LABELS[course]}: nic dla diety {DIET_LABELS[diet]} "
                    f"({n} os. z listy gości). Poproście salę o wariant."
                )
    return out


def dish_out(d: MenuDish) -> dict[str, Any]:
    return {
        "id": d.id,
        "course": d.course,
        "name": d.name,
        "description": d.description,
        "allergens": [a for a in ALLERGENS if a in d.allergens],
        "vegetarian": d.vegetarian,
        "vegan": d.vegan,
        "gluten_free": "gluten" not in d.allergens,
        "version": d.version,
    }


def overview(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    dishes = _ordered(db, wedding_id)
    diets = diet_counts(db, wedding_id)
    info = db.get(GuestInfo, wedding_id)
    return {
        "dishes": [dish_out(d) for d in dishes],
        "diets": {k: diets.get(k, 0) for k in DIET_LABELS},
        "warnings": warnings(dishes, diets),
        "show_to_guests": bool(info and info.show_menu),
    }


def guest_menu(db: Session, wedding_id: UUID) -> list[dict[str, Any]] | None:
    """Menu na stronę gościa (gdy para je pokazała); bez wersji i identyfikatorów."""
    info = db.get(GuestInfo, wedding_id)
    if not (info and info.show_menu):
        return None
    return [
        {k: v for k, v in dish_out(d).items() if k not in ("id", "version")}
        for d in _ordered(db, wedding_id)
    ]


def _dish(db: Session, wedding_id: UUID, dish_id: UUID) -> MenuDish:
    d = db.get(MenuDish, dish_id)
    if d is None or d.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono dania.", code="menu.not_found")
    return d


def _record(
    db: Session, principal: Principal, wedding_id: UUID, entity_id: UUID, action: str
) -> None:
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="menu_dish",
        entity_id=entity_id,
        wedding_id=wedding_id,
        action=action,
    )


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("vegan"):
        data["vegetarian"] = True
    if data.get("allergens") is not None:
        data["allergens"] = sorted(set(data["allergens"]), key=ALLERGENS.index)
    return data


def create(db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    last = db.scalar(
        select(func.max(MenuDish.position)).where(
            MenuDish.wedding_id == wedding_id, MenuDish.course == data["course"]
        )
    )
    d = MenuDish(
        wedding_id=wedding_id, position=0 if last is None else last + 1, **_normalize(data)
    )
    db.add(d)
    db.flush()
    _record(db, principal, wedding_id, d.id, "create")
    db.commit()


def update(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    dish_id: UUID,
    data: dict[str, Any],
    version: int,
) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    d = _dish(db, wedding_id, dish_id)
    if d.version != version:
        raise Conflict("Danie zmieniło się w międzyczasie.", code="conflict.version_mismatch")
    data = _normalize(data)
    if data.get("vegetarian") is False and d.vegan and "vegan" not in data:
        data["vegan"] = False  # niewegetariańskie nie może być wegańskie
    for k, v in data.items():
        if v is not None or k == "description":
            setattr(d, k, v)
    _record(db, principal, wedding_id, d.id, "update")
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise Conflict(
            "Danie zmieniło się w międzyczasie.", code="conflict.version_mismatch"
        ) from exc


def delete(db: Session, principal: Principal, wedding_id: UUID, dish_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    db.delete(_dish(db, wedding_id, dish_id))
    _record(db, principal, wedding_id, dish_id, "delete")
    db.commit()


def set_show_to_guests(db: Session, principal: Principal, wedding_id: UUID, on: bool) -> bool:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    info = db.get(GuestInfo, wedding_id)
    if info is None:
        info = GuestInfo(wedding_id=wedding_id)
        db.add(info)
    info.show_menu = on
    _record(db, principal, wedding_id, wedding_id, "show_on" if on else "show_off")
    db.commit()
    return on
