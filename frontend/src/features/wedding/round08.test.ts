import { describe, expect, it } from "vitest";

import { messageText, type MessageContext } from "../../lib/vendorMessages";
import { barWidth, monthLabel } from "./BudgetInsights";
import { giftState } from "./GiftsSection";
import { visibilityRows } from "./GuestPageView";
import { hitLink } from "./SearchView";
import { commentWhen } from "./TaskComments";

describe("runda 08", () => {
  it("plan wydatków: nazwa miesiąca i pasek", () => {
    expect(monthLabel("2028-01-01")).toBe("styczeń 2028");
    expect(barWidth(50, 200)).toBe(25);
    expect(barWidth(10, 0)).toBe(0);
  });

  it("lista prezentów: stan dla pary", () => {
    expect(giftState({ kind: "fund", reserved: false, reserved_by: null })).toMatch(/^fundusz/);
    expect(giftState({ kind: "item", reserved: false, reserved_by: null })).toBe("wolne");
    expect(giftState({ kind: "item", reserved: true, reserved_by: "Nowakowie" })).toBe("wybrali: Nowakowie");
  });

  it("strona gościa: co widać", () => {
    const rows = visibilityRows({
      info_published: true,
      show_menu: false,
      song_requests: true,
      gifts_enabled: false,
      runs_shown: 2,
      show_tables: false,
      wishes_enabled: true,
      announcement: null,
      announcement_at: null,
      announcement_emailed_at: null,
      households_with_email: 0,
      households: 3,
    });
    expect(rows.find((r) => r.label.startsWith("Kursy"))?.state).toBe("2 w RSVP");
    expect(rows.filter((r) => r.on).length).toBe(4);
  });

  it("wyszukiwarka: dokąd prowadzi wynik", () => {
    expect(hitLink("w1", { kind: "task", id: "t1", title: "X", subtitle: "zadanie" })).toBe("/w/w1/plan?zadanie=t1");
    expect(hitLink("w1", { kind: "guest", id: "h1", title: "Ola", subtitle: "Kowalscy & syn" })).toBe("/w/w1/goscie?q=Kowalscy%20%26%20syn");
  });

  it("komentarz: dzień i godzina w czasie polskim", () => {
    expect(commentWhen("2026-10-22T12:05:00Z")).toBe("22.10, 14:05");
  });

  it("wiadomość do sali z danymi wesela", () => {
    const ctx: MessageContext = { vendorName: "Dworek", category: "venue", weddingDate: "17 czerwca 2028", city: "Kraków", guests: 120, ceremony: "kościelny", signature: "Ola i Jan" };
    const text = messageText("inquiry", ctx);
    expect(text).toContain("ślub kościelny i wesele: 17 czerwca 2028 w okolicy: Kraków");
    expect(text).toContain("dla ok. 120 gości");
    expect(text.endsWith("Ola i Jan")).toBe(true);
    expect(messageText("booking", { ...ctx, weddingDate: null })).toContain("[data ślubu]");
  });
});
