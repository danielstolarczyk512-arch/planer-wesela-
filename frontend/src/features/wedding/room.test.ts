import { describe, expect, it } from "vitest";

import { defaultPositions, tableSize } from "./RoomLayout";
import type { SeatingTable } from "./data";

const table = (over: Partial<SeatingTable>): SeatingTable =>
  ({ id: "t", name: "Stół", kind: "regular", shape: "round", capacity: 10, pos_x: null, pos_y: null, rotation: 0, guests: [], free_seats: 10, ...over }) as SeatingTable;

describe("układ sali", () => {
  it("rozmiar stołu z liczby miejsc (ok. 60 cm na osobę)", () => {
    expect(tableSize(table({ capacity: 10 })).w).toBeCloseTo(1.91, 1);
    expect(tableSize(table({ capacity: 2 })).w).toBe(1.2); // minimum
    expect(tableSize(table({ shape: "rectangular", capacity: 8 }))).toEqual({ w: 2.4, h: 0.9 });
  });

  it("stoły bez pozycji dostają siatkę w granicach sali; ustawione zostają", () => {
    const tables = [table({ id: "a" }), table({ id: "b" }), table({ id: "c", pos_x: 5, pos_y: 5 })];
    const pos = defaultPositions(tables, { width_m: 7, length_m: 10 });
    expect([...pos.keys()]).toEqual(["a", "b"]);
    for (const p of pos.values()) {
      expect(p.x).toBeLessThanOrEqual(6);
      expect(p.y).toBeLessThanOrEqual(9);
    }
    expect(pos.get("a")!.x).not.toBe(pos.get("b")!.x);
  });

  it("w sali 20 × 12 m stoły stoją wokół parkietu, z dala od ścian; para młoda na środku", () => {
    const tables = [table({ id: "h", kind: "head", capacity: 8 }), ...Array.from({ length: 8 }, (_, i) => table({ id: `t${i}` }))];
    const pos = defaultPositions(tables, { width_m: 20, length_m: 12 });
    expect(pos.get("h")!.x).toBe(10);
    for (const [id, p] of pos) {
      expect(p.x).toBeGreaterThan(1.8);
      expect(p.x).toBeLessThan(18.2);
      if (id === "h") continue;
      // środek poza parkietem (7,3–12,7 m w poziomie)
      expect(p.x < 7.3 || p.x > 12.7).toBe(true);
    }
  });
});

describe("zdjęcia z iPhone'a (HEIC)", () => {
  it("rozpoznaje pliki HEIC/HEIF po nazwie", async () => {
    const { isHeicName } = await import("./Documents");
    expect(isHeicName("IMG_0001.HEIC")).toBe(true);
    expect(isHeicName("zdjecie.heif")).toBe(true);
    expect(isHeicName("oferta.pdf")).toBe(false);
    expect(isHeicName("heic.jpg")).toBe(false);
  });
});
