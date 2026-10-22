from fastapi import APIRouter, FastAPI

from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.idempotency import IdempotencyMiddleware
from app.core.limits import BodySizeLimitMiddleware
from app.core.logging import RequestContextMiddleware, configure_logging
from app.core.throttle import ThrottleMiddleware
from app.health import router as health_router
from app.modules.aftercare.router import router as aftercare_router
from app.modules.ai.router import router as ai_router
from app.modules.budget.router import router as budget_router
from app.modules.calendar.router import public_router as calendar_public_router
from app.modules.calendar.router import router as calendar_router
from app.modules.documents.router import router as documents_router
from app.modules.guests.router import public_router as rsvp_router
from app.modules.guests.router import router as guests_router
from app.modules.identity.router import auth_router, me_router
from app.modules.logistics.router import router as logistics_router
from app.modules.menu.router import router as menu_router
from app.modules.notifications.router import router as notifications_router
from app.modules.offers.router import router as offers_router
from app.modules.overview.router import router as overview_router
from app.modules.planner.router import public_router as helper_public_router
from app.modules.planner.router import router as planner_router
from app.modules.schedule.router import public_router as day_public_router
from app.modules.schedule.router import router as schedule_router
from app.modules.seating.router import router as seating_router
from app.modules.vendors.router import router as vendors_router
from app.modules.workspace.router import router as workspace_router

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    docs = settings.expose_docs
    app = FastAPI(
        title="Wedding Planner AI — API",
        version="0.6.0",
        description="Backend API (MVP, Etap 6). Dokumentacja: docs/api.md.",
        openapi_url=f"{API_PREFIX}/openapi.json" if docs else None,
        docs_url=f"{API_PREFIX}/docs" if docs else None,
        redoc_url=None,
    )
    # Kolejność: ostatnio dodany jest najbardziej zewnętrzny (logi obejmują wszystko).
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(ThrottleMiddleware)
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)
    for router in (
        auth_router,
        me_router,
        notifications_router,
        workspace_router,
        overview_router,
        planner_router,
        helper_public_router,
        budget_router,
        guests_router,
        menu_router,
        rsvp_router,
        vendors_router,
        offers_router,
        documents_router,
        ai_router,
        schedule_router,
        seating_router,
        logistics_router,
        aftercare_router,
        calendar_router,
        calendar_public_router,
        day_public_router,
    ):
        api.include_router(router)
    app.include_router(api)
    app.include_router(health_router)
    return app


app = create_app()
