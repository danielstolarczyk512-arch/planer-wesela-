/** Transport i noclegi gości: kursy z miejscami, pokoje i lista dla hotelu, kto jeszcze bez przydziału. */
import {
  CalendarDateTime,
  parseAbsolute,
  parseDate,
  toCalendarDate,
  toTime,
  toZoned,
  type CalendarDate,
  type Time,
} from "@internationalized/date";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BedDouble, Bus, Download, Plus } from "lucide-react";
import { useRef, useState } from "react";
import { Form } from "react-aria-components";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { downloadAuthorized } from "../../api/download";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { DateField, TimeField } from "../../components/DateField";
import { Checkbox, TextField } from "../../components/Field";
import { ConfirmDialog, Sheet } from "../../components/Overlay";
import { Select } from "../../components/Select";
import { Card, EmptyState, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate, formatTime, plural, TIME_ZONE } from "../../lib/format";
import { GUEST_SECTIONS, PrintLink, SectionNav } from "./SectionNav";
import { keys, useCanWrite, useHouseholds, useWedding, useWeddingId } from "./data";
import { ifMatch, saveErrorMessage } from "./mutations";
import { useVendors } from "./vendors";

type Overview = components["schemas"]["LogisticsOverview"];
type Run = Overview["runs"][number];
type Room = Overview["rooms"][number];

const KINDS = [
  { id: "there", label: "Na wesele" },
  { id: "back", label: "Powrót" },
  { id: "other", label: "Inny" },
];
const PEOPLE = { one: "# osoba", few: "# osoby", many: "# osób", other: "# osoby" };

const logisticsKey = (id: string) => [...keys.households(id), "logistics"];

/** Data i godzina (czas polski) → moment dla API. */
export function toInstant(day: CalendarDate, time: Time): string {
  return toZoned(new CalendarDateTime(day.year, day.month, day.day, time.hour, time.minute), TIME_ZONE).toAbsoluteString();
}

/** Opis zajętości kursu: „12/50”, „Przepełniony o 3”. */
export function seatsText(r: Pick<Run, "taken" | "capacity" | "over">): string {
  return r.over > 0 ? `Przepełniony o ${r.over} (${r.taken}/${r.capacity})` : `${r.taken}/${r.capacity} miejsc`;
}

export function LogisticsView() {
  const id = useWeddingId();
  const canWrite = useCanWrite(id);
  const data = useQuery({
    queryKey: logisticsKey(id),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/logistics", { params: { path: { wedding_id: id } }, signal })),
  });
  const [runSheet, setRunSheet] = useState<Run | "new" | null>(null);
  const [roomSheet, setRoomSheet] = useState<Room | "new" | null>(null);
  const [people, setPeople] = useState<{ kind: "run"; item: Run } | { kind: "room"; item: Room } | null>(null);
  const o = data.data;

  return (
    <main className="page enter-tab" aria-labelledby="log-h">
      <SectionNav label="Goście" sections={GUEST_SECTIONS} />
      <div>
        <h1 id="log-h">Transport i noclegi</h1>
        <p className="text-secondary">Kursy autokaru i pokoje dla gości — z liczbą miejsc i listą dla hotelu, zawsze aktualną.</p>
      </div>
      {data.isPending && <Skeleton lines={4} />}
      {data.isError && (
        <Notice tone="error" live>
          {userMessage(data.error)}
        </Notice>
      )}
      {o && (
        <>
          {o.transport_missing.length > 0 && (
            <Notice tone="warning" title={`Potrzebują transportu, bez kursu: ${plural(o.transport_missing.length, PEOPLE)}`}>
              {o.transport_missing.map((p) => p.name).join(", ")}
            </Notice>
          )}
          {o.lodging_missing.length > 0 && (
            <Notice tone="warning" title={`Potrzebują noclegu, bez pokoju: ${plural(o.lodging_missing.length, PEOPLE)}`}>
              {o.lodging_missing.map((p) => p.name).join(", ")}
            </Notice>
          )}

          <section className="form-stack" aria-labelledby="runs-h">
            <div className="section-head section-head--wrap">
              <h2 id="runs-h">Kursy</h2>
              {o.runs.length > 0 && <PrintLink kind="kursy">Listy pasażerów</PrintLink>}
              {canWrite && (
                <Button variant="secondary" icon={<Plus aria-hidden size={18} />} onPress={() => setRunSheet("new")}>
                  Dodaj kurs
                </Button>
              )}
            </div>
            {o.runs.length === 0 ? (
              <EmptyState title="Brak kursów">Dodajcie np. „Autokar: kościół → sala” z liczbą miejsc i godziną odjazdu.</EmptyState>
            ) : (
              o.runs.map((r) => (
                <Card key={r.id} className="form-stack">
                  <div className="section-head section-head--wrap">
                    <h3 className="logistics__title">
                      <Bus aria-hidden size={20} /> {r.name}
                    </h3>
                    <StatusChip tone={r.over > 0 ? "error" : r.taken === r.capacity ? "warning" : "neutral"}>{seatsText(r)}</StatusChip>
                    {r.show_to_guests && <StatusChip tone="info">Widoczny dla gości</StatusChip>}
                  </div>
                  <p className="text-secondary">
                    {[KINDS.find((k) => k.id === r.kind)?.label, r.departs_at && `odjazd ${formatDate(r.departs_at.slice(0, 10))}, ${formatTime(r.departs_at)}`, [r.from_place, r.to_place].filter(Boolean).join(" → ")]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                  {r.missed_items.length > 0 && (
                    <Notice tone="warning">
                      Odjeżdża przed: {r.missed_items.map((m) => `${m.title} (${formatTime(m.starts_at)})`).join(", ")}. Goście tego kursu to ominą.
                    </Notice>
                  )}
                  <p>{r.passengers.length ? r.passengers.map((p) => p.name + (p.declined ? " (odmówił)" : "")).join(", ") : "Brak pasażerów."}</p>
                  {canWrite && (
                    <div className="wp-sheet__actions">
                      <Button variant="secondary" onPress={() => setPeople({ kind: "run", item: r })}>
                        Pasażerowie
                      </Button>
                      <Button variant="text" onPress={() => setRunSheet(r)}>
                        Edytuj kurs
                      </Button>
                    </div>
                  )}
                </Card>
              ))
            )}
          </section>

          <section className="form-stack" aria-labelledby="rooms-h">
            <div className="section-head section-head--wrap">
              <h2 id="rooms-h">Noclegi</h2>
              {canWrite && (
                <Button variant="secondary" icon={<Plus aria-hidden size={18} />} onPress={() => setRoomSheet("new")}>
                  Dodaj pokój
                </Button>
              )}
            </div>
            {o.rooms.length === 0 ? (
              <EmptyState title="Brak pokoi">Dodajcie pokoje z hotelu lub sali — przypiszecie do nich gości i pobierzecie listę dla hotelu.</EmptyState>
            ) : (
              <>
                {o.rooms.map((r) => (
                  <Card key={r.id} className="form-stack">
                    <div className="section-head section-head--wrap">
                      <h3 className="logistics__title">
                        <BedDouble aria-hidden size={20} /> {r.place}, {r.name}
                      </h3>
                      <StatusChip tone={r.free > 0 ? "neutral" : "success"}>{r.free > 0 ? `Wolne: ${r.free}` : "Pełny"}</StatusChip>
                    </div>
                    <p className="text-secondary">
                      {[
                        `${r.beds} miejsc`,
                        r.check_in && r.check_out && `${formatDate(r.check_in)} – ${formatDate(r.check_out)} (${plural(r.nights ?? 0, { one: "# noc", few: "# noce", many: "# nocy", other: "# nocy" })})`,
                        r.paid_by && `płaci: ${r.paid_by}`,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                    <p>{r.occupants.length ? r.occupants.map((p) => p.name + (p.declined ? " (odmówił)" : "")).join(", ") : "Pokój pusty."}</p>
                    {canWrite && (
                      <div className="wp-sheet__actions">
                        <Button variant="secondary" onPress={() => setPeople({ kind: "room", item: r })}>
                          Kto śpi
                        </Button>
                        <Button variant="text" onPress={() => setRoomSheet(r)}>
                          Edytuj pokój
                        </Button>
                      </div>
                    )}
                  </Card>
                ))}
                <RoomingDownload weddingId={id} />
              </>
            )}
          </section>
        </>
      )}
      <RunSheet weddingId={id} run={runSheet} onClose={() => setRunSheet(null)} />
      <RoomSheet weddingId={id} room={roomSheet} onClose={() => setRoomSheet(null)} />
      <PeopleSheet weddingId={id} target={people} onClose={() => setPeople(null)} />
    </main>
  );
}

function useSaver(weddingId: string, onClose: () => void, message: string) {
  const queryClient = useQueryClient();
  const toast = useToast();
  return {
    queryClient,
    done: (data: Overview | void) => {
      if (data) queryClient.setQueryData(logisticsKey(weddingId), data);
      else void queryClient.invalidateQueries({ queryKey: logisticsKey(weddingId) });
      onClose();
      toast(message);
    },
  };
}

function RunSheet({ weddingId, run, onClose }: { weddingId: string; run: Run | "new" | null; onClose: () => void }) {
  return (
    <Sheet title={run === "new" ? "Nowy kurs" : "Kurs"} isOpen={run !== null} onOpenChange={(open) => !open && onClose()}>
      {run && <RunForm key={run === "new" ? "new" : `${run.id}-${run.version}`} weddingId={weddingId} run={run === "new" ? null : run} onClose={onClose} />}
    </Sheet>
  );
}

function RunForm({ weddingId, run, onClose }: { weddingId: string; run: Run | null; onClose: () => void }) {
  const wedding = useWedding(weddingId);
  const vendors = useVendors(weddingId);
  const start = run?.departs_at ? parseAbsolute(run.departs_at, TIME_ZONE) : null;
  const [name, setName] = useState(run?.name ?? "");
  const [kind, setKind] = useState<string>(run?.kind ?? "there");
  const [day, setDay] = useState<CalendarDate | null>(start ? toCalendarDate(start) : wedding.data?.wedding_date ? parseDate(wedding.data.wedding_date) : null);
  const [time, setTime] = useState<Time | null>(start ? toTime(start) : null);
  const [from, setFrom] = useState(run?.from_place ?? "");
  const [to, setTo] = useState(run?.to_place ?? "");
  const [capacity, setCapacity] = useState(run ? String(run.capacity) : "");
  const [vendor, setVendor] = useState<string>(run?.vendor_id ?? "");
  const [shown, setShown] = useState(run?.show_to_guests ?? false);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const key = useRef(newIdempotencyKey());
  const { queryClient, done } = useSaver(weddingId, onClose, run ? "Zapisano kurs" : "Dodano kurs");
  const seats = Number(capacity);
  const valid = name.trim() !== "" && Number.isInteger(seats) && seats >= 1 && seats <= 500;
  const transport = (vendors.data ?? []).filter((v) => v.category === "transport");
  const body = {
    name: name.trim(),
    kind: kind as Run["kind"],
    departs_at: day && time ? toInstant(day, time) : null,
    from_place: from.trim() || null,
    to_place: to.trim() || null,
    capacity: seats,
    vendor_id: vendor || null,
    show_to_guests: shown,
  };
  const save = useMutation({
    mutationFn: () =>
      run
        ? unwrap(api.PATCH("/api/v1/weddings/{wedding_id}/transport-runs/{run_id}", { params: { path: { wedding_id: weddingId, run_id: run.id } }, body, headers: ifMatch(run.version) }))
        : unwrap(api.POST("/api/v1/weddings/{wedding_id}/transport-runs", { params: { path: { wedding_id: weddingId } }, body, headers: { "Idempotency-Key": key.current } })),
    onSuccess: done,
    onError: (e) => setError(saveErrorMessage(e, queryClient, [logisticsKey(weddingId)])),
  });
  const remove = useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/v1/weddings/{wedding_id}/transport-runs/{run_id}", { params: { path: { wedding_id: weddingId, run_id: run!.id } } })),
    onSuccess: () => done(),
    onError: (e) => setError(`Nie usunięto. ${userMessage(e)}`),
  });
  return (
    <Form
      className="form-stack"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) save.mutate();
      }}
    >
      <TextField label="Nazwa kursu" description="Np. „Autokar: kościół → sala”." value={name} onChange={setName} isRequired autoComplete="off" />
      <Select label="Rodzaj" options={KINDS} value={kind} onChange={setKind} />
      <div className="delivery-plan">
        <DateField label="Dzień" value={day} onChange={setDay} />
        <TimeField label="Godzina odjazdu" value={time} onChange={setTime} />
      </div>
      <div className="delivery-plan">
        <TextField label="Skąd" value={from} onChange={setFrom} maxLength={120} autoComplete="off" />
        <TextField label="Dokąd" value={to} onChange={setTo} maxLength={120} autoComplete="off" />
      </div>
      <TextField
        label="Liczba miejsc"
        inputMode="numeric"
        value={capacity}
        onChange={setCapacity}
        isRequired
        error={capacity !== "" && !(seats >= 1 && seats <= 500) ? "Od 1 do 500." : undefined}
      />
      {transport.length > 0 && (
        <Select
          label="Przewoźnik (zobaczy kurs na swoim linku)"
          options={[{ id: "", label: "Bez przewoźnika" }, ...transport.map((v) => ({ id: v.id, label: v.name }))]}
          value={vendor}
          onChange={setVendor}
        />
      )}
      <Checkbox isSelected={shown} onChange={setShown}>
        Pokaż gościom w formularzu potwierdzenia — sami zapiszą się na kurs (widzą tylko liczbę wolnych miejsc)
      </Checkbox>
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      <div className="wp-sheet__actions">
        <Button type="submit" pending={save.isPending} isDisabled={!valid}>
          {run ? "Zapisz" : "Dodaj kurs"}
        </Button>
        {run && (
          <Button variant="text" onPress={() => setConfirm(true)}>
            Usuń kurs
          </Button>
        )}
      </div>
      <ConfirmDialog title="Usunąć kurs?" isOpen={confirm} onOpenChange={setConfirm}>
        <p>Kurs „{run?.name}” zniknie razem z listą pasażerów.</p>
        <div className="wp-sheet__actions">
          <Button variant="secondary" onPress={() => setConfirm(false)}>
            Zostaw
          </Button>
          <Button variant="danger" pending={remove.isPending} onPress={() => remove.mutate()}>
            Usuń
          </Button>
        </div>
      </ConfirmDialog>
    </Form>
  );
}

function RoomSheet({ weddingId, room, onClose }: { weddingId: string; room: Room | "new" | null; onClose: () => void }) {
  return (
    <Sheet title={room === "new" ? "Nowy pokój" : "Pokój"} isOpen={room !== null} onOpenChange={(open) => !open && onClose()}>
      {room && <RoomForm key={room === "new" ? "new" : `${room.id}-${room.version}`} weddingId={weddingId} room={room === "new" ? null : room} onClose={onClose} />}
    </Sheet>
  );
}

function RoomForm({ weddingId, room, onClose }: { weddingId: string; room: Room | null; onClose: () => void }) {
  const [place, setPlace] = useState(room?.place ?? "");
  const [name, setName] = useState(room?.name ?? "");
  const [beds, setBeds] = useState(room ? String(room.beds) : "2");
  const [checkIn, setCheckIn] = useState<CalendarDate | null>(room?.check_in ? parseDate(room.check_in) : null);
  const [checkOut, setCheckOut] = useState<CalendarDate | null>(room?.check_out ? parseDate(room.check_out) : null);
  const [paidBy, setPaidBy] = useState(room?.paid_by ?? "");
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const key = useRef(newIdempotencyKey());
  const { queryClient, done } = useSaver(weddingId, onClose, room ? "Zapisano pokój" : "Dodano pokój");
  const n = Number(beds);
  const nightsError = checkIn && checkOut && checkOut.compare(checkIn) <= 0 ? "Wymeldowanie musi być po zameldowaniu." : undefined;
  const valid = place.trim() !== "" && name.trim() !== "" && Number.isInteger(n) && n >= 1 && n <= 20 && !nightsError;
  const body = {
    place: place.trim(),
    name: name.trim(),
    beds: n,
    check_in: checkIn?.toString() ?? null,
    check_out: checkOut?.toString() ?? null,
    paid_by: paidBy.trim() || null,
  };
  const save = useMutation({
    mutationFn: () =>
      room
        ? unwrap(api.PATCH("/api/v1/weddings/{wedding_id}/lodging-rooms/{room_id}", { params: { path: { wedding_id: weddingId, room_id: room.id } }, body, headers: ifMatch(room.version) }))
        : unwrap(api.POST("/api/v1/weddings/{wedding_id}/lodging-rooms", { params: { path: { wedding_id: weddingId } }, body, headers: { "Idempotency-Key": key.current } })),
    onSuccess: done,
    onError: (e) => setError(saveErrorMessage(e, queryClient, [logisticsKey(weddingId)])),
  });
  const remove = useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/v1/weddings/{wedding_id}/lodging-rooms/{room_id}", { params: { path: { wedding_id: weddingId, room_id: room!.id } } })),
    onSuccess: () => done(),
    onError: (e) => setError(`Nie usunięto. ${userMessage(e)}`),
  });
  return (
    <Form
      className="form-stack"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) save.mutate();
      }}
    >
      <TextField label="Obiekt" description="Np. hotel przy sali." value={place} onChange={setPlace} isRequired autoComplete="off" />
      <div className="delivery-plan">
        <TextField label="Pokój" value={name} onChange={setName} isRequired autoComplete="off" />
        <TextField label="Liczba miejsc" inputMode="numeric" value={beds} onChange={setBeds} isRequired error={beds !== "" && !(n >= 1 && n <= 20) ? "Od 1 do 20." : undefined} />
      </div>
      <div className="delivery-plan">
        <DateField label="Zameldowanie" value={checkIn} onChange={setCheckIn} />
        <DateField label="Wymeldowanie" value={checkOut} onChange={setCheckOut} error={nightsError} />
      </div>
      <TextField label="Kto płaci (opcjonalnie)" description="Np. para, goście." value={paidBy} onChange={setPaidBy} maxLength={80} autoComplete="off" />
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      <div className="wp-sheet__actions">
        <Button type="submit" pending={save.isPending} isDisabled={!valid}>
          {room ? "Zapisz" : "Dodaj pokój"}
        </Button>
        {room && (
          <Button variant="text" onPress={() => setConfirm(true)}>
            Usuń pokój
          </Button>
        )}
      </div>
      <ConfirmDialog title="Usunąć pokój?" isOpen={confirm} onOpenChange={setConfirm}>
        <p>Pokój „{room?.name}” zniknie, a goście wrócą na listę bez noclegu.</p>
        <div className="wp-sheet__actions">
          <Button variant="secondary" onPress={() => setConfirm(false)}>
            Zostaw
          </Button>
          <Button variant="danger" pending={remove.isPending} onPress={() => remove.mutate()}>
            Usuń
          </Button>
        </div>
      </ConfirmDialog>
    </Form>
  );
}

function PeopleSheet({
  weddingId,
  target,
  onClose,
}: {
  weddingId: string;
  target: { kind: "run"; item: Run } | { kind: "room"; item: Room } | null;
  onClose: () => void;
}) {
  const title = target?.kind === "room" ? `Kto śpi: ${target.item.name}` : target ? `Pasażerowie: ${target.item.name}` : "Goście";
  return (
    <Sheet title={title} isOpen={target !== null} onOpenChange={(open) => !open && onClose()}>
      {target && <PeopleForm key={target.item.id} weddingId={weddingId} target={target} onClose={onClose} />}
    </Sheet>
  );
}

function PeopleForm({ weddingId, target, onClose }: { weddingId: string; target: { kind: "run"; item: Run } | { kind: "room"; item: Room }; onClose: () => void }) {
  const households = useHouseholds(weddingId);
  const current = target.kind === "run" ? target.item.passengers : target.item.occupants;
  const [selected, setSelected] = useState<Set<string>>(new Set(current.map((p) => p.guest_id)));
  const { done } = useSaver(weddingId, onClose, "Zapisano");
  const limit = target.kind === "room" ? target.item.beds : null;
  const need = (g: { needs_transport: boolean; needs_accommodation: boolean }) => (target.kind === "run" ? g.needs_transport : g.needs_accommodation);
  const guests = (households.data ?? [])
    .flatMap((h) => h.guests.map((g) => ({ ...g, household: h.name })))
    .sort((a, b) => Number(need(b)) - Number(need(a)) || a.first_name.localeCompare(b.first_name, "pl"));
  const save = useMutation({
    mutationFn: () => {
      const body = { guest_ids: [...selected] };
      return target.kind === "run"
        ? unwrap(api.PUT("/api/v1/weddings/{wedding_id}/transport-runs/{run_id}/guests", { params: { path: { wedding_id: weddingId, run_id: target.item.id } }, body }))
        : unwrap(api.PUT("/api/v1/weddings/{wedding_id}/lodging-rooms/{room_id}/guests", { params: { path: { wedding_id: weddingId, room_id: target.item.id } }, body }));
    },
    onSuccess: done,
  });
  return (
    <div className="form-stack">
      <p className="text-secondary">
        Na górze osoby, które zaznaczyły, że {target.kind === "run" ? "potrzebują transportu" : "potrzebują noclegu"}.
        {limit ? ` Miejsc w pokoju: ${limit}.` : target.kind === "run" ? ` Miejsc w kursie: ${target.item.capacity}.` : ""}
      </p>
      {households.isPending && <Skeleton lines={3} />}
      <ul className="row-list">
        {guests.map((g) => {
          const on = selected.has(g.id);
          return (
            <li key={g.id} className="row">
              <Checkbox
                isSelected={on}
                isDisabled={!on && limit !== null && selected.size >= limit}
                onChange={(v) =>
                  setSelected((s) => {
                    const next = new Set(s);
                    if (v) next.add(g.id);
                    else next.delete(g.id);
                    return next;
                  })
                }
              >
                <span className="row__body">
                  <span className="row__title">
                    {g.first_name} {g.last_name ?? ""}
                  </span>
                  <span className="text-secondary">
                    {g.household}
                    {need(g) ? (target.kind === "run" ? " · potrzebuje transportu" : " · potrzebuje noclegu") : ""}
                  </span>
                </span>
              </Checkbox>
            </li>
          );
        })}
      </ul>
      {save.isError && (
        <Notice tone="error" live>
          Nie zapisano. {userMessage(save.error)}
        </Notice>
      )}
      <div className="wp-sheet__actions">
        <Button pending={save.isPending} onPress={() => save.mutate()}>
          Zapisz ({selected.size})
        </Button>
      </div>
    </div>
  );
}

/** Lista pokoi dla hotelu: plik CSV pobierany z tokenem sesji (bez tokenu w adresie). */
function RoomingDownload({ weddingId }: { weddingId: string }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <div className="form-stack">
      <Button
        variant="text"
        icon={<Download aria-hidden size={18} />}
        pending={busy}
        onPress={async () => {
          setBusy(true);
          setError(null);
          try {
            await downloadAuthorized(`/api/v1/weddings/${weddingId}/lodging/rooming.csv`, "lista-pokoi.csv");
          } catch (e) {
            setError(userMessage(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        Lista pokoi dla hotelu (Excel/CSV)
      </Button>
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
    </div>
  );
}
