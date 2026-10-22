import { describe, expect, it } from "vitest";

import { courseLabel, dishTags } from "./menu";

describe("menu", () => {
  it("opisuje dietę i alergeny dania", () => {
    expect(dishTags({ vegan: true, vegetarian: true, gluten_free: true, allergens: [] })).toEqual(["wegańskie", "bez glutenu"]);
    expect(dishTags({ vegan: false, vegetarian: false, gluten_free: false, allergens: ["gluten", "milk"] })).toEqual(["alergeny: gluten, mleko"]);
    expect(dishTags({ vegan: false, vegetarian: true, gluten_free: true, allergens: ["eggs"] }, "en")).toEqual([
      "vegetarian",
      "gluten-free",
      "allergens: eggs",
    ]);
  });
  it("nazywa dania menu po polsku i angielsku", () => {
    expect(courseLabel("main")).toBe("Danie główne");
    expect(courseLabel("main", "en")).toBe("Main course");
  });
});
