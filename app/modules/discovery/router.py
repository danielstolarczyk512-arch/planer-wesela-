from datetime import datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from app.core.db import utcnow
from app.core.deps import DbSession
from app.core.errors import Conflict, NotFound, Unprocessable
from app.jobs.queue import Job, enqueue
from app.modules.audit import service as audit
from app.modules.catalog import service as catalog
from app.modules.catalog.models import SourceObservation, VendorSource
from app.modules.catalog.router import Admin
from app.modules.discovery import service
from app.modules.vendors.models import CATEGORIES

router = APIRouter(prefix="/admin/discovery", tags=["badacz katalogu: administrator"])

Category = Annotated[str, Field(min_length=2, max_length=32)]


class SourceCreate(BaseModel):
    url: str = Field(min_length=8, max_length=500, examples=["https://studio-foto.example/cennik"])
    category: Category = "photographer"
    region_hint: str | None = Field(default=None, max_length=120)
    access_basis: str | None = Field(default=None, max_length=300)
    refresh_interval_days: int = Field(default=14, ge=1, le=365)
    catalog_vendor_id: UUID | None = None


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    url: str
    domain: str
    category: str
    region_hint: str | None
    access_basis: str
    state: str
    state_reason: str | None
    refresh_interval_days: int
    next_check_at: datetime
    last_checked_at: datetime | None
    last_success_at: datetime | None
    consecutive_failures: int
    catalog_vendor_id: UUID | None


class SourcePatch(BaseModel):
    state: Literal["active", "paused"]


class LimitsBody(BaseModel):
    daily_fetch_limit: int = Field(ge=0, le=10_000)


@router.get("/status", summary="Stan badacza: tętno, kolejka, źródła, możliwości")
def status(admin: Admin, db: DbSession) -> dict[str, Any]:
    control = service.get_control(db)
    now = utcnow()
    states = dict(
        db.execute(select(VendorSource.state, func.count()).group_by(VendorSource.state)).all()
    )
    queued = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.type == service.FETCH_JOB, Job.status == "queued")
    )
    dead = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.type == service.FETCH_JOB, Job.status == "dead")
    )
    oldest = db.scalar(
        select(func.min(Job.run_after)).where(Job.type == service.FETCH_JOB, Job.status == "queued")
    )
    overdue = db.scalar(
        select(func.min(VendorSource.next_check_at)).where(
            VendorSource.state == "active", VendorSource.next_check_at < now
        )
    )
    used = db.scalar(
        select(func.count())
        .select_from(SourceObservation)
        .where(SourceObservation.fetched_at > now - timedelta(hours=24))
    )
    db.commit()
    return {
        "paused": control.paused,
        "daily_fetch_limit": control.daily_fetch_limit,
        "fetches_last_24h": used or 0,
        "worker_heartbeat_at": control.worker_heartbeat_at,
        "scheduler_heartbeat_at": control.scheduler_heartbeat_at,
        "last_success_at": control.last_success_at,
        "sources_by_state": states,
        "queued_jobs": queued or 0,
        "dead_jobs": dead or 0,
        "oldest_queued_job_at": oldest,
        "oldest_overdue_source_at": overdue,
        "catalog": catalog.stats(db),
        "capabilities": service.capabilities(),
    }


@router.post("/pause", summary="Wstrzymaj badacza")
def pause(admin: Admin, db: DbSession) -> dict[str, bool]:
    return _set_paused(db, admin.user.id, True)


@router.post("/resume", summary="Wznów badacza")
def resume(admin: Admin, db: DbSession) -> dict[str, bool]:
    return _set_paused(db, admin.user.id, False)


def _set_paused(db: DbSession, admin_id: UUID, paused: bool) -> dict[str, bool]:
    control = service.get_control(db)
    control.paused, control.updated_by = paused, admin_id
    audit.record(
        db,
        actor_type="admin",
        actor_id=admin_id,
        entity_type="discovery_control",
        entity_id=None,
        action="pause" if paused else "resume",
    )
    db.commit()
    return {"paused": paused}


@router.put("/limits", summary="Dzienny limit pobrań")
def limits(body: LimitsBody, admin: Admin, db: DbSession) -> dict[str, int]:
    control = service.get_control(db)
    control.daily_fetch_limit, control.updated_by = body.daily_fetch_limit, admin.user.id
    audit.record(
        db,
        actor_type="admin",
        actor_id=admin.user.id,
        entity_type="discovery_control",
        entity_id=None,
        action="set_limit",
        changes={"daily_fetch_limit": body.daily_fetch_limit},
    )
    db.commit()
    return {"daily_fetch_limit": body.daily_fetch_limit}


@router.get("/sources", summary="Źródła (strony firm)")
def list_sources(
    admin: Admin,
    db: DbSession,
    state: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[SourceOut]:
    query = select(VendorSource).order_by(VendorSource.created_at.desc()).limit(limit)
    if state:
        query = query.where(VendorSource.state == state)
    return [SourceOut.model_validate(s) for s in db.scalars(query)]


@router.post("/sources", status_code=201, summary="Dodaj stronę firmy jako źródło")
def create_source(body: SourceCreate, admin: Admin, db: DbSession) -> SourceOut:
    if body.category not in CATEGORIES:
        raise Unprocessable("Nieznana kategoria.", code="discovery.bad_category")
    source = service.add_source(
        db,
        admin.user.id,
        url=body.url,
        category=body.category,
        region_hint=body.region_hint,
        access_basis=body.access_basis,
        refresh_interval_days=body.refresh_interval_days,
        catalog_vendor_id=body.catalog_vendor_id,
    )
    db.commit()
    return SourceOut.model_validate(source)


@router.patch("/sources/{source_id}", summary="Wstrzymaj albo wznów źródło")
def patch_source(source_id: UUID, body: SourcePatch, admin: Admin, db: DbSession) -> SourceOut:
    source = db.get(VendorSource, source_id)
    if source is None:
        raise NotFound("Nie znaleziono źródła.", code="discovery.source_not_found")
    if body.state == "active":
        source.state, source.state_reason = "active", None
        source.consecutive_failures, source.next_check_at = 0, utcnow()
    else:
        source.state = "paused"
    audit.record(
        db,
        actor_type="admin",
        actor_id=admin.user.id,
        entity_type="catalog_source",
        entity_id=source.id,
        action=f"set_{body.state}",
    )
    db.commit()
    return SourceOut.model_validate(source)


@router.post("/sources/{source_id}/fetch-now", status_code=202, summary="Odśwież teraz")
def fetch_now(source_id: UUID, admin: Admin, db: DbSession) -> dict[str, str]:
    source = db.get(VendorSource, source_id)
    if source is None:
        raise NotFound("Nie znaleziono źródła.", code="discovery.source_not_found")
    if source.state != "active":
        raise Conflict("Źródło jest wstrzymane albo zablokowane.", code="discovery.source_inactive")
    source.next_check_at = utcnow()
    db.flush()
    pending = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(
            Job.type == service.FETCH_JOB,
            Job.status.in_(("queued", "running")),
            Job.payload["source_id"].astext == str(source.id),
        )
    )
    if not pending:
        enqueue(db, service.FETCH_JOB, {"source_id": str(source.id)}, max_attempts=3)
    db.commit()
    return {"status": "queued"}
