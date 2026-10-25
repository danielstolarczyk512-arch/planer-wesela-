from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, Response, status

from app.core.config import get_settings
from app.core.deps import CurrentPrincipal, DbSession
from app.core.errors import Unauthorized, Unprocessable
from app.core.net import ip_prefix, user_agent
from app.modules.identity import mfa, service
from app.modules.identity.schemas import (
    AcceptedOut,
    ChangePasswordIn,
    ConsentIn,
    ConsentOut,
    DeleteAccountIn,
    ForgotPasswordIn,
    LoginIn,
    LoginMfaIn,
    MeOut,
    MePatch,
    MfaChallengeOut,
    MfaCodeIn,
    MfaConfirmIn,
    MfaSetupOut,
    PasswordConfirmIn,
    RecoveryCodesOut,
    RefreshIn,
    RegisterIn,
    ResetPasswordIn,
    SessionOut,
    TokenIn,
    TokenPairOut,
    VerifyCodeIn,
)
from app.modules.identity.service import IssuedTokens, Principal

auth_router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(prefix="/me", tags=["konto"])

_ERR = {
    401: {"description": "Brak lub nieprawidłowe uwierzytelnienie"},
    422: {"description": "Błąd walidacji"},
    429: {"description": "Przekroczony limit żądań (nagłówek Retry-After)"},
}


REFRESH_COOKIE = "wp_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _is_web(request: Request) -> bool:
    """Klient webowy: refresh token tylko w ciasteczku HttpOnly (ochrona przed XSS).

    Nagłówek X-Client wymusza preflight CORS, więc obca strona nie wyśle go w tle (CSRF);
    dodatkowo ciasteczko ma SameSite=Strict.
    """
    return request.headers.get("x-client") == "web"


def _pair(t: IssuedTokens, request: Request, response: Response) -> TokenPairOut:
    if not _is_web(request):
        return TokenPairOut(
            access_token=t.access_token, refresh_token=t.refresh_token, expires_in=t.expires_in
        )
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        t.refresh_token,
        max_age=settings.refresh_token_ttl_days * 86400,
        path=REFRESH_COOKIE_PATH,
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    return TokenPairOut(access_token=t.access_token, refresh_token=None, expires_in=t.expires_in)


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        secure=get_settings().auth_cookie_secure,
        httponly=True,
        samesite="strict",
    )


def _me(p: Principal, db: DbSession) -> MeOut:
    u = p.user
    enabled = mfa.is_enabled(db, u.id)
    return MeOut(
        mfa_enabled=enabled,
        mfa_recovery_codes_left=mfa.remaining_recovery_codes(db, u.id) if enabled else None,
        id=u.id,
        email=u.email,
        display_name=u.display_name,
        locale=u.locale,
        global_role=u.global_role,
        email_verified=u.email_verified,
        created_at=u.created_at,
        deletion_scheduled_at=service.deletion_scheduled_at(u),
    )


@auth_router.post(
    "/register",
    status_code=status.HTTP_202_ACCEPTED,
    responses={422: _ERR[422], 429: _ERR[429]},
    summary="Rejestracja",
    description="Zawsze 202, niezależnie od tego, czy konto istnieje (ochrona przed "
    "enumeracją). Link weryfikacyjny wysyłany e-mailem.",
)
def register(body: RegisterIn, request: Request, db: DbSession) -> AcceptedOut:
    service.register(
        db,
        email=body.email,
        password=body.password.get_secret_value(),
        display_name=body.display_name,
        ip=ip_prefix(request),
    )
    return AcceptedOut(detail="Sprawdź skrzynkę e-mail, aby dokończyć rejestrację.")


@auth_router.post(
    "/verify-email",
    status_code=204,
    responses={422: _ERR[422]},
    summary="Potwierdzenie adresu e-mail tokenem z wiadomości",
)
def verify_email(body: TokenIn, request: Request, db: DbSession) -> None:
    service.verify_email(db, token=body.token, ip=ip_prefix(request))


@me_router.post(
    "/verify-email/code",
    status_code=204,
    responses={422: _ERR[422], 429: _ERR[429]},
    summary="Potwierdzenie adresu e-mail 6-cyfrowym kodem z wiadomości",
)
def verify_email_code(body: VerifyCodeIn, principal: CurrentPrincipal, db: DbSession) -> None:
    service.verify_email_code(db, principal, code=body.code)


@auth_router.post(
    "/login",
    responses={401: _ERR[401], 403: {"description": "Konto zablokowane"}, 429: _ERR[429]},
    summary="Logowanie",
    description="Przy włączonej weryfikacji dwuetapowej zwraca `mfa_required` i `mfa_token` "
    "zamiast tokenów; dokończenie: POST /auth/login/mfa.",
)
def login(
    body: LoginIn, request: Request, response: Response, db: DbSession
) -> TokenPairOut | MfaChallengeOut:
    result = service.login(
        db,
        email=body.email,
        password=body.password.get_secret_value(),
        ip=ip_prefix(request),
        user_agent=user_agent(request),
    )
    if isinstance(result, mfa.MfaChallenge):
        return MfaChallengeOut(mfa_token=result.mfa_token, expires_in=result.expires_in)
    return _pair(result, request, response)


@auth_router.post(
    "/login/mfa",
    responses={401: _ERR[401], 429: _ERR[429]},
    summary="Drugi krok logowania: kod z aplikacji (TOTP) albo kod zapasowy",
)
def login_mfa(
    body: LoginMfaIn, request: Request, response: Response, db: DbSession
) -> TokenPairOut:
    tokens = service.login_mfa(
        db,
        mfa_token=body.mfa_token,
        code=body.code,
        ip=ip_prefix(request),
        user_agent=user_agent(request),
    )
    return _pair(tokens, request, response)


@auth_router.post(
    "/refresh",
    responses={401: _ERR[401]},
    summary="Rotacja refresh tokena (stary token przestaje działać)",
    description="Aplikacja mobilna wysyła token w treści. Klient webowy (X-Client: web) "
    "wysyła pustą treść, a token jest w ciasteczku HttpOnly.",
)
def refresh(
    request: Request, response: Response, db: DbSession, body: RefreshIn | None = None
) -> TokenPairOut:
    token = body.refresh_token if body else None
    if token is None and _is_web(request):
        token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise Unauthorized("Sesja wygasła. Zaloguj się ponownie.", code="auth.invalid_refresh")
    try:
        tokens = service.refresh(
            db, refresh_token=token, ip=ip_prefix(request), user_agent=user_agent(request)
        )
    except Unauthorized as exc:
        if _is_web(request):
            # Odpowiedź błędu nie przenosi nagłówków z `response`: czyścimy ciasteczko w wyjątku.
            exc.headers["Set-Cookie"] = _expired_cookie_header()
        raise
    return _pair(tokens, request, response)


def _expired_cookie_header() -> str:
    tmp = Response()
    _clear_cookie(tmp)
    return tmp.headers["set-cookie"]


@auth_router.post(
    "/logout",
    status_code=204,
    responses={401: _ERR[401]},
    summary="Wylogowanie bieżącego urządzenia",
)
def logout(
    principal: CurrentPrincipal, request: Request, response: Response, db: DbSession
) -> None:
    service.logout(db, principal)
    if _is_web(request):
        _clear_cookie(response)


@auth_router.post(
    "/password/forgot",
    status_code=202,
    responses={429: _ERR[429]},
    summary="Wysyłka linku do resetu hasła (zawsze 202)",
)
def forgot_password(body: ForgotPasswordIn, request: Request, db: DbSession) -> AcceptedOut:
    service.forgot_password(db, email=body.email, ip=ip_prefix(request))
    return AcceptedOut(detail="Jeśli konto istnieje, wysłaliśmy link do resetu hasła.")


@auth_router.post(
    "/password/reset",
    status_code=204,
    responses={422: _ERR[422]},
    summary="Ustawienie nowego hasła; wylogowuje wszystkie urządzenia",
)
def reset_password(body: ResetPasswordIn, request: Request, db: DbSession) -> None:
    service.reset_password(
        db,
        token=body.token,
        new_password=body.new_password.get_secret_value(),
        ip=ip_prefix(request),
    )


@me_router.get("", responses={401: _ERR[401]}, summary="Mój profil")
def get_me(principal: CurrentPrincipal, db: DbSession) -> MeOut:
    return _me(principal, db)


@me_router.patch("", responses={401: _ERR[401], 422: _ERR[422]}, summary="Edycja profilu")
def patch_me(body: MePatch, principal: CurrentPrincipal, db: DbSession) -> MeOut:
    service.update_profile(db, principal, body.model_dump(exclude_unset=True))
    return _me(principal, db)


@me_router.post(
    "/verify-email/resend",
    status_code=204,
    responses={429: _ERR[429]},
    summary="Ponowna wysyłka linku weryfikacyjnego",
)
def resend_verification(principal: CurrentPrincipal, db: DbSession) -> None:
    service.resend_verification(db, principal)


@me_router.post(
    "/password",
    status_code=204,
    responses={401: _ERR[401], 422: _ERR[422]},
    summary="Zmiana hasła; wylogowuje pozostałe urządzenia",
)
def change_password(body: ChangePasswordIn, principal: CurrentPrincipal, db: DbSession) -> None:
    service.change_password(
        db,
        principal,
        current_password=body.current_password.get_secret_value(),
        new_password=body.new_password.get_secret_value(),
    )


@me_router.get("/sessions", summary="Aktywne sesje (urządzenia)")
def list_sessions(principal: CurrentPrincipal, db: DbSession) -> list[SessionOut]:
    return [
        SessionOut(
            id=s.id,
            created_at=s.created_at,
            expires_at=s.expires_at,
            user_agent=s.user_agent,
            current=s.family_id == principal.family_id,
        )
        for s in service.list_sessions(db, principal)
    ]


@me_router.delete(
    "/sessions/{session_id}",
    status_code=204,
    responses={404: {"description": "Nie znaleziono sesji"}},
    summary="Wylogowanie wybranego urządzenia",
)
def revoke_session(session_id: UUID, principal: CurrentPrincipal, db: DbSession) -> None:
    service.revoke_session(db, principal, session_id)


@me_router.get("/consents", summary="Historia zgód")
def list_consents(principal: CurrentPrincipal, db: DbSession) -> list[ConsentOut]:
    return [
        ConsentOut(
            type=c.type,
            document_version=c.document_version,
            granted_at=c.granted_at,
            withdrawn_at=c.withdrawn_at,
        )
        for c in service.list_consents(db, principal)
    ]


@me_router.post("/consents", status_code=201, summary="Udzielenie zgody")
def grant_consent(body: ConsentIn, principal: CurrentPrincipal, db: DbSession) -> ConsentOut:
    c = service.grant_consent(db, principal, body.type)
    return ConsentOut(
        type=c.type,
        document_version=c.document_version,
        granted_at=c.granted_at,
        withdrawn_at=c.withdrawn_at,
    )


@me_router.delete(
    "/consents/{consent_type}",
    status_code=204,
    responses={404: {"description": "Brak aktywnej zgody"}},
    summary="Wycofanie zgody (regulamin i polityka: tylko przez usunięcie konta)",
)
def withdraw_consent(consent_type: str, principal: CurrentPrincipal, db: DbSession) -> None:
    if consent_type not in ("marketing", "ai_external_processing"):
        raise Unprocessable("Tej zgody nie można wycofać osobno.", code="consent.not_withdrawable")
    service.withdraw_consent(db, principal, consent_type)


@me_router.get("/export", summary="Eksport moich danych (RODO art. 15 i 20), JSON")
def export_me(principal: CurrentPrincipal, db: DbSession) -> dict[str, Any]:
    return service.export_account(db, principal)


@me_router.delete(
    "",
    status_code=202,
    responses={
        401: _ERR[401],
        409: {"description": "Jesteś jedynym właścicielem wesela z innymi członkami"},
    },
    summary="Usunięcie konta (po okresie karencji)",
)
def delete_me(body: DeleteAccountIn, principal: CurrentPrincipal, db: DbSession) -> AcceptedOut:
    when = service.request_account_deletion(
        db, principal, password=body.password.get_secret_value()
    )
    return AcceptedOut(detail=f"Konto zostanie usunięte {when:%Y-%m-%d}.")


@me_router.post("/cancel-deletion", status_code=204, summary="Anulowanie usunięcia konta")
def cancel_deletion(principal: CurrentPrincipal, db: DbSession) -> None:
    service.cancel_account_deletion(db, principal)


# --- weryfikacja dwuetapowa ---------------------------------------------------------------


@me_router.post(
    "/mfa/setup",
    responses={401: _ERR[401], 409: {"description": "MFA już włączone"}},
    summary="Rozpoczęcie konfiguracji MFA: sekret i kod QR (wymaga hasła)",
)
def mfa_setup(body: PasswordConfirmIn, principal: CurrentPrincipal, db: DbSession) -> MfaSetupOut:
    data = mfa.start_setup(db, principal.user, password=body.password.get_secret_value())
    return MfaSetupOut(secret=data.secret, otpauth_uri=data.otpauth_uri, qr_svg=data.qr_svg)


@me_router.post(
    "/mfa/enable",
    responses={409: {"description": "Brak konfiguracji"}, 422: _ERR[422], 429: _ERR[429]},
    summary="Włączenie MFA kodem z aplikacji; zwraca kody zapasowe (jednorazowo)",
)
def mfa_enable(body: MfaCodeIn, principal: CurrentPrincipal, db: DbSession) -> RecoveryCodesOut:
    return RecoveryCodesOut(recovery_codes=mfa.enable(db, principal.user, code=body.code))


@me_router.post(
    "/mfa/disable",
    status_code=204,
    responses={401: _ERR[401], 429: _ERR[429]},
    summary="Wyłączenie MFA (hasło + kod z aplikacji albo zapasowy)",
)
def mfa_disable(body: MfaConfirmIn, principal: CurrentPrincipal, db: DbSession) -> None:
    mfa.disable(db, principal.user, password=body.password.get_secret_value(), code=body.code)


@me_router.post(
    "/mfa/recovery-codes",
    responses={401: _ERR[401], 429: _ERR[429]},
    summary="Nowe kody zapasowe (stare przestają działać); hasło + kod z aplikacji",
)
def mfa_recovery_codes(
    body: MfaConfirmIn, principal: CurrentPrincipal, db: DbSession
) -> RecoveryCodesOut:
    codes = mfa.regenerate_recovery_codes(
        db, principal.user, password=body.password.get_secret_value(), code=body.code
    )
    return RecoveryCodesOut(recovery_codes=codes)
