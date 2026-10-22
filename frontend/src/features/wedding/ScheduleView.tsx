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
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Printer } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { DateField, TimeField } from "../../components/DateField";
import { Checkbox, TextField } from "../../components/Field";
import { ConfirmDialog, Sheet } from "../../components/Overlay";
import { Select } from "../../components/Select";
import { Card, EmptyState, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { PremiumBadge } from "../../components/Premium";
import { formatDate, formatTime, plural, TIME_ZONE, todayInWarsaw } from "../../lib/format";
import {
  keys,
  useCanRunDay,
  useCanWrite,
  useEvents,
  useSchedule,
  useScheduleConflicts,
  useWedding,
  useWeddingId,
  type ScheduleConflict,
  type ScheduleItem,
  type WeddingEvent,
} from "./data";
import { ifMatch, saveErrorMessage } from "./mutations";
import { useVendors } from "./vendors";
import { VendorAckSummary, briefKeys } from "./VendorBriefSection";
import { DayChecklist } from "./DayChecklist";
import { DaySectionNav } from "./SectionNav";
import { DayTransport } from "./DayTransport";
import { OfflineDay, useOnline } from "../../components/OfflineDay";
import { readDayCopy, removeDayCopy, saveDayCopy, weddingCopyKey } from "../../lib/dayCopy";
import { applyQueue, canSendSafely, enqueueShift, readQueue, removeShift, type QueuedShift } from "../../lib/dayQueue";

type ItemPatch = components["schemas"]["app__modules__schedule__schemas__ItemUpdate"];
type Shift = components["schemas"]["ShiftOut"];
type Template = components["schemas"]["TemplateOut"];

const NO_EVENT = "__none__";
const NO_VENDOR = "__no_vendor__";
const DURATIONS = [0, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 360].map((m) => ({
  id: String(m),
  label: m === 0 ? "Chwila (bez czasu trwania)" : m < 60 ? `${m} min` : m % 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m / 60} h`,
}));
const SHIFTS = [-30, -15, 15, 30, 60];

/** Data i godzina z formularza (czas polski) → moment dla API. */
export function toInstant(day: CalendarDate, time: Time): string {
  return toZoned(new CalendarDateTime(day.year, day.month, day.day, time.hour, time.minute), TIME_ZONE).toAbsoluteString();
}

/** Moment z API → data i godzina w czasie polskim (do pól formularza). */
export function fromInstant(iso: string): { day: CalendarDate; time: Time } {
  const z = parseAbsolute(iso, TIME_ZONE);
  return { day: toCalendarDate(z), time: toTime(z) };
}

/** „15:00–16:30” albo „15:00” dla punktu bez czasu trwania. */
export function timeRange(item: Pick<ScheduleItem, "starts_at" | "ends_at" | "duration_minutes">): string {
  const start = formatTime(item.starts_at);
  return item.duration_minutes > 0 ? `${start}–${formatTime(item.ends_at)}` : start;
}

/**
 * Doba weselna w czasie polskim („2028-07-01”) — do grupowania (np. wesele + poprawiny).
 * Punkty do 6:00 rano należą do poprzedniego dnia: oczepiny o 0:30 to wciąż ta sama noc.
 */
export function dayOf(iso: string): string {
  return toCalendarDate(parseAbsolute(iso, TIME_ZONE).subtract({ hours: 6 })).toString();
}

function TimeCell({ item }: { item: Pick<ScheduleItem, "starts_at" | "ends_at" | "duration_minutes"> }) {
  return (
    <span className="timeline__time num">
      <strong>{formatTime(item.starts_at)}</strong>
      {item.duration_minutes > 0 && <span className="text-secondary">do {formatTime(item.ends_at)}</span>}
    </span>
  );
}

export function ScheduleView() {
  const id = useWeddingId();
  const wedding = useWedding(id);
  const schedule = useSchedule(id);
  const conflicts = useScheduleConflicts(id);
  const events = useEvents(id);
  const canWrite = useCanWrite(id);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [template, setTemplate] = useState(false);
  const canRun = useCanRunDay(id);
  const isWeddingDay = wedding.data?.wedding_date === todayInWarsaw();
  const [live, setLive] = useState(false);
  const online = useOnline();
  // Brak sieci i brak danych: program z kopii zapisanej na tym urządzeniu (jeśli jest).
  const offlineCopy = !schedule.data && (!online || schedule.isError) ? readDayCopy(weddingCopyKey(id), todayInWarsaw()) : null;

  const days = useMemo(() => {
    const map = new Map<string, ScheduleItem[]>();
    for (const item of schedule.data ?? []) {
      const d = dayOf(item.starts_at);
      map.set(d, [...(map.get(d) ?? []), item]);
    }
    return [...map.entries()];
  }, [schedule.data]);
  const eventName = useMemo(() => new Map((events.data ?? []).map((e) => [e.id, e.name])), [events.data]);
  const editingItem = schedule.data?.find((i) => i.id === editing) ?? null;
  const errors = (conflicts.data ?? []).filter((c) => c.severity === "error");
  const warnings = (conflicts.data ?? []).filter((c) => c.severity === "warning");

  return (
    <main className="page enter-tab schedule" aria-labelledby="schedule-h">
      <DaySectionNav />
      <div className="view-head">
        <div>
          <h1 id="schedule-h">Harmonogram dnia</h1>
          <p className="text-secondary">
            {wedding.data?.wedding_date ? formatDate(wedding.data.wedding_date) : "Godzina po godzinie."}
          </p>
        </div>
        {canWrite && (schedule.data?.length ?? 0) > 0 && (
          <Button variant="secondary" icon={<Plus aria-hidden size={20} />} onPress={() => setAdding(true)}>
            Dodaj punkt
          </Button>
        )}
      </div>

      {schedule.isPending && !offlineCopy && <Skeleton lines={8} />}
      {offlineCopy && !schedule.data && <OfflineDay copy={offlineCopy} />}
      {schedule.isError && !offlineCopy && (
        <Notice tone="error" title="Nie udało się wczytać harmonogramu." live>
          {userMessage(schedule.error)}
        </Notice>
      )}

      {schedule.data && schedule.data.length === 0 && (
        <EmptyState
          title="Harmonogram jest pusty"
          action={
            canWrite ? (
              <div className="form-stack">
                <Button onPress={() => setTemplate(true)}>Wczytaj typowy program</Button>
                <Button variant="text" onPress={() => setAdding(true)}>
                  Dodaj pierwszy punkt ręcznie
                </Button>
              </div>
            ) : undefined
          }
        >
          Typowy program polskiego wesela (przygotowania, ceremonia, obiad, pierwszy taniec, tort, oczepiny) to dobry punkt
          wyjścia — godziny dopasujecie później.
        </EmptyState>
      )}

      {(schedule.data?.length ?? 0) > 0 &&
        (isWeddingDay || live ? (
          <LivePanel
            weddingId={id}
            weddingName={wedding.data?.name ?? "Program dnia"}
            weddingDate={wedding.data?.wedding_date ?? null}
            items={schedule.data ?? []}
            canRun={canRun}
          />
        ) : (
          <Button variant="secondary" onPress={() => setLive(true)}>
            Tryb dnia ślubu <PremiumBadge />
          </Button>
        ))}

      {errors.length > 0 && <ConflictNotice tone="error" title="Do poprawienia" list={errors} />}
      {warnings.length > 0 && <ConflictNotice tone="warning" title="Warto sprawdzić" list={warnings} />}

      {days.map(([day, items]) => (
        <section key={day} className="form-stack" aria-label={formatDate(day)}>
          {days.length > 1 && <h2>{formatDate(day)}</h2>}
          <Card>
            <ol className="row-list timeline">
              {items.map((item) => {
                const body = (
                  <>
                    <TimeCell item={item} />
                    <span className="row__body">
                      <span className="row__title">{item.title}</span>
                      <span className="text-secondary">
                        {[
                          item.event_id && eventName.get(item.event_id),
                          item.location,
                          item.responsible_name ?? item.vendor_name,
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                      {item.plan_b && <span className="text-secondary plan-b">Plan B: {item.plan_b}</span>}
                    </span>
                  </>
                );
                const severity = (conflicts.data ?? []).find((c) => c.item_ids.includes(item.id))?.severity;
                return (
                  <li key={item.id} className="row">
                    {canWrite ? (
                      <AriaButton className="row-edit timeline__row" onPress={() => setEditing(item.id)}>
                        {body}
                      </AriaButton>
                    ) : (
                      <div className="timeline__row">{body}</div>
                    )}
                    {severity && (
                      <StatusChip tone={severity === "error" ? "error" : "warning"}>
                        {severity === "error" ? "Konflikt" : "Uwaga"}
                      </StatusChip>
                    )}
                  </li>
                );
              })}
            </ol>
          </Card>
        </section>
      ))}

      <VendorAckSummary weddingId={id} />
      <DayTransport weddingId={id} />
      <DayChecklist weddingId={id} canWrite={canWrite} canRun={canRun} />

      {(schedule.data?.length ?? 0) > 0 && (
        <Button variant="text" icon={<Printer aria-hidden size={20} />} onPress={() => window.print()}>
          Drukuj harmonogram
        </Button>
      )}

      <ItemSheet
        weddingId={id}
        item={editingItem}
        isOpen={adding || !!editingItem}
        events={events.data ?? []}
        defaultDay={wedding.data?.wedding_date ?? days[0]?.[0] ?? null}
        onClose={() => {
          setAdding(false);
          setEditing(null);
        }}
      />
      <TemplateSheet
        weddingId={id}
        weddingDate={wedding.data?.wedding_date ?? null}
        isOpen={template}
        onOpenChange={setTemplate}
      />
    </main>
  );
}

function ConflictNotice({ tone, title, list }: { tone: "error" | "warning"; title: string; list: ScheduleConflict[] }) {
  return (
    <Notice tone={tone} title={title}>
      <ul className="conflict-list">
        {list.map((c) => (
          <li key={`${c.code}-${c.item_ids.join("-")}`}>{c.message}</li>
        ))}
      </ul>
    </Notice>
  );
}

function useRefreshSchedule(weddingId: string) {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: keys.schedule(weddingId) }),
      queryClient.invalidateQueries({ queryKey: briefKeys.statuses(weddingId) }),
    ]);
}

/* ------------------------------------------------------------- punkt: nowy / edycja */

function ItemSheet({
  weddingId,
  item,
  isOpen,
  events,
  defaultDay,
  onClose,
}: {
  weddingId: string;
  item: ScheduleItem | null;
  isOpen: boolean;
  events: WeddingEvent[];
  defaultDay: string | null;
  onClose: () => void;
}) {
  return (
    <Sheet title={item ? "Punkt programu" : "Nowy punkt programu"} isOpen={isOpen} onOpenChange={(o) => !o && onClose()}>
      {isOpen && (
        <ItemForm
          key={item ? `${item.id}-${item.version}` : "new"}
          weddingId={weddingId}
          item={item}
          events={events}
          defaultDay={defaultDay}
          onClose={onClose}
        />
      )}
    </Sheet>
  );
}

function ItemForm({
  weddingId,
  item,
  events,
  defaultDay,
  onClose,
}: {
  weddingId: string;
  item: ScheduleItem | null;
  events: WeddingEvent[];
  defaultDay: string | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const refresh = useRefreshSchedule(weddingId);
  const toast = useToast();
  const start = item ? fromInstant(item.starts_at) : null;
  const [title, setTitle] = useState(item?.title ?? "");
  const [day, setDay] = useState<CalendarDate | null>(start?.day ?? (defaultDay ? parseDate(defaultDay) : null));
  const [time, setTime] = useState<Time | null>(start?.time ?? null);
  const [duration, setDuration] = useState(String(item?.duration_minutes ?? 30));
  const [eventId, setEventId] = useState(item?.event_id ?? NO_EVENT);
  const [location, setLocation] = useState(item?.location ?? "");
  const [who, setWho] = useState(item?.responsible_name ?? "");
  const [prep, setPrep] = useState(item?.preparations ?? "");
  const [planB, setPlanB] = useState(item?.plan_b ?? "");
  const [forGuests, setForGuests] = useState(item?.for_guests ?? false);
  const [vendorId, setVendorId] = useState(item?.vendor_id ?? NO_VENDOR);
  const vendors = useVendors(weddingId);
  const [errors, setErrors] = useState<{ title?: string; day?: string; time?: string }>({});
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const key = useRef(newIdempotencyKey());
  // Własne czasy trwania (spoza listy) też pokazujemy w wyborze.
  const durations = DURATIONS.some((d) => d.id === duration) ? DURATIONS : [...DURATIONS, { id: duration, label: `${duration} min` }];

  const save = useMutation({
    mutationFn: async () => {
      const fields = {
        title: title.trim(),
        starts_at: toInstant(day!, time!),
        duration_minutes: Number(duration),
        event_id: eventId === NO_EVENT ? null : eventId,
        location: location.trim() || null,
        responsible_name: who.trim() || null,
        preparations: prep.trim() || null,
        plan_b: planB.trim() || null,
        for_guests: forGuests,
        vendor_id: vendorId === NO_VENDOR ? null : vendorId,
      };
      if (!item) {
        return unwrap(
          api.POST("/api/v1/weddings/{wedding_id}/schedule", {
            params: { path: { wedding_id: weddingId } },
            body: { ...fields, buffer_before_minutes: 0, buffer_after_minutes: 0 },
            headers: { "Idempotency-Key": key.current },
          }),
        );
      }
      return unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/schedule/{item_id}", {
          params: { path: { wedding_id: weddingId, item_id: item.id } },
          body: fields as ItemPatch,
          headers: ifMatch(item.version),
        }),
      );
    },
    onSuccess: async (saved) => {
      await refresh();
      onClose();
      toast(item ? "Zapisano punkt programu" : `Dodano „${saved.title}”`);
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [keys.schedule(weddingId)])),
  });

  const remove = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE("/api/v1/weddings/{wedding_id}/schedule/{item_id}", {
          params: { path: { wedding_id: weddingId, item_id: item!.id } },
        }),
      ),
    onSuccess: async () => {
      setConfirmDelete(false);
      await refresh();
      onClose();
      toast(`Usunięto „${item!.title}”`);
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
          if (!title.trim()) next.title = "Wpisz, co się dzieje, np. Pierwszy taniec.";
          if (!day) next.day = "Wybierz dzień.";
          if (!time) next.time = "Wpisz godzinę.";
          setErrors(next);
          if (next.title || next.day || next.time) return;
          save.mutate();
        }}
      >
        {error && (
          <Notice tone="error" live>
            {error}
          </Notice>
        )}
        <TextField label="Co się dzieje?" value={title} onChange={setTitle} error={errors.title} isRequired autoFocus={!item} />
        <div className="stat-grid">
          <DateField label="Dzień" value={day} onChange={setDay} error={errors.day} isRequired />
          <TimeField label="Godzina" value={time} onChange={setTime} error={errors.time} isRequired />
        </div>
        <Select label="Czas trwania" options={durations} value={duration} onChange={setDuration} />
        {events.length > 0 && (
          <Select
            label="Część dnia"
            options={[{ id: NO_EVENT, label: "Bez przypisania" }, ...events.map((e) => ({ id: e.id, label: e.name }))]}
            value={eventId}
            onChange={setEventId}
          />
        )}
        <TextField label="Miejsce (opcjonalnie)" value={location} onChange={setLocation} />
        <TextField
          label="Kto pilnuje? (opcjonalnie)"
          description="Np. Świadkowa Kasia, DJ, wodzirej."
          value={who}
          onChange={setWho}
          autoComplete="off"
        />
        {(vendors.data?.length ?? 0) > 0 && (
          <Select
            label="Usługodawca (opcjonalnie)"
            description="Zobaczy ten punkt ze szczegółami w swoim linku z programem dnia."
            options={[{ id: NO_VENDOR, label: "Bez usługodawcy" }, ...(vendors.data ?? []).map((v) => ({ id: v.id, label: `${v.name} · ${v.category_label}` }))]}
            value={vendorId}
            onChange={setVendorId}
          />
        )}
        <TextField label="Do przygotowania (opcjonalnie)" value={prep} onChange={setPrep} />
        <TextField
          label="Plan B (opcjonalnie)"
          description="Co robimy, gdy pada deszcz albo coś się opóźnia, i kogo powiadomić."
          value={planB}
          onChange={setPlanB}
        />
        <Checkbox isSelected={forGuests} onChange={setForGuests}>
          Pokaż gościom (na stronie z linkiem do potwierdzenia)
        </Checkbox>
        <Button type="submit" block pending={save.isPending}>
          {item ? "Zapisz" : "Dodaj punkt"}
        </Button>
        {item && (
          <Button variant="text" onPress={() => setConfirmDelete(true)}>
            Usuń punkt
          </Button>
        )}
      </Form>
      {item && <ShiftSection weddingId={weddingId} item={item} onDone={onClose} />}
      {item && (
        <ConfirmDialog title="Usunąć punkt programu?" isOpen={confirmDelete} onOpenChange={setConfirmDelete}>
          <p>„{item.title}” zniknie z harmonogramu. Pozostałe punkty zostaną na swoich godzinach.</p>
          <div className="wp-sheet__actions">
            <Button variant="secondary" onPress={() => setConfirmDelete(false)}>
              Anuluj
            </Button>
            <Button variant="danger" pending={remove.isPending} onPress={() => remove.mutate()}>
              Usuń
            </Button>
          </div>
        </ConfirmDialog>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ tryb dnia ślubu */

/**
 * „Teraz / za chwilę” na podstawie godzin programu. Program odświeża się co 30 s, więc
 * przesunięcie zrobione przez koordynatora widzą wszyscy (także usługodawcy w swoich linkach).
 */
function LivePanel({
  weddingId,
  weddingName,
  weddingDate,
  items,
  canRun,
}: {
  weddingId: string;
  weddingName: string;
  weddingDate: string | null;
  items: ScheduleItem[];
  canRun: boolean;
}) {
  const queryClient = useQueryClient();
  const online = useOnline();
  const vendors = useVendors(weddingId);
  const key = weddingCopyKey(weddingId);
  const [hasCopy, setHasCopy] = useState(() => readDayCopy(key, todayInWarsaw()) !== null);
  const [now, setNow] = useState(() => Date.now());
  // Przesunięcia zrobione bez sieci: od razu widoczne, wysyłane po powrocie połączenia.
  const [queue, setQueue] = useState<QueuedShift[]>(() => readQueue(weddingId));
  const shown = useMemo(() => applyQueue(items, queue), [items, queue]);
  const vendorName = useMemo(() => new Map((vendors.data ?? []).map((v) => [v.id, v.name])), [vendors.data]);
  const save = useCallback(
    () =>
      saveDayCopy(key, {
        name: weddingName,
        wedding_date: weddingDate,
        items: shown.map((i) => ({ ...i, vendor_name: i.vendor_id ? (vendorName.get(i.vendor_id) ?? null) : null })),
      }),
    [key, weddingName, weddingDate, shown, vendorName],
  );
  // Kopia już jest: po każdym odświeżeniu programu (np. przesunięciu, także z kolejki) zapisujemy aktualną wersję.
  useEffect(() => {
    if (hasCopy) save();
  }, [hasCopy, save]);
  const copy = hasCopy ? readDayCopy(key, todayInWarsaw()) : null;
  useEffect(() => {
    const timer = window.setInterval(() => {
      setNow(Date.now());
      void queryClient.invalidateQueries({ queryKey: keys.schedule(weddingId) });
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [queryClient, weddingId]);
  const t = (iso: string) => new Date(iso).getTime();
  const current = shown.filter((i) => t(i.starts_at) <= now && now < Math.max(t(i.ends_at), t(i.starts_at) + 60_000));
  const next = shown.find((i) => t(i.starts_at) > now);
  const anchor = current[0] ?? next;
  return (
    <section className="form-stack live" aria-labelledby="live-h" aria-live="polite">
      <h2 id="live-h">
        Dzień ślubu na żywo <PremiumBadge />
      </h2>
      <Card className="form-stack">
        {current.length > 0 ? (
          current.map((i) => (
            <div key={i.id} className="live__item">
              <p className="overline">Teraz · do {formatTime(i.ends_at)}</p>
              <p className="live__title">{i.title}</p>
              {i.location && <p className="text-secondary">{i.location}</p>}
              {i.plan_b && <p className="plan-b">Plan B: {i.plan_b}</p>}
            </div>
          ))
        ) : (
          <p className="text-secondary">{next ? "Teraz nic nie trwa." : "Program na dziś się zakończył."}</p>
        )}
        {next && (
          <div className="live__item">
            <p className="overline">Za chwilę · {formatTime(next.starts_at)}</p>
            <p className="live__title">{next.title}</p>
            {next.preparations && <p className="text-secondary">Przygotować: {next.preparations}</p>}
          </div>
        )}
      </Card>
      {!online && (
        <Notice tone="warning" live>
          Bez połączenia{copy ? ` — program z godz. ${formatTime(copy.saved_at)}` : ""}.
          {canRun ? " Przesunięcia zapiszemy na tym telefonie i wyślemy, gdy wróci internet." : " Przesuwanie programu wymaga internetu."}
        </Notice>
      )}
      {canRun && online && anchor && queue.length === 0 && <ShiftSection weddingId={weddingId} item={anchor} onDone={() => undefined} />}
      {canRun && !online && anchor && (
        <OfflineShift
          item={anchor}
          onShift={(minutes) => setQueue(enqueueShift(weddingId, { from_item_id: anchor.id, from_title: anchor.title, minutes, base_starts_at: anchor.starts_at }))}
        />
      )}
      {canRun && queue.length > 0 && <QueueSection weddingId={weddingId} queue={queue} online={online} onChange={setQueue} />}
      <div className="form-stack offline-copy">
        {copy ? (
          <>
            <p className="text-secondary">
              Kopia programu z godz. {formatTime(copy.saved_at)} jest na tym urządzeniu — pokażemy ją, gdy zabraknie zasięgu (bez gości i kwot;
              zniknie dzień po ślubie albo po wylogowaniu).
            </p>
            <Button
              variant="text"
              onPress={() => {
                removeDayCopy(key);
                setHasCopy(false);
              }}
            >
              Usuń kopię z tego urządzenia
            </Button>
          </>
        ) : (
          <Button variant="secondary" isDisabled={!online} onPress={() => setHasCopy(save() !== null)}>
            Zapisz program na tym telefonie (na wypadek braku zasięgu)
          </Button>
        )}
      </div>
    </section>
  );
}

/* ------------------------------------------------ przesunięcia bez sieci (kolejka) */

function OfflineShift({ item, onShift }: { item: ScheduleItem; onShift: (minutes: number) => void }) {
  return (
    <section className="form-stack shift" aria-labelledby={`offline-shift-${item.id}`}>
      <h3 id={`offline-shift-${item.id}`}>Przesuń bez sieci: „{item.title}” i późniejsze</h3>
      <div className="chips">
        {SHIFTS.map((m) => (
          <Button key={m} variant="secondary" onPress={() => onShift(m)}>
            {m > 0 ? `+${m}` : `−${-m}`} min
          </Button>
        ))}
      </div>
    </section>
  );
}

/**
 * Kolejka przesunięć: po powrocie sieci wysyła je po kolei. Gdy ktoś w międzyczasie zmienił
 * program (inna godzina punktu na serwerze), zatrzymuje się i pyta, co zrobić.
 */
function QueueSection({
  weddingId,
  queue,
  online,
  onChange,
}: {
  weddingId: string;
  queue: QueuedShift[];
  online: boolean;
  onChange: (q: QueuedShift[]) => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [conflict, setConflict] = useState<{ shift: QueuedShift; serverStart: string | null } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);
  const path = { params: { path: { wedding_id: weddingId } } };

  const send = useCallback(
    async (q: QueuedShift) => {
      await unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/schedule/shift", {
          ...path,
          body: { from_item_id: q.from_item_id, minutes: q.minutes, dry_run: false },
        }),
      );
      return removeShift(weddingId, q.id);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [weddingId],
  );

  const flush = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    setError(null);
    let left = readQueue(weddingId);
    let sent = 0;
    try {
      while (left.length) {
        const q = left[0]!;
        const server = await unwrap(api.GET("/api/v1/weddings/{wedding_id}/schedule", path));
        if (!canSendSafely(q, server)) {
          setConflict({ shift: q, serverStart: server.find((i) => i.id === q.from_item_id)?.starts_at ?? null });
          break;
        }
        left = await send(q);
        sent += 1;
      }
    } catch (e) {
      setError(`Nie wysłano przesunięć. ${userMessage(e)}`);
    } finally {
      busy.current = false;
      onChange(readQueue(weddingId));
      if (sent) {
        await queryClient.invalidateQueries({ queryKey: keys.schedule(weddingId) });
        toast(plural(sent, { one: "Wysłano # przesunięcie zrobione bez sieci", few: "Wysłano # przesunięcia zrobione bez sieci", many: "Wysłano # przesunięć zrobionych bez sieci", other: "Wysłano # przesunięcia" }));
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [weddingId, send, onChange, queryClient, toast]);

  // Powrót sieci (albo rozwiązany konflikt): jedna próba wysyłki. Po błędzie nie ponawiamy w pętli —
  // „Spróbuj ponownie” albo kolejna zmiana sieci. Najnowsza funkcja w refie, efekt zależy tylko od stanu.
  const flushRef = useRef(flush);
  useEffect(() => {
    flushRef.current = flush;
  }, [flush]);
  useEffect(() => {
    if (online && !conflict) void flushRef.current();
  }, [online, conflict]);

  const resolve = async (sendAnyway: boolean) => {
    if (!conflict) return;
    try {
      onChange(sendAnyway ? await send(conflict.shift) : removeShift(weddingId, conflict.shift.id));
      if (sendAnyway) await queryClient.invalidateQueries({ queryKey: keys.schedule(weddingId) });
      setConflict(null); // efekt wznowi wysyłkę pozostałych
    } catch (e) {
      setError(`Nie wysłano. ${userMessage(e)}`);
    }
  };

  const label = (m: number) => (m > 0 ? `+${m} min` : `−${-m} min`);
  return (
    <section className="form-stack shift" aria-labelledby="queue-h" aria-live="polite">
      <h3 id="queue-h">{online ? "Wysyłamy przesunięcia zrobione bez sieci" : "Czeka na internet"}</h3>
      <ul className="row-list">
        {queue.map((q) => (
          <li key={q.id} className="row">
            <span className="row__body">
              <span className="row__title">
                „{q.from_title}” i późniejsze: {label(q.minutes)}
              </span>
              <span className="text-secondary num">zapisane o {formatTime(q.queued_at)}</span>
            </span>
            {!online && (
              <Button variant="text" aria-label={`Usuń przesunięcie: ${q.from_title} ${label(q.minutes)}`} onPress={() => onChange(removeShift(weddingId, q.id))}>
                Usuń
              </Button>
            )}
          </li>
        ))}
      </ul>
      {conflict && (
        <Notice tone="warning" title="Program zmienił się w międzyczasie" live>
          <p>
            „{conflict.shift.from_title}” ma teraz {conflict.serverStart ? `godz. ${formatTime(conflict.serverStart)}` : "inną postać (punkt usunięto)"}, a przesuwaliście od
            godz. {formatTime(conflict.shift.base_starts_at)}. Wysłać przesunięcie o {label(conflict.shift.minutes)} mimo to?
          </p>
          <div className="wp-sheet__actions">
            <Button variant="secondary" onPress={() => void resolve(false)}>
              Odrzuć
            </Button>
            {conflict.serverStart && <Button onPress={() => void resolve(true)}>Wyślij mimo to</Button>}
          </div>
        </Notice>
      )}
      {error && (
        <Notice tone="error" live>
          {error}
          <Button variant="text" onPress={() => void flush()}>
            Spróbuj ponownie
          </Button>
        </Notice>
      )}
    </section>
  );
}

/* --------------------------------------------------- przesunięcie: ten i późniejsze */

function ShiftSection({ weddingId, item, onDone }: { weddingId: string; item: ScheduleItem; onDone: () => void }) {
  const refresh = useRefreshSchedule(weddingId);
  const queryClient = useQueryClient();
  const toast = useToast();
  const [preview, setPreview] = useState<(Shift & { minutes: number }) | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = useMutation({
    mutationFn: async ({ minutes, dryRun }: { minutes: number; dryRun: boolean }) => ({
      minutes,
      ...(await unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/schedule/shift", {
          params: { path: { wedding_id: weddingId } },
          body: { from_item_id: item.id, minutes, dry_run: dryRun },
        }),
      )),
    }),
    onSuccess: async (r) => {
      setError(null);
      if (r.dry_run) {
        setPreview(r);
        return;
      }
      setPreview(null);
      await Promise.all([refresh(), queryClient.invalidateQueries({ queryKey: keys.scheduleConflicts(weddingId) })]);
      onDone();
      toast(plural(r.changes.length, { one: "Przesunięto # punkt", few: "Przesunięto # punkty", many: "Przesunięto # punktów", other: "Przesunięto # punktu" }));
    },
    onError: (e) => {
      setPreview(null);
      setError(saveErrorMessage(e, queryClient, [keys.schedule(weddingId)]));
    },
  });

  const label = (m: number) => (m < 0 ? `${-m} min wcześniej` : `${m} min później`);

  return (
    <section className="form-stack shift" aria-labelledby={`shift-${item.id}`}>
      <h3 id={`shift-${item.id}`}>Przesuń ten i wszystkie późniejsze</h3>
      <p className="text-secondary">Np. ceremonia się opóźnia — reszta dnia przesunie się razem z nią.</p>
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      <div className="chips">
        {SHIFTS.map((m) => (
          <Button
            key={m}
            variant="secondary"
            pending={run.isPending && run.variables?.minutes === m && run.variables.dryRun}
            onPress={() => run.mutate({ minutes: m, dryRun: true })}
          >
            {m > 0 ? `+${m}` : `−${-m}`} min
          </Button>
        ))}
      </div>
      <ConfirmDialog title="Przesunąć program?" isOpen={!!preview} onOpenChange={(o) => !o && setPreview(null)}>
        {preview && (
          <>
            <p>
              {label(preview.minutes)}:{" "}
              {plural(preview.changes.length, { one: "# punkt", few: "# punkty", many: "# punktów", other: "# punktu" })}.
            </p>
            <ul className="row-list reschedule-list">
              {preview.changes.slice(0, 8).map((c) => (
                <li key={c.item_id} className="row">
                  <span className="row__body">
                    <span className="row__title">{c.title}</span>
                    <span className="text-secondary num">
                      {formatTime(c.old_starts_at)} → {formatTime(c.new_starts_at)}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
            {preview.changes.length > 8 && <p className="text-secondary">…i {preview.changes.length - 8} kolejnych.</p>}
            {preview.conflicts_after.length > 0 && (
              <Notice tone="warning" title="Po przesunięciu">
                <ul className="conflict-list">
                  {preview.conflicts_after.map((c) => (
                    <li key={`${c.code}-${c.item_ids.join("-")}`}>{c.message}</li>
                  ))}
                </ul>
              </Notice>
            )}
            <div className="wp-sheet__actions">
              <Button variant="secondary" onPress={() => setPreview(null)}>
                Anuluj
              </Button>
              <Button pending={run.isPending} onPress={() => run.mutate({ minutes: preview.minutes, dryRun: false })}>
                Przesuń
              </Button>
            </div>
          </>
        )}
      </ConfirmDialog>
    </section>
  );
}

/* ------------------------------------------------------------------ typowy program */

function TemplateSheet({
  weddingId,
  weddingDate,
  isOpen,
  onOpenChange,
}: {
  weddingId: string;
  weddingDate: string | null;
  isOpen: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [day, setDay] = useState<CalendarDate | null>(weddingDate ? parseDate(weddingDate) : null);
  const [time, setTime] = useState<Time | null>(null);
  const [preview, setPreview] = useState<Template | null>(null);
  const [errors, setErrors] = useState<{ day?: string; time?: string }>({});

  const run = useMutation({
    mutationFn: (dryRun: boolean) =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/schedule/from-template", {
          params: { path: { wedding_id: weddingId } },
          body: {
            day: day!.toString(),
            ceremony_time: `${String(time!.hour).padStart(2, "0")}:${String(time!.minute).padStart(2, "0")}`,
            dry_run: dryRun,
          },
        }),
      ),
    onSuccess: async (r) => {
      if (r.dry_run) {
        setPreview(r);
        return;
      }
      setPreview(null);
      onOpenChange(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.schedule(weddingId) }),
        queryClient.invalidateQueries({ queryKey: keys.scheduleConflicts(weddingId) }),
      ]);
      toast(plural(r.items.length, { one: "Dodano # punkt", few: "Dodano # punkty", many: "Dodano # punktów", other: "Dodano # punktu" }));
    },
  });

  return (
    <Sheet title="Typowy program dnia" isOpen={isOpen} onOpenChange={onOpenChange}>
      {preview ? (
        <div className="form-stack">
          <p className="text-secondary">{preview.note}</p>
          <ol className="row-list timeline">
            {preview.items.map((s) => (
              <li key={`${s.title}-${s.starts_at}`} className="row">
                <span className="timeline__row">
                  <TimeCell item={{ starts_at: s.starts_at, ends_at: s.starts_at, duration_minutes: 0 }} />
                  <span className="row__body">
                    <span className="row__title">{s.title}</span>
                  </span>
                </span>
              </li>
            ))}
          </ol>
          {run.isError && (
            <Notice tone="error" live>
              {userMessage(run.error)}
            </Notice>
          )}
          <div className="wp-sheet__actions">
            <Button variant="secondary" onPress={() => setPreview(null)}>
              Wróć
            </Button>
            <Button pending={run.isPending} onPress={() => run.mutate(false)}>
              Wstaw do harmonogramu
            </Button>
          </div>
        </div>
      ) : (
        <Form
          className="form-stack"
          validationBehavior="aria"
          onSubmit={(e) => {
            e.preventDefault();
            const next: typeof errors = {};
            if (!day) next.day = "Wybierz dzień ślubu.";
            if (!time) next.time = "Wpisz godzinę ceremonii, np. 15:00.";
            setErrors(next);
            if (next.day || next.time) return;
            run.mutate(true);
          }}
        >
          {run.isError && (
            <Notice tone="error" live>
              {userMessage(run.error)}
            </Notice>
          )}
          <p className="text-secondary">Wszystkie godziny liczymy od początku ceremonii.</p>
          <DateField label="Dzień ślubu" value={day} onChange={setDay} error={errors.day} isRequired />
          <TimeField label="Godzina ceremonii" value={time} onChange={setTime} error={errors.time} isRequired />
          <Button type="submit" block pending={run.isPending}>
            Pokaż program
          </Button>
        </Form>
      )}
    </Sheet>
  );
}
