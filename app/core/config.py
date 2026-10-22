"""Konfiguracja aplikacji wyłącznie ze zmiennych środowiskowych (prefiks WP_)."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Znacznik wartości przykładowej (nie sekret).
_DEV_SECRET_MARKER = "change-me"  # noqa: S105  # nosec B105


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WP_", env_file=".env", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "postgresql+psycopg://wedding:wedding@localhost:5432/wedding"
    # Na proces API: (pool_size + max_overflow) razy liczba procesów (WEB_CONCURRENCY) + worker
    # musi zmieścić się w max_connections PostgreSQL (domyślnie 100).
    db_pool_size: int = 10
    db_max_overflow: int = 10

    jwt_secret: SecretStr
    jwt_algorithm: Literal["HS256"] = "HS256"
    # Klucz AES-256 (base64, 32 bajty) do szyfrowania kolumn z danymi wrażliwymi.
    data_encryption_key: SecretStr
    # Rotacja klucza (docs/wdrozenie.md): nowy klucz dostaje kolejny numer wersji, stare klucze
    # zostają do odczytu w WP_DATA_ENCRYPTION_PREVIOUS_KEYS ("1:klucz,2:klucz") do czasu
    # przeszyfrowania danych skryptem scripts/rotate_encryption_key.py.
    data_encryption_key_version: int = 1
    data_encryption_previous_keys: SecretStr | None = None
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    # Powtórzenie tego samego refresh tokena w tym oknie (np. ponowienie żądania przy słabym
    # zasięgu) nie jest traktowane jak kradzież, o ile następca nie został jeszcze użyty.
    refresh_reuse_grace_seconds: int = 30
    # Ciasteczko refresh tokena klienta webowego tylko przez HTTPS (localhost przeglądarki
    # traktują jak bezpieczny kontekst, więc w dev też działa). False tylko w testach.
    auth_cookie_secure: bool = True

    email_verification_ttl_hours: int = 24
    password_reset_ttl_minutes: int = 60
    invitation_ttl_days: int = 14
    account_deletion_grace_days: int = 30

    login_max_failures: int = 5
    login_window_minutes: int = 15

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_starttls: bool = False
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    mail_from: str = "Wedding Planner <no-reply@weddingplanner.local>"

    # Adres GUI w linkach e-maili i QR (dev: Vite). Port 8000 zajmuje inna aplikacja właściciela.
    public_app_url: str = "http://localhost:5173"
    expose_docs: bool = True

    # Globalny limit żądań na użytkownika/IP na instancję API (0 = wyłączony).
    rate_limit_per_minute: int = 600
    # Publiczne RSVP: zapytań z jednego IP na 10 minut (wiele rodzin z jednej sieci).
    rsvp_rate_limit: int = 60
    # Dokumenty: lokalny katalog (wolumen Dockera) albo magazyn S3-compatible (dostawca w UE).
    storage_backend: Literal["local", "s3"] = "local"
    storage_dir: str = "storage"
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None
    s3_region: str = "eu-central-1"
    s3_access_key_id: str | None = None
    s3_secret_access_key: SecretStr | None = None
    max_upload_mb: int = 20
    max_documents_per_wedding: int = 300
    max_storage_mb_per_wedding: int = 1000
    ocr_enabled: bool = True
    ocr_languages: str = "pol+eng"
    ocr_max_pages: int = 20
    # Skanowanie plików: ClamAV (clamd) jako osobny kontener (GPL — tylko osobny proces, ADR-0006).
    # Puste = skanowanie wyłączone (pliki oznaczone „nie sprawdzono”); w produkcji wymagane.
    clamav_host: str | None = None
    clamav_port: int = 3310
    clamav_timeout_seconds: int = 120

    # AI (ADR-0005): domyślnie lokalny model przez Ollama — dane nie opuszczają serwera.
    # "fake" i "fake_external" to dublery do testów (bez sieci). Zewnętrzny dostawca: później.
    ai_enabled: bool = True
    ai_provider: Literal["ollama", "fake", "fake_external"] = "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    ai_timeout_seconds: int = 600
    ai_max_input_chars: int = 20000
    ai_max_runs_per_wedding_per_day: int = 20
    log_level: str = "INFO"
    log_json: bool = True

    terms_version: str = "2026-10-draft"
    privacy_version: str = "2026-10-draft"

    @field_validator("jwt_secret")
    @classmethod
    def _secret_long_enough(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < 32:
            raise ValueError("WP_JWT_SECRET musi mieć co najmniej 32 znaki")
        return v

    @model_validator(mode="after")
    def _consistency(self) -> "Settings":
        if not 1 <= self.data_encryption_key_version <= 255:
            raise ValueError("WP_DATA_ENCRYPTION_KEY_VERSION musi być z zakresu 1-255")
        if self.storage_backend == "s3" and not self.s3_bucket:
            raise ValueError("Dla WP_STORAGE_BACKEND=s3 ustaw WP_S3_BUCKET")
        return self

    @model_validator(mode="after")
    def _prod_guards(self) -> "Settings":
        if self.env == "prod":
            if _DEV_SECRET_MARKER in self.jwt_secret.get_secret_value():
                raise ValueError("W produkcji WP_JWT_SECRET nie może być wartością przykładową")
            if self.expose_docs:
                raise ValueError("W produkcji ustaw WP_EXPOSE_DOCS=false")
            if not self.clamav_host:
                raise ValueError("W produkcji ustaw WP_CLAMAV_HOST (skanowanie plików, ClamAV)")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
