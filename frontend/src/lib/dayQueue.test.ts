import { beforeEach, describe, expect, it } from "vitest";

import { applyQueue, canSendSafely, clearQueues, enqueueShift, readQueue, removeShift } from "./dayQueue";

const at = (hhmm: string) => `2028-06-17T${hhmm}:00.000Z`;
const items = [
  { id: "a", starts_at: at("13:00"), ends_at: at("14:00") },
  { id: "b", starts_at: at("15:00"), ends_at: at("15:30") },
  { id: "c", starts_at: at("18:00"), ends_at: at("18:10") },
];

describe("kolejka przesunięć bez sieci", () => {
  beforeEach(() => localStorage.clear());

  it("przesuwa punkt i wszystko później; kolejne przesunięcia na wyniku poprzednich", () => {
    const q1 = enqueueShift("w", { from_item_id: "b", from_title: "Obiad", minutes: 15, base_starts_at: at("15:00") });
    expect(applyQueue(items, q1).map((i) => i.starts_at)).toEqual([at("13:00"), at("15:15"), at("18:15")]);
    const q2 = enqueueShift("w", { from_item_id: "c", from_title: "Tort", minutes: -10, base_starts_at: at("18:15") });
    const shifted = applyQueue(items, q2);
    expect(shifted.map((i) => i.starts_at)).toEqual([at("13:00"), at("15:15"), at("18:05")]);
    expect(shifted[2]!.ends_at).toBe(at("18:15")); // czas trwania zachowany
  });

  it("wysyłka bez pytania tylko przy niezmienionej godzinie na serwerze", () => {
    const [q] = enqueueShift("w", { from_item_id: "b", from_title: "Obiad", minutes: 15, base_starts_at: at("15:00") });
    expect(canSendSafely(q!, items)).toBe(true);
    const movedByOthers = items.map((i) => (i.id === "b" ? { ...i, starts_at: at("15:30") } : i));
    expect(canSendSafely(q!, movedByOthers)).toBe(false);
    expect(canSendSafely(q!, items.filter((i) => i.id !== "b"))).toBe(false); // punkt usunięty
  });

  it("usuwanie, osobne wesela i czyszczenie przy wylogowaniu", () => {
    const [q] = enqueueShift("w1", { from_item_id: "a", from_title: "A", minutes: 15, base_starts_at: at("13:00") });
    enqueueShift("w2", { from_item_id: "a", from_title: "A", minutes: 30, base_starts_at: at("13:00") });
    expect(removeShift("w1", q!.id)).toEqual([]);
    expect(readQueue("w2")).toHaveLength(1);
    localStorage.setItem("inne", "zostaje");
    clearQueues();
    expect(readQueue("w2")).toEqual([]);
    expect(localStorage.getItem("inne")).toBe("zostaje");
  });
});
