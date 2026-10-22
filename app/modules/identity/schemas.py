from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, SecretStr

NormalizedEmail = Annotated[EmailStr, AfterValidator(lambda v: v.strip().lower())]
# Długość hasła sprawdza polityka w serwisie; tu tylko twardy limit przed Argon2.
Password = Annotated[SecretStr, Field(min_length=1, max_length=256)]
Token = Annotated[str, Field(min_length=20, max_length=128)]


class RegisterIn(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "ania@example.com",
                "password": "dlugie-i-unikalne-haslo",  # nosec B105
                "display_name": "Ania",
                "accept_terms": True,
                "accept_privacy": True,
            }
        }
    )

    email: NormalizedEmail
    password: Password
    display_name: str | None = Field(default=None, max_length=100)
    accept_terms: Literal[True]
    accept_privacy: Literal[True]


class AcceptedOut(BaseModel):
    detail: str


class LoginIn(BaseModel):
    email: NormalizedEmail
    password: Password


class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str | None = Field(
        description="Dla klienta webowego (nagłówek X-Client: web) null: token jest wtedy "
        "w ciasteczku HttpOnly niedostępnym dla JavaScriptu"
    )
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - typ tokena, nie sekret
    expires_in: int = Field(description="Ważność access tokena w sekundach")


class RefreshIn(BaseModel):
    refresh_token: Token | None = Field(
        default=None, description="Pomijany przez klienta webowego (token w ciasteczku)"
    )


class TokenIn(BaseModel):
    token: Token


class ForgotPasswordIn(BaseModel):
    email: NormalizedEmail


class ResetPasswordIn(BaseModel):
    token: Token
    new_password: Password


class ChangePasswordIn(BaseModel):
    current_password: Password
    new_password: Password


class DeleteAccountIn(BaseModel):
    password: Password


class MeOut(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    locale: str
    global_role: str
    email_verified: bool
    created_at: datetime
    deletion_scheduled_at: datetime | None = None
    mfa_enabled: bool = False
    mfa_recovery_codes_left: int | None = Field(
        default=None, description="Niewykorzystane kody zapasowe (gdy MFA włączone)"
    )


class MePatch(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    locale: Literal["pl-PL", "en-GB"] | None = None


class SessionOut(BaseModel):
    id: UUID
    created_at: datetime
    expires_at: datetime
    user_agent: str | None
    current: bool


class ConsentOut(BaseModel):
    type: str
    document_version: str | None
    granted_at: datetime
    withdrawn_at: datetime | None


class ConsentIn(BaseModel):
    type: Literal["marketing", "ai_external_processing"]


# --- weryfikacja dwuetapowa (TOTP) ------------------------------------------------------


class MfaChallengeOut(BaseModel):
    mfa_required: Literal[True] = True
    mfa_token: str = Field(description="Jednorazowy token drugiego kroku (5 min)")
    expires_in: int


class LoginMfaIn(BaseModel):
    mfa_token: str = Field(min_length=20, max_length=2000)
    code: str = Field(min_length=6, max_length=20, description="Kod z aplikacji albo kod zapasowy")


class PasswordConfirmIn(BaseModel):
    password: Password


class MfaSetupOut(BaseModel):
    secret: str = Field(description="Do ręcznego wpisania w aplikacji (gdy nie da się zeskanować)")
    otpauth_uri: str
    qr_svg: str = Field(description="Kod QR jako SVG")


class MfaCodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=20)


class MfaConfirmIn(BaseModel):
    password: Password
    code: str = Field(min_length=6, max_length=20)


class RecoveryCodesOut(BaseModel):
    recovery_codes: list[str] = Field(description="Pokazywane tylko raz; każdy działa jeden raz")
