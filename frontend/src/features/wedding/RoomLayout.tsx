/**
 * Układ sali: stoły i elementy stałe (parkiet, scena, bar…) na planie w metrach.
 * Przeciąganie myszą/palcem to wygoda; pełna obsługa jest też z klawiatury i czytnika:
 * wybór stołu z listy i przyciski „w lewo/prawo/w górę/w dół” oraz obrót.
 * Zmiany trafiają do szkicu i zapisują się przyciskiem „Zapisz układ”.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Pencil, RotateCw } from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { TextField } from "../../components/Field";
import { Select } from "../../components/Select";
import { Card, Notice } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { keys, type SeatingPlan, type SeatingTable } from "./data";
import { ifMatch, saveErrorMessage } from "./mutations";

type Room = components["schemas"]["RoomOut"];
type RoomItem = components["schemas"]["RoomItem"];
type ItemKind = RoomItem["kind"];
interface Pos {
  x: number;
  y: number;
  rotation: number;
}

export const ITEM_LABEL: Record<ItemKind, string> = {
  dance_floor: "Parkiet",
  stage: "Scena / zespół",
  bar: "Bar",
  entrance: "Wejście",
  buffet: "Bufet",
  other: "Inne",
};
const ITEM_SIZE: Record<ItemKind, [number, number]> = {
  dance_floor: [6, 5],
  stage: [5, 3],
  bar: [3, 1.5],
  entrance: [2, 0.6],
  buffet: [4, 1.5],
  other: [2, 2],
};
const STEP = 0.5;
const SHAPE_LABEL: Record<string, string> = { round: "okrągły", rectangular: "prostokątny", square: "kwadratowy" };

/** Promień (okrągły) albo połowa boku stołu w metrach — z liczby miejsc (ok. 60 cm na osobę). */
export function tableSize(t: Pick<SeatingTable, "shape" | "capacity"> & { kind?: string }): { w: number; h: number } {
  if (t.shape === "round") {
    // Stół pary młodej jest na planie większy (miejsce na napis i wieniec).
    const d = Math.max(t.kind === "head" ? 1.9 : 1.2, (t.capacity * 0.6) / Math.PI);
    return { w: d, h: d };
  }
  if (t.shape === "square") {
    const side = Math.max(t.kind === "head" ? 2.2 : 1.2, Math.ceil(t.capacity / 4) * 0.6);
    return { w: side, h: side };
  }
  return { w: Math.max(1.2, Math.ceil(t.capacity / 2) * 0.6), h: 0.9 };
}

/** Granice podłogi (bez ścian i ozdób) i parkietu na grafice tła sali — ułamki szerokości i długości. */
const FLOOR = { x0: 0.09, x1: 0.91, y0: 0.17, y1: 0.87 };
const DANCE = { x0: 0.366, x1: 0.633, y0: 0.355, y1: 0.723 };

const round2 = (v: number) => Math.round(v * 100) / 100;

/** Środki rozłożone równo na odcinku [a, b] co najmniej co `step` (pusty, gdy odcinek za krótki). */
function spread(a: number, b: number, step: number): number[] {
  if (b < a) return [];
  const n = Math.floor((b - a) / step + 1e-9) + 1;
  return n === 1 ? [(a + b) / 2] : Array.from({ length: n }, (_, i) => a + (i * (b - a)) / (n - 1));
}

/**
 * Domyślne rozmieszczenie stołów bez pozycji: wokół parkietu (z lewej i z prawej), z dala od ścian;
 * stół pary młodej na środku nad parkietem. Gdy sala jest za mała na takie ustawienie,
 * pozostałe stoły trafiają do zwykłej siatki.
 */
export function defaultPositions(tables: SeatingTable[], room: Pick<Room, "width_m" | "length_m">): Map<string, Pos> {
  const out = new Map<string, Pos>();
  const loose = tables.filter((t) => t.pos_x == null || t.pos_y == null);
  if (loose.length === 0) return out;
  const W = room.width_m;
  const L = room.length_m;
  // Promień stołu razem z krzesłami (największego z ustawianych) i odstęp między środkami.
  const R = Math.max(...loose.map((t) => Math.max(tableSize(t).w, tableSize(t).h) / 2 + 0.35));
  const step = 2 * R + 0.3;
  const fx0 = W * FLOOR.x0 + R;
  const fx1 = W * FLOOR.x1 - R;
  const fy0 = L * FLOOR.y0 + R;
  const fy1 = L * FLOOR.y1 - R;
  const rows = spread(fy0, fy1, step);
  const cols = [...spread(fx0, W * DANCE.x0 - R, step), ...spread(W * DANCE.x1 + R, fx1, step)];
  // Najpierw rząd przy górnej i przy dolnej ścianie (symetrycznie), potem środkowe.
  const rowOrder = rows.length > 2 ? [rows[0]!, rows[rows.length - 1]!, ...rows.slice(1, -1)] : rows;
  const slots = rowOrder.flatMap((y) => cols.map((x) => ({ x, y })));
  const headSlot = fy0 <= fy1 ? { x: W / 2, y: Math.max(fy0, L * DANCE.y0 - R) } : null;

  const rest: SeatingTable[] = [];
  let headUsed = false;
  for (const t of [...loose.filter((t) => t.kind === "head"), ...loose.filter((t) => t.kind !== "head")]) {
    let slot: { x: number; y: number } | undefined;
    if (t.kind === "head" && headSlot && !headUsed) {
      headUsed = true;
      slot = headSlot;
    } else {
      slot = slots.shift();
    }
    if (slot) out.set(t.id, { x: round2(slot.x), y: round2(slot.y), rotation: 0 });
    else rest.push(t);
  }
  // Za mało miejsca wokół parkietu: zwykła siatka w dolnej części sali.
  const gridCols = Math.max(1, Math.floor(W / 3.5));
  rest.forEach((t, i) => {
    out.set(t.id, {
      x: Math.min(W - 1, 1.75 + (i % gridCols) * 3.5),
      y: Math.min(L - 1, L * 0.45 + Math.floor(i / gridCols) * 3),
      rotation: 0,
    });
  });
  // Kolejność jak na liście stołów (wydruk i testy czytają mapę po kolei).
  return new Map(loose.map((t) => [t.id, out.get(t.id)!]));
}

/** Krzesła tuż przy stole (w metrach, względem środka; `rot` — obrót w stopniach, oparcie na zewnątrz). */
export function chairPositions(t: Pick<SeatingTable, "shape" | "capacity"> & { kind?: string }): { x: number; y: number; rot: number }[] {
  const { w, h } = tableSize(t);
  const n = Math.min(Math.max(t.capacity, 0), 40);
  const out: { x: number; y: number; rot: number }[] = [];
  const gap = 0.1;
  if (t.shape === "round") {
    const r = w / 2 + gap;
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 - Math.PI / 2;
      out.push({ x: Math.cos(a) * r, y: Math.sin(a) * r, rot: (a * 180) / Math.PI + 90 });
    }
    return out;
  }
  const sides = t.shape === "square" ? 4 : 2;
  const per = [0, 1, 2, 3].map((i) => (i < sides ? Math.floor(n / sides) + (i < n % sides ? 1 : 0) : 0));
  const spread = (count: number, len: number) => Array.from({ length: count }, (_, i) => ((i + 0.5) / count - 0.5) * len * 0.9);
  spread(per[0] ?? 0, w).forEach((x) => out.push({ x, y: -h / 2 - gap, rot: 0 }));
  spread(per[1] ?? 0, w).forEach((x) => out.push({ x, y: h / 2 + gap, rot: 180 }));
  spread(per[2] ?? 0, h).forEach((y) => out.push({ x: -w / 2 - gap, y, rot: 270 }));
  spread(per[3] ?? 0, h).forEach((y) => out.push({ x: w / 2 + gap, y, rot: 90 }));
  return out;
}

/**
 * Grafiki stołów (okrągły i kwadratowy; zwykły i pary młodej) z miejscem na nazwę.
 * cx/cy — środek blatu jako ułamek boku obrazka, body — szerokość blatu jako ułamek boku,
 * label — przesunięcie napisu od środka blatu (w szerokościach blatu).
 * Stoły prostokątne rysujemy wektorowo (grafika kwadratowa by się zniekształciła).
 */
const TABLE_ART = {
  "regular-round": { file: "stol-goscie-okragly", cx: 0.503, cy: 0.499, body: 0.73, label: 0.36 },
  "regular-square": { file: "stol-goscie-kwadrat", cx: 0.498, cy: 0.495, body: 0.65, label: 0.34 },
  "head-round": { file: "stol-mlodych-okragly", cx: 0.498, cy: 0.603, body: 0.777, label: 0.13 },
  "head-square": { file: "stol-mlodych-kwadrat", cx: 0.498, cy: 0.492, body: 0.65, label: 0.33 },
} as const;

function tableArt(t: Pick<SeatingTable, "shape" | "kind">) {
  if (t.shape === "rectangular") return null;
  return TABLE_ART[`${t.kind === "head" ? "head" : "regular"}-${t.shape}`];
}

/** Nazwa stołu pary młodej w dwóch wierszach („Stół pary / młodej”). */
function headLines(name: string): string[] {
  const words = name.split(" ");
  if (words.length < 3) return [name];
  const cut = Math.ceil(words.length / 2);
  return [words.slice(0, cut).join(" "), words.slice(cut).join(" ")];
}

const MEDIA = "/media/plan-stolow";

const clamp = (v: number, min: number, max: number) => Math.min(max, Math.max(min, Math.round(v * 2) / 2));

export function RoomLayout({
  weddingId,
  plan,
  canWrite,
  onEditTable,
}: {
  weddingId: string;
  plan: SeatingPlan;
  canWrite: boolean;
  onEditTable?: (id: string) => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const room = plan.room;
  const roomItems = room.items ?? [];
  const [draft, setDraft] = useState<Map<string, Pos>>(new Map());
  const [selected, setSelected] = useState<string>(plan.tables[0]?.id ?? "");
  const [error, setError] = useState<string | null>(null);
  const [editingRoom, setEditingRoom] = useState(false);
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<{ id: string; dx: number; dy: number } | null>(null);
  const defaults = useMemo(() => defaultPositions(plan.tables, room), [plan.tables, room]);

  const posOf = (t: SeatingTable): Pos =>
    draft.get(t.id) ?? (t.pos_x != null && t.pos_y != null ? { x: t.pos_x, y: t.pos_y, rotation: t.rotation } : defaults.get(t.id)!);
  const placedCount = plan.tables.filter((t) => t.pos_x != null && t.pos_y != null).length;
  const dirty = draft.size > 0;

  const move = (id: string, change: Partial<Pos>) => {
    const t = plan.tables.find((x) => x.id === id);
    if (!t) return;
    const cur = posOf(t);
    setDraft((d) =>
      new Map(d).set(id, {
        x: clamp(change.x ?? cur.x, 0, room.width_m),
        y: clamp(change.y ?? cur.y, 0, room.length_m),
        rotation: ((change.rotation ?? cur.rotation) + 360) % 360,
      }),
    );
  };

  const save = useMutation({
    mutationFn: async () => {
      // Kolejno (każdy stół ma własną wersję); także stoły ustawione domyślnie, gdy nie miały pozycji.
      const changed = plan.tables.filter((t) => draft.has(t.id) || t.pos_x == null || t.pos_y == null);
      for (const t of changed) {
        const p = posOf(t);
        await unwrap(
          api.PATCH("/api/v1/weddings/{wedding_id}/seating/tables/{table_id}", {
            params: { path: { wedding_id: weddingId, table_id: t.id } },
            body: { pos_x: p.x, pos_y: p.y, rotation: p.rotation },
            headers: ifMatch(t.version),
          }),
        );
      }
      return changed.length;
    },
    onSuccess: async (n) => {
      setDraft(new Map());
      setError(null);
      await queryClient.invalidateQueries({ queryKey: keys.seating(weddingId) });
      toast(n ? "Zapisano układ sali" : "Bez zmian");
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [keys.seating(weddingId)])),
  });

  // Przeciąganie: współrzędne ekranu → metry przez macierz SVG.
  const toMeters = (e: React.PointerEvent): { x: number; y: number } | null => {
    const svg = svgRef.current;
    const ctm = svg?.getScreenCTM();
    if (!svg || !ctm) return null;
    const pt = new DOMPoint(e.clientX, e.clientY).matrixTransform(ctm.inverse());
    return { x: pt.x, y: pt.y };
  };

  const sel = plan.tables.find((t) => t.id === selected);

  return (
    <section className="form-stack" aria-labelledby="room-h">
      <div className="section-head">
        <h2 id="room-h">Układ sali</h2>
        <span className="text-secondary num">
          {room.width_m} × {room.length_m} m
        </span>
      </div>
      {placedCount < plan.tables.length && (
        <p className="text-secondary">
          Stoły bez pozycji ustawiliśmy wstępnie wokół parkietu — przesuńcie je jak na sali i zapiszcie układ.
        </p>
      )}
      <Card className="form-stack room-card">
        <svg
          ref={svgRef}
          className="room-plan"
          viewBox={`0 0 ${room.width_m} ${room.length_m}`}
          role="img"
          aria-labelledby="room-plan-title"
          onPointerMove={(e) => {
            if (!drag.current) return;
            const m = toMeters(e);
            if (m) move(drag.current.id, { x: m.x - drag.current.dx, y: m.y - drag.current.dy });
          }}
          onPointerUp={() => (drag.current = null)}
          onPointerLeave={() => (drag.current = null)}
        >
          <title id="room-plan-title">
            {`Plan sali ${room.width_m} na ${room.length_m} m: ${plan.tables.length} stołów${roomItems.length ? ", " + roomItems.map((i) => i.label || ITEM_LABEL[i.kind]).join(", ") : ""}`}
          </title>
          <rect className="room-plan__floor" x={0} y={0} width={room.width_m} height={room.length_m} />
          {/* Tło sali (grafika właściciela: podłoga, ściany, kwiaty i światła) rozciągnięte na wymiar sali. */}
          <image
            className="room-plan__backdrop"
            href={`${MEDIA}/sala-tlo.webp`}
            x={0}
            y={0}
            width={room.width_m}
            height={room.length_m}
            preserveAspectRatio="none"
            aria-hidden="true"
          />
          {roomItems.map((i, n) => (
            <g key={`${i.kind}-${n}`} className={`room-plan__item room-plan__item--${i.kind}`}>
              <rect x={i.x - i.w / 2} y={i.y - i.h / 2} width={i.w} height={i.h} rx={0.2} />
              <text x={i.x} y={i.y} className="room-plan__label">
                {i.label || ITEM_LABEL[i.kind]}
              </text>
            </g>
          ))}
          {plan.tables.map((t) => {
            const p = posOf(t);
            const { w, h } = tableSize(t);
            const seated = t.capacity - t.free_seats;
            const art = tableArt(t);
            const fontSize = Math.min(t.kind === "head" ? 0.34 : 0.42, Math.max(0.28, w * 0.19));
            return (
              <g
                key={t.id}
                className={`room-plan__table${t.id === selected ? " is-selected" : ""}${t.kind === "head" ? " is-head" : ""}`}
                transform={`translate(${p.x} ${p.y}) rotate(${p.rotation})`}
                onPointerDown={(e) => {
                  if (!canWrite) return;
                  setSelected(t.id);
                  const m = toMeters(e);
                  if (m) drag.current = { id: t.id, dx: m.x - p.x, dy: m.y - p.y };
                  (e.target as Element).setPointerCapture?.(e.pointerId);
                }}
              >
                <title>{`${t.name}: ${seated} z ${t.capacity} miejsc`}</title>
                {art ? (
                  <>
                    <image
                      className="room-plan__art"
                      href={`${MEDIA}/${art.file}.webp`}
                      x={-art.cx * (w / art.body)}
                      y={-art.cy * (w / art.body)}
                      width={w / art.body}
                      height={w / art.body}
                    />
                    {t.shape === "round" ? (
                      <circle className="room-plan__outline" r={w / 2} />
                    ) : (
                      <rect className="room-plan__outline" x={-w / 2} y={-h / 2} width={w} height={h} rx={0.12} />
                    )}
                  </>
                ) : (
                  <>
                    {chairPositions(t).map((c, i) => (
                      <rect
                        key={i}
                        className="room-plan__chair"
                        x={-0.2}
                        y={-0.15}
                        width={0.4}
                        height={0.3}
                        rx={0.11}
                        transform={`translate(${c.x} ${c.y}) rotate(${c.rot})`}
                      />
                    ))}
                    <rect x={-w / 2} y={-h / 2} width={w} height={h} rx={0.1} />
                  </>
                )}
                <g transform={`rotate(${-p.rotation})`}>
                  {!art && (
                    <image
                      className="room-plan__icon"
                      href={`${MEDIA}/${t.kind === "head" ? "obraczki" : "stol-kwiaty"}.webp`}
                      x={-0.22}
                      y={-0.5}
                      width={0.44}
                      height={0.44}
                    />
                  )}
                  <text className="room-plan__label" y={art ? art.label * w : 0.25} style={{ fontSize: `${fontSize}px` }}>
                    {(t.kind === "head" ? headLines(t.name) : [t.name]).map((line, i) => (
                      <tspan key={i} x={0} dy={i === 0 ? 0 : fontSize * 1.25}>
                        {line}
                      </tspan>
                    ))}
                  </text>
                </g>
              </g>
            );
          })}
        </svg>

        {canWrite && sel && (
          <div className="form-stack room-controls">
            <Select
              label="Przesuń stół"
              options={plan.tables.map((t) => ({ id: t.id, label: t.name }))}
              value={selected}
              onChange={setSelected}
            />
            <div className="chips" role="group" aria-label={`Położenie: ${sel.name}`}>
              <Button variant="secondary" icon={<ArrowLeft aria-hidden size={18} />} onPress={() => move(sel.id, { x: posOf(sel).x - STEP })}>
                W lewo
              </Button>
              <Button variant="secondary" icon={<ArrowRight aria-hidden size={18} />} onPress={() => move(sel.id, { x: posOf(sel).x + STEP })}>
                W prawo
              </Button>
              <Button variant="secondary" icon={<ArrowUp aria-hidden size={18} />} onPress={() => move(sel.id, { y: posOf(sel).y - STEP })}>
                W górę
              </Button>
              <Button variant="secondary" icon={<ArrowDown aria-hidden size={18} />} onPress={() => move(sel.id, { y: posOf(sel).y + STEP })}>
                W dół
              </Button>
              <Button variant="secondary" icon={<RotateCw aria-hidden size={18} />} onPress={() => move(sel.id, { rotation: posOf(sel).rotation + 45 })}>
                Obróć
              </Button>
              {onEditTable && (
                <Button variant="secondary" icon={<Pencil aria-hidden size={18} />} onPress={() => onEditTable(sel.id)}>
                  Kształt i wielkość stołu
                </Button>
              )}
            </div>
            <p className="text-secondary num" aria-live="polite">
              {sel.name} ({SHAPE_LABEL[sel.shape] ?? sel.shape}, {sel.capacity} miejsc, ok. {tableSize(sel).w.toFixed(1).replace(".", ",")}
              {sel.shape === "round" ? "" : ` × ${tableSize(sel).h.toFixed(1).replace(".", ",")}`} m): {posOf(sel).x} m od lewej, {posOf(sel).y} m od góry, obrót {posOf(sel).rotation}°
            </p>
            {error && (
              <Notice tone="error" live>
                {error}
              </Notice>
            )}
            <div className="wp-sheet__actions">
              <Button variant="text" onPress={() => setEditingRoom((v) => !v)}>
                {editingRoom ? "Zamknij ustawienia sali" : "Wymiary i elementy sali"}
              </Button>
              {dirty && (
                <Button variant="secondary" onPress={() => setDraft(new Map())}>
                  Cofnij zmiany
                </Button>
              )}
              <Button pending={save.isPending} isDisabled={!dirty && placedCount === plan.tables.length} onPress={() => save.mutate()}>
                Zapisz układ
              </Button>
            </div>
          </div>
        )}
      </Card>
      {canWrite && editingRoom && <RoomEditor weddingId={weddingId} room={room} onDone={() => setEditingRoom(false)} />}
    </section>
  );
}

/** Wymiary sali i elementy stałe (parkiet, scena, bar, wejście, bufet). */
function RoomEditor({ weddingId, room, onDone }: { weddingId: string; room: Room; onDone: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [width, setWidth] = useState(String(room.width_m));
  const [length, setLength] = useState(String(room.length_m));
  const [items, setItems] = useState<RoomItem[]>(room.items ?? []);
  const [adding, setAdding] = useState<ItemKind>("dance_floor");
  const [error, setError] = useState<string | null>(null);
  const num = (v: string) => Number(v.replace(",", "."));
  const valid = (v: string) => Number.isFinite(num(v)) && num(v) >= 4 && num(v) <= 200;

  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.PUT("/api/v1/weddings/{wedding_id}/seating/room", {
          params: { path: { wedding_id: weddingId } },
          body: { width_m: num(width), length_m: num(length), items },
          headers: ifMatch(room.version),
        }),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: keys.seating(weddingId) });
      toast("Zapisano salę");
      onDone();
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [keys.seating(weddingId)])),
  });

  const shift = (n: number, dx: number, dy: number) =>
    setItems((all) =>
      all.map((it, i) =>
        i === n ? { ...it, x: clamp(it.x + dx, 0, num(width) || room.width_m), y: clamp(it.y + dy, 0, num(length) || room.length_m) } : it,
      ),
    );

  return (
    <Card className="form-stack">
      <h3>Sala</h3>
      <div className="stat-grid">
        <TextField label="Szerokość (m)" inputMode="decimal" value={width} onChange={setWidth} error={valid(width) ? null : "Od 4 do 200 m."} />
        <TextField label="Długość (m)" inputMode="decimal" value={length} onChange={setLength} error={valid(length) ? null : "Od 4 do 200 m."} />
      </div>
      {items.length > 0 && (
        <ul className="row-list">
          {items.map((it, n) => (
            <li key={`${it.kind}-${n}`} className="row room-item-row">
              <span className="row__body">
                <span className="row__title">{it.label || ITEM_LABEL[it.kind]}</span>
                <span className="text-secondary num">
                  {it.x} m / {it.y} m · {it.w} × {it.h} m
                </span>
              </span>
              <span className="chips" role="group" aria-label={`Położenie: ${it.label || ITEM_LABEL[it.kind]}`}>
                <Button variant="text" aria-label="W lewo" onPress={() => shift(n, -STEP, 0)}>
                  <ArrowLeft aria-hidden size={18} />
                </Button>
                <Button variant="text" aria-label="W prawo" onPress={() => shift(n, STEP, 0)}>
                  <ArrowRight aria-hidden size={18} />
                </Button>
                <Button variant="text" aria-label="W górę" onPress={() => shift(n, 0, -STEP)}>
                  <ArrowUp aria-hidden size={18} />
                </Button>
                <Button variant="text" aria-label="W dół" onPress={() => shift(n, 0, STEP)}>
                  <ArrowDown aria-hidden size={18} />
                </Button>
                <Button variant="text" onPress={() => setItems((all) => all.filter((_, i) => i !== n))}>
                  Usuń
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
      <div className="room-add">
        <Select
          label="Dodaj element"
          options={(Object.keys(ITEM_LABEL) as ItemKind[]).map((k) => ({ id: k, label: ITEM_LABEL[k] }))}
          value={adding}
          onChange={(v) => setAdding(v as ItemKind)}
        />
        <Button
          variant="secondary"
          isDisabled={items.length >= 30}
          onPress={() => {
            const [w, h] = ITEM_SIZE[adding];
            setItems((all) => [...all, { kind: adding, label: null, x: (num(width) || 20) / 2, y: (num(length) || 12) / 4, w, h }]);
          }}
        >
          Dodaj na plan
        </Button>
      </div>
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      {save.isError && !error && (
        <Notice tone="error" live>
          {userMessage(save.error)}
        </Notice>
      )}
      <Button isDisabled={!valid(width) || !valid(length)} pending={save.isPending} onPress={() => save.mutate()}>
        Zapisz salę
      </Button>
    </Card>
  );
}
