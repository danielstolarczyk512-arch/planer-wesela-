/** Menu z alergenami — etykiety wspólne dla ekranu pary i strony gościa (bez zależności od ekranów). */
import type { components } from "../api/schema";

export type Course = components["schemas"]["DishOut"]["course"];
export type Allergen = components["schemas"]["DishOut"]["allergens"][number];

export const COURSE_LABELS: Record<Course, string> = {
  starter: "Przystawka",
  soup: "Zupa",
  main: "Danie główne",
  dessert: "Deser",
  cake: "Tort",
  hot: "Danie gorące (wieczorem)",
  cold: "Zimna płyta",
  other: "Inne",
};

const COURSE_LABELS_EN: Record<Course, string> = {
  starter: "Starter",
  soup: "Soup",
  main: "Main course",
  dessert: "Dessert",
  cake: "Wedding cake",
  hot: "Late-night hot dish",
  cold: "Cold buffet",
  other: "Other",
};

export function courseLabel(c: Course, lang: "pl" | "en" = "pl"): string {
  return (lang === "pl" ? COURSE_LABELS : COURSE_LABELS_EN)[c];
}

/** 14 alergenów z załącznika II rozporządzenia UE 1169/2011 (nazwy skrócone). */
export const ALLERGEN_LABELS: Record<Allergen, string> = {
  gluten: "gluten",
  crustaceans: "skorupiaki",
  eggs: "jaja",
  fish: "ryby",
  peanuts: "orzeszki ziemne",
  soy: "soja",
  milk: "mleko",
  nuts: "orzechy",
  celery: "seler",
  mustard: "gorczyca",
  sesame: "sezam",
  sulphites: "siarczyny",
  lupin: "łubin",
  molluscs: "mięczaki",
};

const ALLERGEN_LABELS_EN: Record<Allergen, string> = {
  gluten: "gluten",
  crustaceans: "crustaceans",
  eggs: "eggs",
  fish: "fish",
  peanuts: "peanuts",
  soy: "soy",
  milk: "milk",
  nuts: "nuts",
  celery: "celery",
  mustard: "mustard",
  sesame: "sesame",
  sulphites: "sulphites",
  lupin: "lupin",
  molluscs: "molluscs",
};

const TAGS = {
  pl: { vegan: "wegańskie", vegetarian: "wegetariańskie", glutenFree: "bez glutenu", allergens: "alergeny" },
  en: { vegan: "vegan", vegetarian: "vegetarian", glutenFree: "gluten-free", allergens: "allergens" },
};

/** Oznaczenia dania: dieta i lista alergenów („alergeny: gluten, mleko”). */
export function dishTags(d: { vegan: boolean; vegetarian: boolean; gluten_free: boolean; allergens: Allergen[] }, lang: "pl" | "en" = "pl"): string[] {
  const t = TAGS[lang];
  const labels = lang === "pl" ? ALLERGEN_LABELS : ALLERGEN_LABELS_EN;
  const tags: string[] = [];
  if (d.vegan) tags.push(t.vegan);
  else if (d.vegetarian) tags.push(t.vegetarian);
  if (d.gluten_free) tags.push(t.glutenFree);
  if (d.allergens.length) tags.push(`${t.allergens}: ${d.allergens.map((a) => labels[a]).join(", ")}`);
  return tags;
}
