import { parseDate, type CalendarDate, type Time } from "@internationalized/date";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useRef, useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { DateField, TimeField } from "../../components/DateField";
import { TextField } from "../../components/Field";
import { ConfirmDialog, Sheet } from "../../components/Overlay";
import { Select } from "../../components/Select";
import { Card, Notice, Skeleton } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { eventWhen } from "../../lib/format";
import { keys, useEvents, type Wedding, type WeddingEvent } from "./data";
import { ifMatch, saveErrorMessage } from "./mutations";
import { fromInstant, toInstant } from "./ScheduleView";

type EventKind = components["schemas"]["EventCreate"]["kind"];
type EventPatch = components["schemas"]["EventUpdate"];

export const KINDS: { id: EventKind; label: string }[] = [
  { id: "ceremony", label: "Ceremonia" },
  { id: "reception", label: "Przyjęcie" },
  { id: "after_party", label: "Poprawiny" },
  { id: "other", label: "Inne" },
];

/**
 * Wydarzenia wesela: na nie goście odpowiadają (RSVP) i do nich przypisany jest harmonogram.
 * Świeże wesele nie ma żadnego — bez nich formularz gości nie ma o co pytać.
 */
export function EventsSection({ wedding: w, canWrite }: { wedding: Wedding; canWrite: boolean }) {
  const events = useEvents(w.id);
  const queryClient = useQueryClient();
  const toast = useToast();
  const [editing, setEditing] = useState<WeddingEvent | "new" | null>(null);
  const quickKey = useRef([newIdempotencyKey(), newIdempotencyKey()]);

  // Szybki start: ceremonia i przyjęcie (godziny dopisze się później).
  const quick = useMutation({
    mutationFn: async () => {
      const base: { kind: EventKind; name: string }[] = [
        { kind: "ceremony", name: w.ceremony_type === "civil" ? "Ślub cywilny" : "Ceremonia ślubna" },
        { kind: "reception", name: "Przyjęcie weselne" },
      ];
      for (const [i, e] of base.entries()) {
        await unwrap(
          api.POST("/api/v1/weddings/{wedding_id}/events", {
            params: { path: { wedding_id: w.id } },
            body: e,
            headers: { "Idempotency-Key": quickKey.current[i]! },
          }),
        );
      }
    },
    onSuccess: async () => {
      quickKey.current = [newIdempotencyKey(), newIdempotencyKey()];
      await queryClient.invalidateQueries({ queryKey: keys.events(w.id) });
      toast("Dodano ceremonię i przyjęcie");
    },
  });

  return (
    <section aria-labelledby="events-h" className="form-stack">
      <div className="section-head">
        <h2 id="events-h">Wydarzenia</h2>
        {canWrite && (events.data?.length ?? 0) > 0 && (
          <Button variant="text" icon={<Plus aria-hidden size={18} />} onPress={() => setEditing("new")}>
            Dodaj
          </Button>
        )}
      </div>
      <Card className="form-stack">
        {events.isPending && <Skeleton lines={2} />}
        {events.data?.length === 0 && (
          <>
            <p className="text-secondary">
              Goście odpowiadają osobno na każde wydarzenie (np. ceremonia, przyjęcie, poprawiny). Dodajcie przynajmniej jedno,
              zanim wyślecie linki do odpowiedzi.
            </p>
            {quick.isError && (
              <Notice tone="error" live>
                {userMessage(quick.error)}
              </Notice>
            )}
            {canWrite && (
              <>
                <Button pending={quick.isPending} onPress={() => quick.mutate()}>
                  Dodaj ceremonię i przyjęcie
                </Button>
                <Button variant="text" onPress={() => setEditing("new")}>
                  Dodaj inne wydarzenie
                </Button>
              </>
            )}
          </>
        )}
        {(events.data?.length ?? 0) > 0 && (
          <ul className="row-list">
            {events.data!.map((e) => {
              const body = (
                <>
                  <span className="row__title">{e.name}</span>
                  <span className="text-secondary">
                    {[eventWhen(e.starts_at) ?? "Godzina do ustalenia", e.address].filter(Boolean).join(" · ")}
                  </span>
                </>
              );
              return (
                <li key={e.id} className="row">
                  {canWrite ? (
                    <AriaButton className="row-edit" onPress={() => setEditing(e)}>
                      {body}
                    </AriaButton>
                  ) : (
                    <div className="row__body">{body}</div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Card>
      <Sheet
        title={editing === "new" ? "Nowe wydarzenie" : "Wydarzenie"}
        isOpen={!!editing}
        onOpenChange={(o) => !o && setEditing(null)}
      >
        {editing && (
          <EventForm
            key={editing === "new" ? "new" : `${editing.id}-${editing.version}`}
            wedding={w}
            event={editing === "new" ? null : editing}
            onClose={() => setEditing(null)}
          />
        )}
      </Sheet>
    </section>
  );
}

function EventForm({ wedding: w, event, onClose }: { wedding: Wedding; event: WeddingEvent | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const start = event?.starts_at ? fromInstant(event.starts_at) : null;
  const end = event?.ends_at ? fromInstant(event.ends_at) : null;
  const [kind, setKind] = useState<string>(event?.kind ?? "reception");
  const [name, setName] = useState(event?.name ?? "");
  const [day, setDay] = useState<CalendarDate | null>(start?.day ?? (w.wedding_date ? parseDate(w.wedding_date) : null));
  const [from, setFrom] = useState<Time | null>(start?.time ?? null);
  const [to, setTo] = useState<Time | null>(end?.time ?? null);
  const [address, setAddress] = useState(event?.address ?? "");
  const [errors, setErrors] = useState<{ name?: string; from?: string }>({});
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const key = useRef(newIdempotencyKey());
  const refresh = () =>
    Promise.all(
      [keys.events(w.id), keys.households(w.id), keys.guestStats(w.id), keys.schedule(w.id)].map((queryKey) =>
        queryClient.invalidateQueries({ queryKey }),
      ),
    );

  const save = useMutation({
    mutationFn: () => {
      const startsAt = day && from ? toInstant(day, from) : null;
      // Koniec przed początkiem = po północy (np. przyjęcie 17:00–4:00).
      let endsAt: string | null = null;
      if (day && from && to) {
        endsAt = toInstant(to.compare(from) <= 0 ? day.add({ days: 1 }) : day, to);
      }
      const fields = {
        kind: kind as EventKind,
        name: name.trim(),
        starts_at: startsAt,
        ends_at: endsAt,
        address: address.trim() || null,
      };
      if (!event) {
        return unwrap(
          api.POST("/api/v1/weddings/{wedding_id}/events", {
            params: { path: { wedding_id: w.id } },
            body: fields,
            headers: { "Idempotency-Key": key.current },
          }),
        );
      }
      return unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/events/{event_id}", {
          params: { path: { wedding_id: w.id, event_id: event.id } },
          body: fields as EventPatch,
          headers: ifMatch(event.version),
        }),
      );
    },
    onSuccess: async (saved) => {
      await refresh();
      onClose();
      toast(event ? "Zapisano wydarzenie" : `Dodano „${saved.name}”`);
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [keys.events(w.id)])),
  });

  const remove = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE("/api/v1/weddings/{wedding_id}/events/{event_id}", {
          params: { path: { wedding_id: w.id, event_id: event!.id } },
        }),
      ),
    onSuccess: async () => {
      setConfirmDelete(false);
      await refresh();
      onClose();
      toast(`Usunięto „${event!.name}”`);
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
          if (!name.trim()) next.name = "Wpisz nazwę, np. Przyjęcie weselne.";
          if (to && !from) next.from = "Podaj też godzinę rozpoczęcia.";
          setErrors(next);
          if (next.name || next.from) return;
          save.mutate();
        }}
      >
        {error && (
          <Notice tone="error" live>
            {error}
          </Notice>
        )}
        <Select
          label="Rodzaj"
          options={KINDS}
          value={kind}
          onChange={(v) => {
            setKind(v);
            if (!name.trim()) setName(KINDS.find((k) => k.id === v)?.label ?? "");
          }}
        />
        <TextField label="Nazwa (widzą ją goście)" value={name} onChange={setName} error={errors.name} isRequired />
        <DateField label="Dzień" value={day} onChange={setDay} />
        <div className="stat-grid">
          <TimeField label="Początek" value={from} onChange={setFrom} error={errors.from} />
          <TimeField label="Koniec (opcjonalnie)" value={to} onChange={setTo} />
        </div>
        <TextField
          label="Adres (widzą go goście)"
          description="Np. Kościół św. Anny, ul. Krakowskie Przedmieście 68, Warszawa."
          value={address}
          onChange={setAddress}
        />
        <Button type="submit" block pending={save.isPending}>
          {event ? "Zapisz" : "Dodaj wydarzenie"}
        </Button>
        {event && (
          <Button variant="text" onPress={() => setConfirmDelete(true)}>
            Usuń wydarzenie
          </Button>
        )}
      </Form>
      {event && (
        <ConfirmDialog title="Usunąć wydarzenie?" isOpen={confirmDelete} onOpenChange={setConfirmDelete}>
          <p>
            „{event.name}” zniknie razem z odpowiedziami gości na to wydarzenie. Punkty harmonogramu zostaną, tylko bez
            przypisania.
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
      )}
    </>
  );
}
