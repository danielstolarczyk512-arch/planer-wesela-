import { describe, expect, it } from "vitest";

import { reminderText } from "./AfterWeddingView";
import { activeTab } from "./WeddingShell";

describe("po weselu", () => {
  it("składa uprzejme przypomnienie dla usługodawcy", () => {
    expect(reminderText({ title: "Zdjęcia — galeria", due_on: "2028-07-15", vendor_name: "Foto Jan" }, "Ania i Tomek")).toBe(
      "Dzień dobry, Foto Jan! Piszemy w sprawie: Zdjęcia — galeria. Zgodnie z umową termin minął 15 lipca 2028. Czy możemy prosić o informację, kiedy możemy się spodziewać? Dziękujemy i pozdrawiamy, Ania i Tomek",
    );
    expect(reminderText({ title: "Film", due_on: null, vendor_name: null }, "A")).toMatch(/^Dzień dobry! Piszemy w sprawie: Film\. Czy/);
  });

  it("strona należy do zakładki Więcej", () => {
    expect(activeTab("po-weselu")).toBe("wiecej");
  });
});
