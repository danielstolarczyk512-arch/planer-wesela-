from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.deps import CurrentPrincipal, DbSession
from app.modules.notifications import service

router = APIRouter(prefix="/me/notifications", tags=["konto"])


class NotificationSettings(BaseModel):
    digest: Literal["daily", "weekly", "off"]


@router.get("", summary="Ustawienia przypomnień e-mail")
def get_settings_(principal: CurrentPrincipal, db: DbSession) -> NotificationSettings:
    return NotificationSettings.model_validate({"digest": service.get_preference(db, principal)})


@router.put("", summary="Zmiana częstotliwości podsumowań (daily / weekly / off)")
def put_settings(
    body: NotificationSettings, principal: CurrentPrincipal, db: DbSession
) -> NotificationSettings:
    service.set_preference(db, principal, body.digest)
    return body
