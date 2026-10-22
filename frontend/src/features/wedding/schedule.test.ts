import { parseDate, Time } from "@internationalized/date";
import { describe, expect, it } from "vitest";

import { eventWhen } from "../../lib/format";
import { dayOf, fromInstant, timeRange, toInstant } from "./ScheduleView";

describe("harmonogram: czas polski niezależnie od strefy urządzenia", () => {
  it("godzina z formularza → moment UTC (lato +2, zima +1)", () => {
    expect(toInstant(parseDate("2028-07-01"), new Time(15, 0))).toBe("2028-07-01T13:00:00.000Z");
    expect(toInstant(parseDate("2028-01-15"), new Time(15, 0))).toBe("2028-01-15T14:00:00.000Z");
  });

  it("moment z API → dzień i godzina w Polsce", () => {
    const { day, time } = fromInstant("2028-07-01T22:30:00+00:00");
    expect(day.toString()).toBe("2028-07-02");
    expect(`${time.hour}:${time.minute}`).toBe("0:30");
  });

  it("punkty po północy (do 6:00) należą do tej samej doby weselnej", () => {
    expect(dayOf("2028-07-01T22:30:00Z")).toBe("2028-07-01"); // 0:30 w nocy
    expect(dayOf("2028-07-02T03:59:00Z")).toBe("2028-07-01"); // 5:59
    expect(dayOf("2028-07-02T04:00:00Z")).toBe("2028-07-02"); // 6:00 — poprawiny
  });

  it("zakres godzin", () => {
    expect(timeRange({ starts_at: "2028-07-01T13:00:00Z", ends_at: "2028-07-01T14:00:00Z", duration_minutes: 60 })).toBe(
      "15:00–16:00",
    );
    expect(timeRange({ starts_at: "2028-07-01T13:00:00Z", ends_at: "2028-07-01T13:00:00Z", duration_minutes: 0 })).toBe("15:00");
  });

  it("RSVP: termin wydarzenia po polsku", () => {
    expect(eventWhen("2028-07-01T15:00:00+02:00")).toBe("1 lipca 2028, godz. 15:00");
    expect(eventWhen(null)).toBeNull();
  });
});

describe("plan stołów", () => {
  it("zapełnienie stołu i przepełnienie", async () => {
    const { fillLabel } = await import("./SeatingView");
    expect(fillLabel({ capacity: 10, free_seats: 2 })).toBe("8 z 10");
    expect(fillLabel({ capacity: 10, free_seats: -1 })).toBe("1 osoba za dużo");
    expect(fillLabel({ capacity: 10, free_seats: -3 })).toBe("3 osoby za dużo");
  });
});

describe("oferty", () => {
  it("cena pozycji po polsku", async () => {
    const { priceLabel } = await import("./OfferView");
    expect(priceLabel({ kind: "per_guest", amount: "250.00", included: false, quantity: null })).toMatch(/^250\szł za osobę$/);
    expect(priceLabel({ kind: "percent", amount: "10.00", included: false, quantity: null })).toBe("10%");
    expect(priceLabel({ kind: "per_hour", amount: "500.00", included: false, quantity: "3.00" })).toMatch(/^500\szł za godzinę × 3$/);
    expect(priceLabel({ kind: "fixed", amount: null, included: true, quantity: null })).toBe("W cenie");
  });
});
