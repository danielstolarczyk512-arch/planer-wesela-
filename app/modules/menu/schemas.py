from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.schemas import PatchModel

Course = Literal["starter", "soup", "main", "dessert", "cake", "hot", "cold", "other"]
Allergen = Literal[
    "gluten",
    "crustaceans",
    "eggs",
    "fish",
    "peanuts",
    "soy",
    "milk",
    "nuts",
    "celery",
    "mustard",
    "sesame",
    "sulphites",
    "lupin",
    "molluscs",
]


class DishIn(BaseModel):
    course: Course
    name: str = Field(min_length=1, max_length=200, examples=["Rosół z makaronem"])
    description: str | None = Field(default=None, max_length=300)
    allergens: list[Allergen] = Field(
        default_factory=list,
        max_length=14,
        description="Alergeny z załącznika II rozporządzenia UE 1169/2011 (wg informacji sali)",
    )
    vegetarian: bool = False
    vegan: bool = Field(default=False, description="Wegańskie jest też wegetariańskie")


class DishUpdate(PatchModel):
    NOT_NULL = ("course", "name", "allergens", "vegetarian", "vegan")

    course: Course | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=300)
    allergens: list[Allergen] | None = Field(default=None, max_length=14)
    vegetarian: bool | None = None
    vegan: bool | None = None


class DishOut(BaseModel):
    id: UUID
    course: Course
    name: str
    description: str | None
    allergens: list[Allergen]
    vegetarian: bool
    vegan: bool
    gluten_free: bool = Field(description="Bez glutenu wśród alergenów")
    version: int


class DietCounts(BaseModel):
    vegetarian: int
    vegan: int
    gluten_free: int


class MenuOverview(BaseModel):
    dishes: list[DishOut]
    diets: DietCounts = Field(description="Goście z dietą (bez tych, którzy odmówili)")
    warnings: list[str] = Field(description="Dania menu bez opcji dla diety gości")
    show_to_guests: bool


class ShowIn(BaseModel):
    enabled: bool


class GuestDish(BaseModel):
    course: Course
    name: str
    description: str | None
    allergens: list[Allergen]
    vegetarian: bool
    vegan: bool
    gluten_free: bool
