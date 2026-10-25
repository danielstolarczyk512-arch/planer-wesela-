import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pin, Plus, Sparkles } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { ApiError, userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { Checkbox, TextField } from "../../components/Field";
import { ConfirmDialog, Sheet } from "../../components/Overlay";
import { Segmented } from "../../components/Segmented";
import { Select } from "../../components/Select";
import { Card, EmptyState, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { plural } from "../../lib/format";
import {
  keys,
  useCanWrite,
  useHouseholds,
  useSeatingPlan,
  useSeatingRules,
  useWeddingId,
  type SeatingPlan,
  type SeatingTable,
} from "./data";
import { ifMatch, saveErrorMessage } from "./mutations";
import { RoomLayout } from "./RoomLayout";
import { GUEST_SECTIONS, PrintLink, SectionNav } from "./SectionNav";

type Auto = components["schemas"]["AutoResult"];
type TableKind = components["schemas"]["TableCreate"]["kind"];
type Shape = components["schemas"]["TableCreate"]["shape"];
type Issue = components["schemas"]["IssueOut"];

const KIND_LABEL: Record<TableKind, string> = { regular: "Stół", head: "Stół pary młodej", kids: "Stół dziecięcy" };
const KINDS = (Object.keys(KIND_LABEL) as TableKind[]).map((id) => ({ id, label: KIND_LABEL[id] }));
const SHAPES: { id: Shape; label: string }[] = [
  { id: "round", label: "Okrągły" },
  { id: "rectangular", label: "Prostokątny" },
  { id: "square", label: "Kwadratowy" },
];
const NO_TABLE = "__none__";

interface PersonRef {
  guest_id: string;
  name: string;
  household_id: string;
  age_group: string;
  table_id: string | null;
  locked: boolean;
}

/** Wszyscy z planu (posadzeni i bez miejsca) — do nazw w podglądzie automatu i wyboru w regułach. */
export function peopleOf(plan: SeatingPlan | undefined): Map<string, PersonRef> {
  const map = new Map<string, PersonRef>();
  for (const t of plan?.tables ?? []) {
    for (const g of t.guests) map.set(g.guest_id, { ...g, table_id: t.id });
  }
  for (const g of plan?.unassigned ?? []) map.set(g.guest_id, { ...g, table_id: null, locked: false });
  return map;
}

/** „8 z 10 miejsc” / „2 osoby za dużo”. */
export function fillLabel(t: Pick<SeatingTable, "capacity" | "free_seats">): string {
  if (t.free_seats < 0) {
    const over = -t.free_seats;
    return plural(over, { one: "# osoba za dużo", few: "# osoby za dużo", many: "# osób za dużo", other: "# osoby za dużo" });
  }
  return `${t.capacity - t.free_seats} z ${t.capacity}`;
}

export function SeatingView() {
  const id = useWeddingId();
  const plan = useSeatingPlan(id);
  const canWrite = useCanWrite(id);
  const [addingTables, setAddingTables] = useState(false);
  const [auto, setAuto] = useState(false);
  const [moving, setMoving] = useState<string | null>(null);
  const [editingTable, setEditingTable] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);
  const people = useMemo(() => peopleOf(plan.data), [plan.data]);
  const queryClient = useQueryClient();
  const toast = useToast();

  const clear = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/seating/clear", {
          params: { path: { wedding_id: id } },
          body: { include_locked: false },
        }),
      ),
    onSuccess: async () => {
      setClearing(false);
      await queryClient.invalidateQueries({ queryKey: keys.seating(id) });
      toast("Wyczyszczono plan (przypięte miejsca zostały)");
    },
  });

  const numbers = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/seating/seat-numbers", {
          params: { path: { wedding_id: id } },
          body: { keep_existing: true, dry_run: false },
        }),
      ),
    onSuccess: async (r) => {
      await queryClient.invalidateQueries({ queryKey: keys.seating(id) });
      toast(r.seats.length ? "Ponumerowano miejsca — rodziny obok siebie, dzieci przy rodzicach" : "Brak gości przy stołach");
    },
    onError: (e) => toast(`Nie ponumerowano miejsc. ${userMessage(e)}`),
  });

  const p = plan.data;
  const errors = (p?.issues ?? []).filter((i) => i.severity === "error");
  const warnings = (p?.issues ?? []).filter((i) => i.severity === "warning");

  return (
    <main className="page enter-tab" aria-labelledby="seating-h">
      <SectionNav label="Goście" sections={GUEST_SECTIONS} />
      <div className="view-head seating-head">
        <div>
          <h1 id="seating-h">Plan stołów</h1>
          {p && (
            <p className="text-secondary num seating-head__meta">
              <span>Posadzeni: {p.stats.seated}</span>
              <span>bez miejsca: {p.stats.to_seat}</span>
              <span>miejsc: {p.stats.seats}</span>
            </p>
          )}
          {p && p.stats.seated > 0 && (
            <p className="chips">
              <PrintLink kind="stoly">Plan dla sali (z dietami)</PrintLink>
              <PrintLink kind="winietki">Winietki</PrintLink>
              <PrintLink kind="sala">Plan sali</PrintLink>
            </p>
          )}
        </div>
        {canWrite && p && p.tables.length > 0 && (
          <div className="seating-head__actions">
            <Button icon={<Sparkles aria-hidden size={20} />} onPress={() => setAuto(true)}>
              Usadź automatycznie
            </Button>
            <Button variant="secondary" icon={<Plus aria-hidden size={20} />} onPress={() => setAddingTables(true)}>
              Dodaj stoły
            </Button>
          </div>
        )}
      </div>

      {plan.isPending && <Skeleton lines={8} />}
      {plan.isError && (
        <Notice tone="error" title="Nie udało się wczytać planu." live>
          {userMessage(plan.error)}
        </Notice>
      )}

      {p && p.tables.length === 0 && (
        <EmptyState
          title="Nie ma jeszcze stołów"
          action={canWrite ? <Button onPress={() => setAddingTables(true)}>Dodaj stoły</Button> : undefined}
        >
          Dodajcie stoły (np. 8 okrągłych po 10 miejsc i stół pary młodej), a potem usadźcie gości automatycznie lub ręcznie.
        </EmptyState>
      )}

      {p && p.tables.length > 0 && (
        <div className="seating-stats" role="group" aria-label="Podsumowanie planu stołów">
          <div className="seating-stat">
            <span className="seating-stat__icon">
              <img src="/media/plan-stolow/stol-kwiaty.webp" alt="" width={36} height={36} loading="lazy" />
            </span>
            <span>
              <span className="seating-stat__value num">{p.tables.length}</span>
              <span className="seating-stat__label">{plural(p.tables.length, { one: "stół", few: "stoły", many: "stołów", other: "stoły" })}</span>
            </span>
          </div>
          <div className="seating-stat">
            <span className="seating-stat__icon">
              <img src="/media/plan-stolow/goscie.webp" alt="" width={36} height={36} loading="lazy" />
            </span>
            <span>
              <span className="seating-stat__value num">{Math.max(0, p.stats.seats - p.stats.seated)}</span>
              <span className="seating-stat__label">{plural(Math.max(0, p.stats.seats - p.stats.seated), { one: "wolne miejsce", few: "wolne miejsca", many: "wolnych miejsc", other: "wolnych miejsc" })}</span>
            </span>
          </div>
          <button
            type="button"
            className={`seating-stat seating-stat--button${p.unassigned.length > 0 ? " seating-stat--warn" : ""}`}
            disabled={p.unassigned.length === 0}
            onClick={() => document.getElementById("unseated-h")?.scrollIntoView({ behavior: "smooth", block: "start" })}
          >
            <span className="seating-stat__icon">
              <img src="/media/plan-stolow/ostrzezenie.webp" alt="" width={36} height={36} loading="lazy" />
            </span>
            <span>
              <span className="seating-stat__value num">{p.unassigned.length}</span>
              <span className="seating-stat__label">{plural(p.unassigned.length, { one: "osoba bez przypisania", few: "osoby bez przypisania", many: "osób bez przypisania", other: "osoby bez przypisania" })}</span>
            </span>
          </button>
        </div>
      )}

      {p && p.tables.length > 0 && canWrite && p.stats.seated > 0 && (
        <div className="seating-actions">
          <Button variant="secondary" pending={numbers.isPending} onPress={() => numbers.mutate()}>
            Ponumeruj miejsca
          </Button>
          <Button variant="text" onPress={() => setClearing(true)}>
            Wyczyść plan
          </Button>
        </div>
      )}

      {errors.length > 0 && <IssueNotice tone="error" title="Do poprawienia" list={errors} />}
      {warnings.length > 0 && <IssueNotice tone="warning" title="Warto sprawdzić" list={warnings} />}

      {p && p.unassigned.length > 0 && (
        <section aria-labelledby="unseated-h" className="form-stack">
          <div className="section-head">
            <h2 id="unseated-h">Bez miejsca</h2>
            <span className="text-secondary num">{p.unassigned.length}</span>
          </div>
          <Card>
            <ul className="chips seating-people">
              {p.unassigned.map((g) => (
                <li key={g.guest_id}>
                  {canWrite && p.tables.length > 0 ? (
                    <AriaButton className="person-chip" onPress={() => setMoving(g.guest_id)}>
                      {g.name}
                    </AriaButton>
                  ) : (
                    <span className="person-chip">{g.name}</span>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        </section>
      )}

      {p && p.tables.length > 0 && (
        <section aria-labelledby="tables-h" className="form-stack">
          <h2 id="tables-h">Stoły</h2>
          <div className="table-grid">
            {p.tables.map((t) => (
              <Card key={t.id} className={`seating-table${t.kind === "head" ? " seating-table--head" : ""}`} aria-label={t.name}>
                {t.kind === "head" && (
                  <>
                    <img className="seating-table__corner seating-table__corner--l" src="/media/plan-stolow/naroznik.webp" alt="" loading="lazy" />
                    <img className="seating-table__corner seating-table__corner--r" src="/media/plan-stolow/naroznik.webp" alt="" loading="lazy" />
                  </>
                )}
                <div className="seating-table__top">
                  <span className="seating-table__icon">
                    <img
                      src={t.kind === "head" ? "/media/plan-stolow/obraczki.webp" : "/media/plan-stolow/stol-krzesla.webp"}
                      alt=""
                      width={32}
                      height={32}
                      loading="lazy"
                    />
                  </span>
                  <div className="seating-table__name">
                    {canWrite ? (
                      <AriaButton className="row-edit row-edit--inline" onPress={() => setEditingTable(t.id)}>
                        <span className="row__title">{t.name}</span>
                      </AriaButton>
                    ) : (
                      <span className="row__title">{t.name}</span>
                    )}
                  </div>
                  <StatusChip tone={t.free_seats < 0 ? "error" : t.free_seats === 0 ? "success" : "neutral"}>
                    <img className="seating-table__guests" src="/media/plan-stolow/goscie.webp" alt="" width={16} height={16} loading="lazy" />
                    {fillLabel(t)}
                  </StatusChip>
                </div>
                {t.kind !== "regular" && t.name !== KIND_LABEL[t.kind] && <span className="text-secondary">{KIND_LABEL[t.kind]}</span>}
                {t.guests.length === 0 ? (
                  <p className="text-secondary">Pusty</p>
                ) : (
                  <ul className="chips seating-people">
                    {t.guests.map((g) => (
                      <li key={g.guest_id}>
                        {canWrite ? (
                          <AriaButton className="person-chip" onPress={() => setMoving(g.guest_id)}>
                            {g.locked && <Pin aria-hidden size={14} />}
                            {g.seat_number != null && <span className="seat-no num">{g.seat_number}.</span>}
                            {g.name}
                            {g.locked && <span className="visually-hidden"> (przypięty)</span>}
                          </AriaButton>
                        ) : (
                          <span className="person-chip">
                            {g.seat_number != null && <span className="seat-no num">{g.seat_number}.</span>}
                            {g.name}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            ))}
          </div>
        </section>
      )}

      {p && p.tables.length > 0 && <RoomLayout weddingId={id} plan={p} canWrite={canWrite} onEditTable={setEditingTable} />}

      {p && p.tables.length > 0 && <RulesSection weddingId={id} people={people} canWrite={canWrite} />}

      <AddTablesSheet weddingId={id} count={p?.tables.length ?? 0} isOpen={addingTables} onOpenChange={setAddingTables} />
      {p && <AutoSheet weddingId={id} plan={p} people={people} isOpen={auto} onOpenChange={setAuto} />}
      <MoveSheet weddingId={id} plan={p} person={moving ? (people.get(moving) ?? null) : null} onClose={() => setMoving(null)} />
      <TableSheet
        weddingId={id}
        table={p?.tables.find((t) => t.id === editingTable) ?? null}
        onClose={() => setEditingTable(null)}
      />
      <ConfirmDialog title="Wyczyścić plan?" isOpen={clearing} onOpenChange={setClearing}>
        <p>Goście posadzeni automatycznie wrócą do listy „Bez miejsca”. Miejsca przypięte ręcznie zostaną.</p>
        <div className="wp-sheet__actions">
          <Button variant="secondary" onPress={() => setClearing(false)}>
            Anuluj
          </Button>
          <Button variant="danger" pending={clear.isPending} onPress={() => clear.mutate()}>
            Wyczyść
          </Button>
        </div>
      </ConfirmDialog>
    </main>
  );
}

function IssueNotice({ tone, title, list }: { tone: "error" | "warning"; title: string; list: Issue[] }) {
  return (
    <Notice tone={tone} title={title}>
      <ul className="conflict-list">
        {list.map((i) => (
          <li key={`${i.code}-${i.guest_ids.join("-")}-${i.table_ids.join("-")}`}>{i.message}</li>
        ))}
      </ul>
    </Notice>
  );
}

/* --------------------------------------------------------------------- stoły: dodanie */

function AddTablesSheet({
  weddingId,
  count,
  isOpen,
  onOpenChange,
}: {
  weddingId: string;
  count: number;
  isOpen: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [how, setHow] = useState("8");
  const [capacity, setCapacity] = useState("10");
  const [shape, setShape] = useState<string>("round");
  const [head, setHead] = useState(count === 0);
  const [errors, setErrors] = useState<{ how?: string; capacity?: string }>({});
  const keysRef = useRef<string[]>([]);

  const create = useMutation({
    mutationFn: async () => {
      const list: { name: string; kind: TableKind; capacity: number }[] = [];
      if (head) list.push({ name: "Stół pary młodej", kind: "head", capacity: 8 });
      for (let i = 1; i <= Number(how); i++) list.push({ name: `Stół ${count + i}`, kind: "regular", capacity: Number(capacity) });
      for (const [i, t] of list.entries()) {
        keysRef.current[i] ??= newIdempotencyKey();
        await unwrap(
          api.POST("/api/v1/weddings/{wedding_id}/seating/tables", {
            params: { path: { wedding_id: weddingId } },
            body: { ...t, shape: shape as Shape, sort_order: count + i, rotation: 0 },
            headers: { "Idempotency-Key": keysRef.current[i]! },
          }),
        );
      }
      return list.length;
    },
    onSuccess: async (n) => {
      keysRef.current = [];
      onOpenChange(false);
      await queryClient.invalidateQueries({ queryKey: keys.seating(weddingId) });
      toast(plural(n, { one: "Dodano # stół", few: "Dodano # stoły", many: "Dodano # stołów", other: "Dodano # stołu" }));
    },
  });

  return (
    <Sheet title="Dodaj stoły" isOpen={isOpen} onOpenChange={onOpenChange}>
      <Form
        className="form-stack"
        validationBehavior="aria"
        onSubmit={(e) => {
          e.preventDefault();
          const next: typeof errors = {};
          const n = Number(how);
          const c = Number(capacity);
          if (!Number.isInteger(n) || n < 0 || n > 60 || (n === 0 && !head)) next.how = "Wpisz liczbę stołów od 1 do 60.";
          if (!Number.isInteger(c) || c < 1 || c > 40) next.capacity = "Od 1 do 40 miejsc.";
          setErrors(next);
          if (next.how || next.capacity) return;
          create.mutate();
        }}
      >
        {create.isError && (
          <Notice tone="error" title="Nie dodano wszystkich stołów." live>
            {userMessage(create.error)} Spróbuj ponownie — już dodane nie zdublują się.
          </Notice>
        )}
        <div className="stat-grid">
          <TextField label="Ile stołów?" inputMode="numeric" value={how} onChange={setHow} error={errors.how} />
          <TextField label="Miejsc przy stole" inputMode="numeric" value={capacity} onChange={setCapacity} error={errors.capacity} />
        </div>
        <Select label="Kształt" options={SHAPES} value={shape} onChange={setShape} />
        <Checkbox isSelected={head} onChange={setHead}>
          Dodaj też stół pary młodej (8 miejsc)
        </Checkbox>
        <Button type="submit" block pending={create.isPending}>
          Dodaj
        </Button>
      </Form>
    </Sheet>
  );
}

/* -------------------------------------------------------------------- stół: edycja */

function TableSheet({ weddingId, table, onClose }: { weddingId: string; table: SeatingTable | null; onClose: () => void }) {
  return (
    <Sheet title="Stół" isOpen={!!table} onOpenChange={(o) => !o && onClose()}>
      {table && <TableForm key={`${table.id}-${table.version}`} weddingId={weddingId} table={table} onClose={onClose} />}
    </Sheet>
  );
}

function TableForm({ weddingId, table: t, onClose }: { weddingId: string; table: SeatingTable; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState(t.name);
  const [capacity, setCapacity] = useState(String(t.capacity));
  const [kind, setKind] = useState<string>(t.kind);
  const [shape, setShape] = useState<string>(t.shape);
  const [errors, setErrors] = useState<{ name?: string; capacity?: string }>({});
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const refresh = () => queryClient.invalidateQueries({ queryKey: keys.seating(weddingId) });

  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/seating/tables/{table_id}", {
          params: { path: { wedding_id: weddingId, table_id: t.id } },
          body: { name: name.trim(), capacity: Number(capacity), kind: kind as TableKind, shape: shape as Shape },
          headers: ifMatch(t.version),
        }),
      ),
    onSuccess: async () => {
      await refresh();
      onClose();
      toast("Zapisano stół");
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [keys.seating(weddingId)])),
  });

  const remove = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE("/api/v1/weddings/{wedding_id}/seating/tables/{table_id}", {
          params: { path: { wedding_id: weddingId, table_id: t.id } },
        }),
      ),
    onSuccess: async () => {
      setConfirmDelete(false);
      await refresh();
      onClose();
      toast(`Usunięto „${t.name}”`);
    },
    onError: (e) => {
      setConfirmDelete(false);
      setError(`Nie usunięto. ${userMessage(e)}`);
    },
  });

  return (
    <>
      <Form
        className="form-stack"
        validationBehavior="aria"
        onSubmit={(e) => {
          e.preventDefault();
          const next: typeof errors = {};
          const c = Number(capacity);
          if (!name.trim()) next.name = "Wpisz nazwę, np. Stół 3.";
          if (!Number.isInteger(c) || c < 1 || c > 40) next.capacity = "Od 1 do 40 miejsc.";
          setErrors(next);
          if (next.name || next.capacity) return;
          save.mutate();
        }}
      >
        {error && (
          <Notice tone="error" live>
            {error}
          </Notice>
        )}
        <TextField label="Nazwa" value={name} onChange={setName} error={errors.name} isRequired />
        <TextField label="Miejsc" inputMode="numeric" value={capacity} onChange={setCapacity} error={errors.capacity} />
        <Select label="Rodzaj" options={KINDS} value={kind} onChange={setKind} />
        <Select label="Kształt" options={SHAPES} value={shape} onChange={setShape} />
        <Button type="submit" block pending={save.isPending}>
          Zapisz
        </Button>
        <Button variant="text" onPress={() => setConfirmDelete(true)}>
          Usuń stół
        </Button>
      </Form>
      <ConfirmDialog title="Usunąć stół?" isOpen={confirmDelete} onOpenChange={setConfirmDelete}>
        <p>
          „{t.name}” zniknie z planu.{" "}
          {t.guests.length > 0 &&
            plural(t.guests.length, {
              one: "# osoba wróci do listy „Bez miejsca”.",
              few: "# osoby wrócą do listy „Bez miejsca”.",
              many: "# osób wróci do listy „Bez miejsca”.",
              other: "# osoby wrócą do listy „Bez miejsca”.",
            })}
        </p>
        <div className="wp-sheet__actions">
          <Button variant="secondary" onPress={() => setConfirmDelete(false)}>
            Anuluj
          </Button>
          <Button variant="danger" pending={remove.isPending} onPress={() => remove.mutate()}>
            Usuń
          </Button>
        </div>
      </ConfirmDialog>
    </>
  );
}

/* ----------------------------------------------------------------- gość: przeniesienie */

function MoveSheet({
  weddingId,
  plan,
  person,
  onClose,
}: {
  weddingId: string;
  plan: SeatingPlan | undefined;
  person: PersonRef | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);
  const done = async (message: string) => {
    setError(null);
    await queryClient.invalidateQueries({ queryKey: keys.seating(weddingId) });
    onClose();
    toast(message);
  };

  const seat = useMutation({
    mutationFn: (tableId: string) =>
      tableId === NO_TABLE
        ? unwrap(
            api.DELETE("/api/v1/weddings/{wedding_id}/seating/guests/{guest_id}", {
              params: { path: { wedding_id: weddingId, guest_id: person!.guest_id } },
            }),
          )
        : unwrap(
            api.PUT("/api/v1/weddings/{wedding_id}/seating/guests/{guest_id}", {
              params: { path: { wedding_id: weddingId, guest_id: person!.guest_id } },
              body: { table_id: tableId },
            }),
          ),
    onSuccess: (_r, tableId) =>
      done(
        tableId === NO_TABLE
          ? `${person!.name}: bez miejsca`
          : `${person!.name} → ${plan?.tables.find((t) => t.id === tableId)?.name ?? "stół"}`,
      ),
    onError: (e) => setError(`Nie zapisano. ${userMessage(e)}`),
  });

  const unpin = useMutation({
    mutationFn: () =>
      unwrap(
        api.PUT("/api/v1/weddings/{wedding_id}/seating/assignments", {
          params: { path: { wedding_id: weddingId } },
          body: { assignments: [{ guest_id: person!.guest_id, table_id: person!.table_id!, locked: false }], replace_unlocked: false },
        }),
      ),
    onSuccess: () => done(`${person!.name}: odpięty`),
    onError: (e) => setError(`Nie zapisano. ${userMessage(e)}`),
  });

  return (
    <Sheet title={person ? `Gdzie siedzi ${person.name}?` : "Miejsce"} isOpen={!!person} onOpenChange={(o) => !o && onClose()}>
      {person && plan && (
        <div className="form-stack">
          {error && (
            <Notice tone="error" live>
              {error}
            </Notice>
          )}
          <p className="text-secondary">Wybrane ręcznie miejsce zostaje przypięte — automat go nie zmieni.</p>
          <ul className="row-list">
            {plan.tables.map((t) => {
              const here = t.id === person.table_id;
              return (
                <li key={t.id}>
                  <AriaButton
                    className="row-edit move-option"
                    isDisabled={here || seat.isPending}
                    onPress={() => seat.mutate(t.id)}
                  >
                    <span className="row__title">{t.name}</span>
                    <span className="text-secondary num">
                      {here ? "tu siedzi teraz" : t.free_seats > 0 ? plural(t.free_seats, { one: "# wolne miejsce", few: "# wolne miejsca", many: "# wolnych miejsc", other: "# wolnego miejsca" }) : "brak wolnych miejsc"}
                    </span>
                  </AriaButton>
                </li>
              );
            })}
          </ul>
          {person.table_id && (
            <Button variant="secondary" pending={seat.isPending && seat.variables === NO_TABLE} onPress={() => seat.mutate(NO_TABLE)}>
              Bez miejsca
            </Button>
          )}
          {person.locked && (
            <Button variant="text" pending={unpin.isPending} onPress={() => unpin.mutate()}>
              Odepnij (automat może przesadzić)
            </Button>
          )}
        </div>
      )}
    </Sheet>
  );
}

/* ---------------------------------------------------------------------------- automat */

function AutoSheet({
  weddingId,
  plan,
  people,
  isOpen,
  onOpenChange,
}: {
  weddingId: string;
  plan: SeatingPlan;
  people: Map<string, PersonRef>;
  isOpen: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [basis, setBasis] = useState<"not_declined" | "attending">("not_declined");
  const [keepHouseholds, setKeepHouseholds] = useState(true);
  const [kids, setKids] = useState(true);
  const [teens, setTeens] = useState(false);
  const [preview, setPreview] = useState<Auto | null>(null);
  const hasKidsTable = plan.tables.some((t) => t.kind === "kids");
  // „Blisko stołu pary / parkietu”: grupy z etykiet zaproszeń (np. „Rodzina Ani”).
  const households = useHouseholds(weddingId);
  const groups = useMemo(
    () => [...new Set((households.data ?? []).map((h) => h.group_label?.trim()).filter((g): g is string => !!g))].sort((a, b) => a.localeCompare(b, "pl")),
    [households.data],
  );
  const [near, setNear] = useState<Set<string>>(new Set());
  const [nearTarget, setNearTarget] = useState<"head" | "dance_floor">("head");
  const hasHead = plan.tables.some((t) => t.kind === "head");
  const hasFloor = (plan.room.items ?? []).some((i) => i.kind === "dance_floor");

  // Solver liczy w workerze (do kilkunastu sekund): zlecamy przebieg i odpytujemy jego stan.
  const run = useMutation({
    mutationFn: async () => {
      const path = { path: { wedding_id: weddingId } };
      const started = await unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/seating/auto-runs", {
          params: path,
          body: {
            basis,
            keep_households: keepHouseholds,
            kids_table: kids,
            kids_table_teens: kids && teens,
            time_limit_seconds: 10,
            near_groups: [...near],
            near_target: nearTarget,
            dry_run: true,
          },
        }),
      );
      const deadline = Date.now() + 60_000;
      for (;;) {
        const r = await unwrap(
          api.GET("/api/v1/weddings/{wedding_id}/seating/auto-runs/{run_id}", { params: { path: { ...path.path, run_id: started.id } } }),
        );
        if (r.status === "done" && r.result) return r.result;
        if (r.status === "failed") throw new Error(r.error_message ?? "Nie udało się ułożyć planu.");
        if (Date.now() > deadline) throw new Error("Liczenie trwa dłużej niż zwykle. Spróbujcie ponownie za chwilę.");
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    },
    onSuccess: setPreview,
  });

  const accept = useMutation({
    mutationFn: (a: Auto) =>
      unwrap(
        api.PUT("/api/v1/weddings/{wedding_id}/seating/assignments", {
          params: { path: { wedding_id: weddingId } },
          body: { assignments: a.assignments, replace_unlocked: true },
        }),
      ),
    onSuccess: async () => {
      setPreview(null);
      onOpenChange(false);
      await queryClient.invalidateQueries({ queryKey: keys.seating(weddingId) });
      toast("Zapisano układ stołów");
    },
  });

  const grouped = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const a of preview?.assignments ?? []) {
      map.set(a.table_id, [...(map.get(a.table_id) ?? []), people.get(a.guest_id)?.name ?? "?"]);
    }
    return plan.tables.map((t) => ({ table: t, names: map.get(t.id) ?? [] }));
  }, [preview, people, plan.tables]);

  const close = (o: boolean) => {
    if (!o) setPreview(null);
    onOpenChange(o);
  };

  return (
    <Sheet title="Usadź automatycznie" isOpen={isOpen} onOpenChange={close}>
      {preview ? (
        <div className="form-stack">
          <p className="text-secondary">
            Propozycja do dopracowania — miejsca przypięte ręcznie zostały zachowane. Po zapisie możecie przenosić osoby.
          </p>
          {preview.split_households.length > 0 && (
            <Notice tone="warning">
              {plural(preview.split_households.length, {
                one: "# rodzina nie zmieściła się przy jednym stole.",
                few: "# rodziny nie zmieściły się przy jednym stole.",
                many: "# rodzin nie zmieściło się przy jednym stole.",
                other: "# rodziny nie zmieściły się przy jednym stole.",
              })}
            </Notice>
          )}
          {near.size > 0 && !preview.near_applied && (
            <Notice tone="info">
              „Blisko” nie zostało uwzględnione: ustawcie na planie sali {nearTarget === "head" ? "stół pary młodej" : "parkiet"} i stoły, a potem
              spróbujcie ponownie.
            </Notice>
          )}
          {preview.issues.length > 0 && <IssueNotice tone="warning" title="Po usadzeniu" list={preview.issues} />}
          <ul className="row-list reschedule-list auto-preview">
            {grouped.map(({ table, names }) => (
              <li key={table.id} className="row">
                <span className="row__body">
                  <span className="row__title">
                    {table.name} <span className="text-secondary num">({names.length}/{table.capacity})</span>
                  </span>
                  <span className="text-secondary">{names.join(", ") || "pusty"}</span>
                </span>
              </li>
            ))}
          </ul>
          {accept.isError && (
            <Notice tone="error" live>
              {userMessage(accept.error)}
            </Notice>
          )}
          <div className="wp-sheet__actions">
            <Button variant="secondary" onPress={() => setPreview(null)}>
              Zmień ustawienia
            </Button>
            <Button pending={accept.isPending} onPress={() => accept.mutate(preview)}>
              Zapisz ten układ
            </Button>
          </div>
        </div>
      ) : (
        <Form
          className="form-stack"
          onSubmit={(e) => {
            e.preventDefault();
            run.mutate();
          }}
        >
          {run.isError && (
            <Notice tone="error" live>
              {run.error instanceof Error && !(run.error instanceof ApiError) ? run.error.message : userMessage(run.error)}
            </Notice>
          )}
          <Segmented
            label="Kogo sadzamy?"
            value={basis}
            options={[
              { value: "not_declined", label: "Wszystkich poza odmowami" },
              { value: "attending", label: "Tylko potwierdzonych" },
            ]}
            onChange={setBasis}
          />
          <Checkbox isSelected={keepHouseholds} onChange={setKeepHouseholds}>
            Rodziny i pary razem
          </Checkbox>
          {hasKidsTable && (
            <Checkbox isSelected={kids} onChange={setKids}>
              Dzieci przy stole dziecięcym
            </Checkbox>
          )}
          {hasKidsTable && kids && (
            <Checkbox isSelected={teens} onChange={setTeens}>
              Także nastolatki (13–17 lat), jeśli starczy miejsc
            </Checkbox>
          )}
          {groups.length > 0 && (
            <fieldset className="plain-fieldset form-stack">
              <legend className="wp-field__label">Blisko (wg planu sali)</legend>
              {(hasHead || hasFloor) && (
                <Segmented
                  label="Czego blisko?"
                  value={nearTarget}
                  options={[
                    { value: "head", label: "Stołu pary młodej" },
                    { value: "dance_floor", label: "Parkietu" },
                  ]}
                  onChange={setNearTarget}
                />
              )}
              {groups.map((g) => (
                <Checkbox
                  key={g}
                  isSelected={near.has(g)}
                  onChange={(v) =>
                    setNear((s) => {
                      const next = new Set(s);
                      if (v) next.add(g);
                      else next.delete(g);
                      return next;
                    })
                  }
                >
                  {g}
                </Checkbox>
              ))}
              <p className="text-secondary">Np. rodzice i dziadkowie przy stołach najbliżej pary. Działa, gdy stoły są ustawione na planie sali.</p>
            </fieldset>
          )}
          <p className="text-secondary">Liczenie trwa do kilkunastu sekund. Uwzględniamy też Wasze reguły „razem” i „osobno”.</p>
          <Button type="submit" block pending={run.isPending}>
            Pokaż propozycję
          </Button>
        </Form>
      )}
    </Sheet>
  );
}

/* ----------------------------------------------------------------------------- reguły */

function RulesSection({ weddingId, people, canWrite }: { weddingId: string; people: Map<string, PersonRef>; canWrite: boolean }) {
  const rules = useSeatingRules(weddingId);
  const queryClient = useQueryClient();
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const [kind, setKind] = useState<"together" | "apart">("apart");
  const [a, setA] = useState<string | null>(null);
  const [b, setB] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const options = [...people.values()]
    .sort((x, y) => x.name.localeCompare(y.name, "pl"))
    .map((g) => ({ id: g.guest_id, label: g.name }));
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: keys.seatingRules(weddingId) }),
      queryClient.invalidateQueries({ queryKey: keys.seating(weddingId) }),
    ]);

  const create = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/seating/rules", {
          params: { path: { wedding_id: weddingId } },
          body: { kind, guest_a_id: a!, guest_b_id: b!, note: note.trim() || null },
        }),
      ),
    onSuccess: async () => {
      setAdding(false);
      setA(null);
      setB(null);
      setNote("");
      setError(null);
      await refresh();
      toast("Dodano regułę");
    },
    onError: (e) => setError(`Nie zapisano. ${userMessage(e)}`),
  });

  const remove = useMutation({
    mutationFn: (ruleId: string) =>
      unwrap(
        api.DELETE("/api/v1/weddings/{wedding_id}/seating/rules/{rule_id}", {
          params: { path: { wedding_id: weddingId, rule_id: ruleId } },
        }),
      ),
    onSuccess: async () => {
      await refresh();
      toast("Usunięto regułę");
    },
  });

  const name = (guestId: string) => people.get(guestId)?.name ?? "?";

  return (
    <section aria-labelledby="rules-h" className="form-stack">
      <div className="section-head">
        <h2 id="rules-h">Razem i osobno</h2>
        {canWrite && (
          <Button variant="text" icon={<Plus aria-hidden size={18} />} onPress={() => setAdding(true)}>
            Dodaj
          </Button>
        )}
      </div>
      <Card>
        {(rules.data?.length ?? 0) === 0 ? (
          <p className="text-secondary">Np. „Wujek Zenek osobno od cioci Basi” albo „Kasia razem z Tomkiem”.</p>
        ) : (
          <ul className="row-list">
            {rules.data!.map((r) => (
              <li key={r.id} className="row">
                <span className="row__body">
                  <span className="row__title">
                    {name(r.guest_a_id)} {r.kind === "together" ? "razem z" : "osobno od"} {name(r.guest_b_id)}
                  </span>
                  {r.note && <span className="text-secondary">{r.note}</span>}
                </span>
                {canWrite && (
                  <Button
                    variant="text"
                    pending={remove.isPending && remove.variables === r.id}
                    onPress={() => remove.mutate(r.id)}
                    aria-label={`Usuń regułę: ${name(r.guest_a_id)} ${r.kind === "together" ? "razem z" : "osobno od"} ${name(r.guest_b_id)}`}
                  >
                    Usuń
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Sheet title="Nowa reguła" isOpen={adding} onOpenChange={setAdding}>
        <Form
          className="form-stack"
          onSubmit={(e) => {
            e.preventDefault();
            if (!a || !b || a === b) {
              setError("Wybierz dwie różne osoby.");
              return;
            }
            create.mutate();
          }}
        >
          {error && (
            <Notice tone="error" live>
              {error}
            </Notice>
          )}
          <Select label="Osoba" options={options} value={a} onChange={setA} placeholder="Wybierz" />
          <Segmented
            label="Ma siedzieć"
            value={kind}
            options={[
              { value: "apart", label: "Osobno od" },
              { value: "together", label: "Razem z" },
            ]}
            onChange={setKind}
          />
          <Select label="Druga osoba" options={options} value={b} onChange={setB} placeholder="Wybierz" />
          <TextField label="Notatka (opcjonalnie, widzicie ją tylko Wy)" value={note} onChange={setNote} />
          <Button type="submit" block pending={create.isPending}>
            Dodaj regułę
          </Button>
        </Form>
      </Sheet>
    </section>
  );
}
