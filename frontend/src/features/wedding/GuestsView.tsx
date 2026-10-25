import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Plus } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import {
  Button as AriaButton,
  Disclosure,
  DisclosurePanel,
  Form,
  Heading,
  Input,
  Label,
  SearchField,
} from "react-aria-components";
import { Link, useSearchParams } from "react-router";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { downloadAuthorized } from "../../api/download";
import { userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { Checkbox, TextField } from "../../components/Field";
import { ConfirmDialog, Sheet } from "../../components/Overlay";
import { Segmented } from "../../components/Segmented";
import { Select } from "../../components/Select";
import { Card, EmptyState, Notice, Skeleton, StatusChip, type Tone } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { plural } from "../../lib/format";
import { GuestImportSheet } from "./GuestImport";
import { RsvpEmailsSheet } from "./RsvpEmailsSheet";
import { GUEST_SECTIONS, PrintLink, SectionNav } from "./SectionNav";
import { EditGuestSheet, EditHouseholdSheet, fullName, SIDES } from "./EditGuestSheet";
import {
  keys,
  useCanWrite,
  useEvents,
  useGuestStats,
  useHouseholds,
  useWeddingId,
  type Guest,
  type Household,
  type WeddingEvent,
} from "./data";

type Status = "attending" | "declined" | "maybe" | "pending";
type Filter = "wszyscy" | "bez-odpowiedzi" | "nie-wiedza" | "odmowy" | "do-wreczenia" | "nocleg-transport";

export const STATUS: Record<Status, { label: string; tone: Tone }> = {
  attending: { label: "Będzie", tone: "success" },
  declined: { label: "Nie będzie", tone: "neutral" },
  maybe: { label: "Jeszcze nie wie", tone: "info" },
  pending: { label: "Bez odpowiedzi", tone: "warning" },
};

const FILTERS: { value: Filter; label: string; status?: Status; match?: (h: Household) => boolean }[] = [
  { value: "wszyscy", label: "Wszyscy" },
  { value: "bez-odpowiedzi", label: "Bez odpowiedzi", status: "pending" },
  { value: "nie-wiedza", label: "Nie wiedzą", status: "maybe" },
  { value: "odmowy", label: "Odmowy", status: "declined" },
  // Zaproszenia do wręczenia osobiście i goście z potrzebą noclegu lub transportu.
  { value: "do-wreczenia", label: "Do wręczenia", match: (h) => h.delivery_method === "in_person" && h.invitation_status !== "delivered" },
  { value: "nocleg-transport", label: "Nocleg / transport", match: (h) => h.guests.some((g) => g.needs_accommodation || g.needs_transport) },
];

/** Wyszukiwanie bez względu na wielkość liter i polskie znaki („Zielinska” znajdzie „Zielińska”). */
export function normalize(s: string): string {
  return s
    .toLocaleLowerCase("pl-PL")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/ł/g, "l");
}

/** Status osoby na wydarzeniu (brak wpisu = brak odpowiedzi, nie odmowa). */
export function statusOf(g: Guest, eventId: string | undefined): Status {
  if (!eventId) return "pending";
  return ((g.attendance as Record<string, Status>)[eventId] ?? "pending") as Status;
}

export function GuestsView() {
  const id = useWeddingId();
  const households = useHouseholds(id);
  const events = useEvents(id);
  const stats = useGuestStats(id);
  const canWrite = useCanWrite(id);
  const [params, setParams] = useSearchParams();
  const filter = (params.get("filtr") as Filter) || "wszyscy";
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [adding, setAdding] = useState(false);
  const [importing, setImporting] = useState(false);
  const [emailing, setEmailing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [answering, setAnswering] = useState<Guest | null>(null);
  // Trzymamy identyfikatory, a dane bierzemy z listy: po dodaniu osoby arkusz widzi świeży stan.
  const [editingGuest, setEditingGuest] = useState<{ guestId: string; householdId: string } | null>(null);
  const [editingHousehold, setEditingHousehold] = useState<string | null>(null);
  const householdEdit = households.data?.find((h) => h.id === editingHousehold) ?? null;
  const guestEdit = useMemo(() => {
    const household = households.data?.find((h) => h.id === editingGuest?.householdId);
    const guest = household?.guests.find((g) => g.id === editingGuest?.guestId);
    return guest && household ? { guest, household } : null;
  }, [households.data, editingGuest]);

  const mainEvent = useMemo(
    () => (events.data ?? []).find((e) => e.kind === "reception") ?? events.data?.[0],
    [events.data],
  );
  const mainStats = stats.data?.events.find((e) => e.event_id === mainEvent?.id);

  const visible = useMemo(() => {
    const q = normalize(query.trim());
    const chosen = FILTERS.find((f) => f.value === filter);
    const wanted = chosen?.status;
    return (households.data ?? []).filter((h) => {
      const matches = !q || normalize(h.name).includes(q) || h.guests.some((g) => normalize(fullName(g)).includes(q));
      const status = !wanted || h.guests.some((g) => statusOf(g, mainEvent?.id) === wanted);
      return matches && status && (!chosen?.match || chosen.match(h));
    });
  }, [households.data, query, filter, mainEvent]);

  const setParam = (key: string, value: string) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      },
      { replace: true },
    );

  return (
    <main className="page enter-tab" aria-labelledby="guests-h">
      <SectionNav label="Goście" sections={GUEST_SECTIONS} />
      <div className="view-head">
        <div>
          <h1 id="guests-h">Goście</h1>
          <p className="text-secondary">Wszyscy bliscy. Wszystkie odpowiedzi.</p>
        </div>
        <div className="seating-actions">
          {canWrite && (
            <Button variant="secondary" icon={<Plus aria-hidden size={20} />} onPress={() => setAdding(true)}>
              Dodaj zaproszenie
            </Button>
          )}
          {canWrite && (
            <Button variant="text" onPress={() => setImporting(true)}>
              Import z pliku
            </Button>
          )}
          <details className="action-menu">
            <summary>Więcej działań</summary>
            <div className="action-menu__items">
          <PrintLink kind="goscie">Drukuj listę</PrintLink>
          {canWrite && <PrintLink kind="qr">Karty z kodem QR</PrintLink>}
          {canWrite && (
            <Button variant="text" onPress={() => setExporting(true)}>
              Pobierz do Excela (CSV)
            </Button>
          )}
          {canWrite && (
            <Button variant="text" onPress={() => setEmailing(true)}>
              Wyślij linki e-mailem
            </Button>
          )}
          <Link to={`/w/${id}/strona-goscia`} viewTransition className="wp-button wp-button--text">
            Strona gościa
          </Link>
            </div>
          </details>
        </div>
      </div>

      {mainStats && (
        <Card aria-label={`Odpowiedzi: ${mainStats.name}`}>
          <div className="stat-grid">
            <Stat value={mainStats.attending} label="Będą" tone="ok" />
            <Stat value={mainStats.pending} label="Bez odpowiedzi" tone="warn" />
            <Stat value={mainStats.maybe} label="Nie wiedzą" tone="neutral" />
            <Stat value={mainStats.declined} label="Odmowy" tone="neutral" />
          </div>
          <p className="text-secondary" style={{ marginTop: "var(--wp-space-3)" }}>
            {mainStats.name} · brak odpowiedzi nie oznacza odmowy.
          </p>
        </Card>
      )}
      {events.data && !mainEvent && (
        <Notice tone="info">Dodajcie wydarzenie (np. przyjęcie), aby zbierać odpowiedzi gości.</Notice>
      )}

      <SearchField
        className="wp-field"
        value={query}
        onChange={(v) => {
          setQuery(v);
          setParam("q", v);
        }}
      >
        <Label className="wp-field__label">Szukaj osoby lub rodziny</Label>
        <Input className="wp-field__input" placeholder="np. Kowalscy, Zosia" />
      </SearchField>

      <Segmented
        label="Pokaż"
        variant="chips"
        value={filter}
        options={FILTERS}
        onChange={(v) => setParam("filtr", v === "wszyscy" ? "" : v)}
      />

      {households.isPending && <Skeleton lines={6} />}
      {households.isError && (
        <Notice tone="error" title="Nie udało się wczytać gości." live>
          {userMessage(households.error)}
        </Notice>
      )}
      {households.data && households.data.length === 0 && (
        <EmptyState
          title="Lista gości jest pusta"
          action={canWrite ? <Button onPress={() => setAdding(true)}>Dodaj pierwsze zaproszenie</Button> : undefined}
        >
          Jedno zaproszenie to jedna rodzina lub para, np. „Państwo Kowalscy z dziećmi”.
        </EmptyState>
      )}
      {households.data && households.data.length > 0 && (
        <section aria-labelledby="inv-h" className="form-stack">
          <div className="section-head">
            <h2 id="inv-h">Zaproszenia</h2>
            <span className="text-secondary num" aria-live="polite">
              {plural(visible.length, { one: "# zaproszenie", few: "# zaproszenia", many: "# zaproszeń", other: "# zaproszenia" })}
            </span>
          </div>
          {visible.length === 0 ? (
            <p className="text-secondary">Nikt nie pasuje do wyszukiwania.</p>
          ) : (
            visible.map((h) => (
              <HouseholdCard
                key={h.id}
                household={h}
                events={events.data ?? []}
                mainEventId={mainEvent?.id}
                canWrite={canWrite}
                onAnswer={setAnswering}
                onEditGuest={(g, h) => setEditingGuest({ guestId: g.id, householdId: h.id })}
                onEditHousehold={(h) => setEditingHousehold(h.id)}
              />
            ))
          )}
        </section>
      )}

      <NewHouseholdSheet weddingId={id} isOpen={adding} onOpenChange={setAdding} />
      <GuestImportSheet weddingId={id} isOpen={importing} onClose={() => setImporting(false)} />
      <AnswerSheet weddingId={id} guest={answering} events={events.data ?? []} onClose={() => setAnswering(null)} />
      <EditGuestSheet
        weddingId={id}
        guest={guestEdit?.guest ?? null}
        household={guestEdit?.household}
        onClose={() => setEditingGuest(null)}
      />
      <EditHouseholdSheet weddingId={id} household={householdEdit} onClose={() => setEditingHousehold(null)} />
      <ThanksSection households={households.data ?? []} onEdit={setEditingHousehold} />
      <RsvpEmailsSheet weddingId={id} isOpen={emailing} onClose={() => setEmailing(false)} />
      <ExportCsvDialog weddingId={id} isOpen={exporting} onClose={() => setExporting(false)} />
    </main>
  );
}

function Stat({ value, label, tone }: { value: number; label: string; tone: "ok" | "warn" | "neutral" }) {
  return (
    <div className="stat">
      <span className={`stat__value stat__value--${tone}`}>{value}</span>
      <span className="text-secondary">{label}</span>
    </div>
  );
}

function HouseholdCard({
  household: h,
  events,
  mainEventId,
  canWrite,
  onAnswer,
  onEditGuest,
  onEditHousehold,
}: {
  household: Household;
  events: WeddingEvent[];
  mainEventId: string | undefined;
  canWrite: boolean;
  onAnswer: (g: Guest) => void;
  onEditGuest: (g: Guest, h: Household) => void;
  onEditHousehold: (h: Household) => void;
}) {
  const statuses = h.guests.map((g) => statusOf(g, mainEventId));
  const attending = statuses.filter((s) => s === "attending").length;
  const summary: { tone: Tone; label: string } =
    attending > 0
      ? { tone: "success", label: plural(attending, { one: "# będzie", few: "# będą", many: "# będzie", other: "# będzie" }) }
      : statuses.every((s) => s === "declined") && statuses.length > 0
        ? STATUS.declined
        : statuses.some((s) => s === "maybe")
          ? STATUS.maybe
          : STATUS.pending;

  return (
    <Disclosure className="wp-card household">
      <Heading level={3} className="household__heading">
        <AriaButton slot="trigger" className="household__trigger">
          <span className="row__body">
            <span className="household__name">{h.name}</span>
            <span className="text-secondary">
              {h.guests.map((g) => (g.added_via_rsvp ? `${g.first_name} (dopisana przez gości)` : g.first_name)).join(", ") || "Brak osób"}
            </span>
            {events.length > 1 && (
              <span className="text-secondary num">
                {events
                  .map((e) => `${e.name}: ${h.guests.filter((g) => statusOf(g, e.id) === "attending").length}`)
                  .join(" · ")}
              </span>
            )}
          </span>
          <StatusChip tone={summary.tone}>{summary.label}</StatusChip>
          <ChevronDown aria-hidden size={20} className="household__chevron" />
        </AriaButton>
      </Heading>
      <DisclosurePanel className="household__panel">
        <ul className="row-list">
          {h.guests.map((g) => (
            <li key={g.id} className="row">
              <div className="row__body">
                {canWrite ? (
                  // Dotknięcie imienia otwiera edycję osoby (nazwa przycisku = widoczne imię).
                  <AriaButton className="row-edit row-edit--inline" onPress={() => onEditGuest(g, h)}>
                    <span className="row__title">{fullName(g)}</span>
                  </AriaButton>
                ) : (
                  <span className="row__title">{fullName(g)}</span>
                )}
                <span className="chips">
                  {events.map((e) => {
                    const s = statusOf(g, e.id);
                    return (
                      <StatusChip key={e.id} tone={STATUS[s].tone}>
                        {e.name}: {STATUS[s].label.toLocaleLowerCase("pl-PL")}
                      </StatusChip>
                    );
                  })}
                </span>
              </div>
              {canWrite && events.length > 0 && (
                <Button variant="text" onPress={() => onAnswer(g)} aria-label={`Odpowiedz za: ${fullName(g)}`}>
                  Odpowiedz
                </Button>
              )}
            </li>
          ))}
        </ul>
        {canWrite && (
          <Button variant="text" onPress={() => onEditHousehold(h)}>
            Edytuj zaproszenie
          </Button>
        )}
      </DisclosurePanel>
    </Disclosure>
  );
}

const ANSWERS: { value: Status; label: string }[] = [
  { value: "attending", label: "Będzie" },
  { value: "declined", label: "Nie będzie" },
  { value: "maybe", label: "Nie wie" },
  { value: "pending", label: "Brak" },
];

/** Odpowiedź wpisana przez parę (np. po telefonie od cioci) — osobno na każde wydarzenie. */
function AnswerSheet({ weddingId, guest, events, onClose }: { weddingId: string; guest: Guest | null; events: WeddingEvent[]; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: ({ eventId, status }: { eventId: string; status: Status }) =>
      unwrap(
        api.PUT("/api/v1/weddings/{wedding_id}/guests/{guest_id}/attendance/{event_id}", {
          params: { path: { wedding_id: weddingId, guest_id: guest!.id, event_id: eventId } },
          body: { status },
        }),
      ),
    onSuccess: async (g) => {
      setError(null);
      queryClient.setQueryData<Household[]>(keys.households(weddingId), (list) =>
        list?.map((h) => ({ ...h, guests: h.guests.map((x) => (x.id === g.id ? g : x)) })),
      );
      void queryClient.invalidateQueries({ queryKey: keys.guestStats(weddingId) });
      void queryClient.invalidateQueries({ queryKey: keys.summary(weddingId) });
      toast("Zapisano odpowiedź");
    },
    onError: (e) => setError(`Nie zapisano. ${userMessage(e)}`),
  });
  const current = queryClient
    .getQueryData<Household[]>(keys.households(weddingId))
    ?.flatMap((h) => h.guests)
    .find((g) => g.id === guest?.id);

  return (
    <Sheet title={guest ? `Odpowiedź: ${fullName(guest)}` : "Odpowiedź"} isOpen={!!guest} onOpenChange={(o) => !o && onClose()}>
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      {current &&
        events.map((e) => (
          <Segmented
            key={e.id}
            label={e.name}
            value={statusOf(current, e.id)}
            options={ANSWERS}
            onChange={(status) => save.mutate({ eventId: e.id, status })}
          />
        ))}
      <Button block variant="secondary" onPress={onClose}>
        Gotowe
      </Button>
    </Sheet>
  );
}

function NewHouseholdSheet({ weddingId, isOpen, onOpenChange }: { weddingId: string; isOpen: boolean; onOpenChange: (o: boolean) => void }) {
  const [name, setName] = useState("");
  const [people, setPeople] = useState("");
  const [side, setSide] = useState<string>("both");
  const [errors, setErrors] = useState<{ name?: string; people?: string }>({});
  const keysRef = useRef({ household: newIdempotencyKey(), guests: [] as string[] });
  const queryClient = useQueryClient();
  const toast = useToast();

  const names = people
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  const create = useMutation({
    mutationFn: async () => {
      // Ponowienie po błędzie sieci używa tych samych kluczy: bez duplikatów zaproszeń i osób.
      const h = await unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/households", {
          params: { path: { wedding_id: weddingId } },
          body: { name: name.trim(), side: side as "both", invitation_status: "not_sent" },
          headers: { "Idempotency-Key": keysRef.current.household },
        }),
      );
      for (const [i, full] of names.entries()) {
        keysRef.current.guests[i] ??= newIdempotencyKey();
        const [first, ...rest] = full.split(/\s+/);
        await unwrap(
          api.POST("/api/v1/weddings/{wedding_id}/households/{household_id}/guests", {
            params: { path: { wedding_id: weddingId, household_id: h.id } },
            body: {
              first_name: first ?? full,
              last_name: rest.join(" ") || null,
              age_group: "adult",
              is_plus_one: false,
              dietary_preference: "standard",
              needs_accommodation: false,
              needs_transport: false,
            },
            headers: { "Idempotency-Key": keysRef.current.guests[i]! },
          }),
        );
      }
      return h;
    },
    onSuccess: async (h) => {
      keysRef.current = { household: newIdempotencyKey(), guests: [] };
      setName("");
      setPeople("");
      setSide("both");
      onOpenChange(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.households(weddingId) }),
        queryClient.invalidateQueries({ queryKey: keys.guestStats(weddingId) }),
        queryClient.invalidateQueries({ queryKey: keys.summary(weddingId) }),
      ]);
      toast(`Dodano zaproszenie „${h.name}”`);
    },
  });

  return (
    <Sheet
      title="Nowe zaproszenie"
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      isDirty={(name.trim() !== "" || people.trim() !== "") && !create.isPending}
    >
      <Form
        className="form-stack"
        validationBehavior="aria"
        onSubmit={(e) => {
          e.preventDefault();
          const next: typeof errors = {};
          if (!name.trim()) next.name = "Wpisz nazwę zaproszenia, np. Państwo Kowalscy.";
          if (names.length === 0) next.people = "Wpisz przynajmniej jedną osobę.";
          setErrors(next);
          if (next.name || next.people) return;
          create.mutate();
        }}
      >
        {create.isError && (
          <Notice tone="error" title="Nie zapisano wszystkiego." live>
            {userMessage(create.error)} Spróbuj ponownie — już dodane osoby nie zdublują się.
          </Notice>
        )}
        <TextField label="Nazwa zaproszenia" value={name} onChange={setName} error={errors.name} isRequired autoFocus />
        <TextField
          label="Osoby"
          description="Imiona (i nazwiska) oddzielone przecinkami, np. Joanna Kowalska, Piotr, Zosia."
          value={people}
          onChange={setPeople}
          error={errors.people}
          isRequired
        />
        <Select label="Strona" options={SIDES} value={side} onChange={setSide} />
        <Button type="submit" block pending={create.isPending}>
          Dodaj zaproszenie
        </Button>
      </Form>
    </Sheet>
  );
}

/** Prezenty i podziękowania: widoczne, gdy para zapisała choć jeden prezent. */
function ThanksSection({ households, onEdit }: { households: Household[]; onEdit: (id: string) => void }) {
  const withGift = households.filter((h) => h.gift_note || h.thanked);
  if (withGift.length === 0) return null;
  const done = withGift.filter((h) => h.thanked).length;
  return (
    <section className="form-stack" aria-labelledby="thanks-h">
      <div className="section-head">
        <h2 id="thanks-h">Prezenty i podziękowania</h2>
        <span className="text-secondary num">
          {done} z {withGift.length} podziękowań
        </span>
      </div>
      <Card>
        <ul className="row-list">
          {withGift.map((h) => (
            <li key={h.id}>
              <AriaButton className="row row-edit calendar-entry" onPress={() => onEdit(h.id)}>
                <span className="row__body">
                  <span className="row__title">{h.name}</span>
                  <span className="text-secondary">{h.gift_note ?? "Bez opisu prezentu"}</span>
                </span>
                <StatusChip tone={h.thanked ? "success" : "warning"}>{h.thanked ? "Podziękowane" : "Do podziękowania"}</StatusChip>
              </AriaButton>
            </li>
          ))}
        </ul>
      </Card>
    </section>
  );
}

/** Lista gości do Excela; uwagi dietetyczne (dane o zdrowiu) tylko po świadomym zaznaczeniu. */
function ExportCsvDialog({ weddingId, isOpen, onClose }: { weddingId: string; isOpen: boolean; onClose: () => void }) {
  const [notes, setNotes] = useState(false);
  const toast = useToast();
  const download = useMutation({
    mutationFn: () =>
      downloadAuthorized(`/api/v1/weddings/${weddingId}/guests/export.csv${notes ? "?include_notes=true" : ""}`, "goscie.csv"),
    onSuccess: () => {
      onClose();
      setNotes(false);
      toast("Pobrano listę gości (CSV)");
    },
  });
  return (
    <ConfirmDialog title="Lista gości do Excela" isOpen={isOpen} onOpenChange={(o) => !o && onClose()}>
      <p>Plik CSV otworzycie w Excelu lub Arkuszach Google: zaproszenie, osoby, wiek, odpowiedź, dieta, stół i miejsce, nocleg i transport.</p>
      <Checkbox isSelected={notes} onChange={setNotes}>
        Dołącz uwagi dla kuchni (np. alergie)
      </Checkbox>
      {notes && (
        <Notice tone="warning">
          Uwagi mogą dotyczyć zdrowia. Przekazujcie plik tylko osobom, które przygotowują posiłki, i usuńcie go po weselu.
        </Notice>
      )}
      {download.isError && (
        <Notice tone="error" live>
          {userMessage(download.error)}
        </Notice>
      )}
      <div className="wp-sheet__actions">
        <Button variant="secondary" onPress={onClose}>
          Anuluj
        </Button>
        <Button pending={download.isPending} onPress={() => download.mutate()}>
          Pobierz plik
        </Button>
      </div>
    </ConfirmDialog>
  );
}
