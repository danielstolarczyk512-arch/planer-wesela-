import { describe, expect, it } from "vitest";

import { mapLink, pace, printBreakdown } from "./InvitationsView";
import { activeTab } from "./WeddingShell";

describe("wręczanie zaproszeń", () => {
  it("liczy tempo wizyt na weekend", () => {
    expect(pace(10, 4)).toBe("Zostało 10 wizyt i 4 weekendy — ok. 3 na weekend.");
    expect(pace(1, 1)).toBe("Zostało 1 wizyta i 1 weekend — ok. 1 na weekend.");
    expect(pace(0, 5)).toBeNull();
    expect(pace(3, 0)).toMatch(/^Termin minął/);
  });

  it("link do mapy zawiera tylko miejscowość", () => {
    expect(mapLink("Nowy Sącz")).toBe("https://www.openstreetmap.org/search?query=Nowy%20S%C4%85cz");
  });

  it("strona należy do zakładki Goście", () => {
    expect(activeTab("zaproszenia")).toBe("goscie");
  });
});

describe("printBreakdown", () => {
  it("rozpisuje liczbę do drukarni", () => {
    expect(printBreakdown({ printed: 45, spare: 5, reserve: 0, total: 50 })).toBe("45 zaproszeń dla rodzin + 5 zapasu");
    expect(printBreakdown({ printed: 2, spare: 3, reserve: 1, total: 6 })).toBe("2 zaproszenia dla rodzin + 3 zapasu + 1 dla listy rezerwowej");
  });
});
