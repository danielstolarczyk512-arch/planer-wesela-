"""Wspólne schematy API: pieniądze, paginacja kursorowa."""

import base64
import binascii
from decimal import Decimal
from typing import Annotated, ClassVar, Generic, Literal, Self, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from app.core.errors import Unprocessable

Amount = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class Money(BaseModel):
    """Kwota jako string z dwoma miejscami po przecinku, nigdy float."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"amount": "65000.00", "currency": "PLN"}}
    )

    amount: Amount
    currency: Literal["PLN"] = "PLN"

    @field_serializer("amount")
    def _serialize_amount(self, v: Decimal) -> str:
        return f"{v:.2f}"


class PatchModel(BaseModel):
    """Częściowa aktualizacja: pola z NOT_NULL można pominąć, ale nie ustawić jawnie na null."""

    NOT_NULL: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def _no_explicit_nulls(self) -> Self:
        bad = [f for f in self.NOT_NULL if f in self.model_fields_set and getattr(self, f) is None]
        if bad:
            raise ValueError(f"Tych pól nie można wyczyścić (null): {', '.join(bad)}")
        return self


class SignedMoney(BaseModel):
    """Kwota wynikowa, która może być ujemna (np. przekroczenie budżetu). Tylko w odpowiedziach."""

    amount: Annotated[Decimal, Field(max_digits=13, decimal_places=2)]
    currency: Literal["PLN"] = "PLN"

    @field_serializer("amount")
    def _serialize_amount(self, v: Decimal) -> str:
        return f"{v:.2f}"


T = TypeVar("T")


class Page(BaseModel, Generic[T]):  # noqa: UP046 - Pydantic generics
    items: list[T]
    next_cursor: str | None = None


def encode_cursor(last_id: UUID) -> str:
    return base64.urlsafe_b64encode(last_id.bytes).decode().rstrip("=")


def decode_cursor(cursor: str) -> UUID:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        return UUID(bytes=base64.urlsafe_b64decode(padded))
    except (ValueError, binascii.Error) as exc:
        raise Unprocessable("Nieprawidłowy kursor.", code="pagination.invalid_cursor") from exc
