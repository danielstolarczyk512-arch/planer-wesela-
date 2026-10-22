import { parseDate, Time } from "@internationalized/date";
import { describe, expect, it } from "vitest";

import { seatsText, toInstant } from "./LogisticsView";
import { activeTab } from "./WeddingShell";

describe("transport i noclegi", () => {
  it("opisuje zajętość kursu", () => {
    expect(seatsText({ taken: 12, capacity: 50, over: 0 })).toBe("12/50 miejsc");
    expect(seatsText({ taken: 53, capacity: 50, over: 3 })).toBe("Przepełniony o 3 (53/50)");
  });

  it("zamienia godzinę w czasie polskim na moment (czas letni)", () => {
    expect(toInstant(parseDate("2028-07-01"), new Time(23, 30))).toBe("2028-07-01T21:30:00.000Z");
  });

  it("strona należy do zakładki Goście", () => {
    expect(activeTab("logistyka")).toBe("goscie");
  });
});
