/** Frekwencja: ilu gości realnie przyjdzie, minimum sali i lista rezerwowa („druga fala” zaproszeń). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Plus, Trash2, UserPlus } from "lucide-react";
import { useRef, useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";
import { Link } from "react-router";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { TextField } from "../../components/Field";
import { ConfirmDialog, Sheet } from "../../components/Overlay";
import { Segmented } from "../../components/Segmented";
import { Select } from "../../components/Select";
import { Card, EmptyState, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate, formatMoney, plural } from "../../lib/format";
import { GuestCostCard } from "./BudgetInsights";
import { AGE_GROUPS, SIDES } from "./EditGuestSheet";
import { GUEST_SECTIONS, SectionNav } from "./SectionNav";
import { keys, useCanWrite, useWeddingId } from "./data";
import { ifMatch, saveErrorMessage } from "./mutations";

type Forecast = components["schemas"]["AttendanceForecast"];
type Entry = components["schemas"]["ReserveEntryOut"];

export const PENDING_RATES = ["0.7", "0.8", "0.85", "0.9", "0.95"] as const;
export const MAYBE_RATES = ["0.3", "0.5", "0.7"] as const;
const percent = (rate: string) => `${Math.round(Number(rate) * 100)}%`;

const PEOPLE = { one: "# osoba", few: "# osoby", many: "# osób", other: "# osoby" };
export const people = (n: number) => plural(n, PEOPLE);
const FREE_PLACES = { one: "# wolne miejsce", few: "# wolne miejsca", many: "# wolnych miejsc", other: "# wolnego miejsca" };

/** Zakres prognozy po ludzku: „5 osób” albo „od 3 do 6 osób”. */
export function rangeText(f: Pick<Forecast["forecast"], "low" | "high">): string {
  return f.low === f.high ? people(f.low) : `od ${f.low} do ${people(f.high)}`;
}

/** Kolejność po przesunięciu o jedno miejsce (null: już na brzegu listy). */
export function movedPosition(index: number, direction: -1 | 1, length: number): number | null {
  const target = index + direction;
  return target < 0 || target >= length ? null : target;
}

export function AttendanceView() {
  const id = useWeddingId();
  const canWrite = useCanWrite(id);
  const [pendingRate, setPendingRate] = useState<string>("0.85");
  const [maybeRate, setMaybeRate] = useState<string>("0.5");
  const forecast = useQuery({
    queryKey: [...keys.forecast(id), pendingRate, maybeRate],
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/weddings/{wedding_id}/attendance-forecast", {
          params: { path: { wedding_id: id }, query: { pending_rate: Number(pendingRate), maybe_rate: Number(maybeRate) } },
          signal,
        }),
      ),
    placeholderData: (previous) => previous,
  });
  const f = forecast.data;

  return (
    <main className="page enter-tab" aria-labelledby="attendance-h">
      <SectionNav label="Goście" sections={GUEST_SECTIONS} />
      <div>
        <h1 id="attendance-h">Frekwencja</h1>
        <p className="text-secondary">Ilu gości realnie przyjdzie, co to znaczy dla umowy z salą i kogo zaprosić, gdy ktoś odmówi.</p>
      </div>

      {forecast.isPending && <Skeleton lines={5} />}
      {forecast.isError && (
        <Notice tone="error" live>
          {userMessage(forecast.error)}
        </Notice>
      )}
      {f && (
        <>
          {f.alerts.length > 0 && (
            <section aria-label="Na co uważać" className="form-stack">
              {f.alerts.map((a) => (
                <Notice key={a.code + a.message} tone="warning">
                  {a.message}
                </Notice>
              ))}
            </section>
          )}

          <Card className="form-stack" aria-labelledby="forecast-h">
            <h2 id="forecast-h">Prognoza na przyjęcie</h2>
            <p className="forecast__value">
              <span className="num">ok. {people(f.forecast.expected)}</span>
            </p>
            <p className="text-secondary">
              Najpewniej {rangeText(f.forecast)} (przedział ok. 90%).
              {f.forecast.expected_children > 0 && ` W tym ok. ${f.forecast.expected_children} ${f.forecast.expected_children === 1 ? "dziecko" : "dzieci"}.`}
              {f.planned ? ` Planowaliście ${people(f.planned)}.` : ""}
            </p>
            <ul className="forecast__people">
              <li>
                <StatusChip tone="success">Potwierdzeni: {f.people.attending}</StatusChip>
              </li>
              <li>
                <StatusChip tone="neutral">Bez odpowiedzi: {f.people.pending}</StatusChip>
              </li>
              <li>
                <StatusChip tone="info">Może: {f.people.maybe}</StatusChip>
              </li>
              <li>
                <StatusChip tone="neutral">Odmowy: {f.people.declined}</StatusChip>
              </li>
            </ul>
            {f.people.infants > 0 && (
              <p className="text-secondary">Niemowlęta ({f.people.infants}) są poza liczbami — zwykle bez opłaty i bez miejsca.</p>
            )}
            <details className="forecast__assumptions">
              <summary>Założenia prognozy</summary>
              <div className="form-stack">
                <p className="text-secondary">
                  To Wasze założenia, nie dane z innych wesel. Rodzina zwykle odpowiada wspólnie, dlatego przy dużych rodzinach
                  przedział jest szerszy.
                </p>
                <Segmented
                  label="Ile osób bez odpowiedzi przyjdzie"
                  value={pendingRate}
                  options={PENDING_RATES.map((r) => ({ value: r, label: percent(r) }))}
                  onChange={setPendingRate}
                />
                <Segmented
                  label="Ile osób z odpowiedzią „może” przyjdzie"
                  value={maybeRate}
                  options={MAYBE_RATES.map((r) => ({ value: r, label: percent(r) }))}
                  onChange={setMaybeRate}
                />
              </div>
            </details>
          </Card>

          {f.after_party && <AfterPartyCard after={f.after_party} />}
          <GuestCostCard weddingId={id} />

          <VenueSection forecast={f} weddingId={id} />
          <OverdueSection forecast={f} weddingId={id} />
          <ReserveSection forecast={f} weddingId={id} canWrite={canWrite} />
        </>
      )}
    </main>
  );
}

/** Poprawiny: osobna liczba (zwykle mniej gości, osobna cena u sali). */
function AfterPartyCard({ after: a }: { after: NonNullable<Forecast["after_party"]> }) {
  return (
    <Card className="form-stack" aria-labelledby="after-h">
      <h2 id="after-h">Prognoza: {a.event_name}</h2>
      <p className="forecast__value">
        <span className="num">ok. {people(a.forecast.expected)}</span>
      </p>
      <p className="text-secondary">
        Najpewniej {rangeText(a.forecast)}. Potwierdzeni: {a.people.attending}, bez odpowiedzi: {a.people.pending}, odmowy:{" "}
        {a.people.declined}. Kto odmówił przyjęcia, nie liczy się też tutaj.
      </p>
    </Card>
  );
}

function VenueSection({ forecast: f, weddingId }: { forecast: Forecast; weddingId: string }) {
  const final = f.final_count;
  return (
    <section className="form-stack" aria-labelledby="venue-h">
      <h2 id="venue-h">Sala i ostateczna liczba</h2>
      <Card className="form-stack">
        {final && (
          <p>
            {final.done ? (
              <>Ostateczna liczba gości przekazana sali — zadanie zrobione.</>
            ) : final.due_date ? (
              <>
                Ostateczną liczbę gości sala chce poznać do <strong>{formatDate(final.due_date)}</strong>
                {final.days_left !== null && final.days_left >= 0 && <> (za {plural(final.days_left, { one: "# dzień", few: "# dni", many: "# dni", other: "# dnia" })})</>}.
              </>
            ) : (
              <>Zadanie „{final.title}” nie ma terminu.</>
            )}{" "}
            <Link to={`/w/${weddingId}/plan`}>Termin zmienicie w planie.</Link>
          </p>
        )}
        {f.venues.length === 0 ? (
          <p className="text-secondary">
            Nie ma wybranej oferty z minimalną liczbą gości. Gdy wybierzecie salę z minimum, pokażemy, ile kosztowałyby puste miejsca.
          </p>
        ) : (
          <ul className="row-list">
            {f.venues.map((v) => (
              <li key={v.offer_id} className="row">
                <span className="row__body">
                  <span className="row__title">
                    {v.vendor_name}: minimum {people(v.min_guests)}
                  </span>
                  <span className="text-secondary">
                    {v.shortfall_expected === 0
                      ? "Przy prognozie minimum jest spełnione."
                      : `Przy prognozie brakuje ${people(v.shortfall_expected)}${v.unused_cost_expected ? ` — ok. ${formatMoney(v.unused_cost_expected)} za puste miejsca` : ""}.`}
                    {v.shortfall_low > v.shortfall_expected &&
                      ` W ostrożnym wariancie brakuje ${people(v.shortfall_low)}${v.unused_cost_low ? ` (${formatMoney(v.unused_cost_low)})` : ""}.`}
                  </span>
                </span>
                {v.shortfall_expected === 0 ? <StatusChip tone="success">OK</StatusChip> : <StatusChip tone="warning">Poniżej minimum</StatusChip>}
              </li>
            ))}
          </ul>
        )}
        <p className="text-secondary">Liczymy dorosłych (z nastolatkami) tak jak w wycenie oferty. Niemowlęta nie są liczone.</p>
      </Card>
    </section>
  );
}

function OverdueSection({ forecast: f, weddingId }: { forecast: Forecast; weddingId: string }) {
  if (f.overdue_households.length === 0) return null;
  return (
    <section className="form-stack" aria-labelledby="overdue-h">
      <h2 id="overdue-h">Po terminie odpowiedzi</h2>
      <Card>
        <ul className="row-list">
          {f.overdue_households.map((h) => (
            <li key={h.household_id} className="row">
              <span className="row__body">
                <span className="row__title">{h.name}</span>
                <span className="text-secondary">
                  Termin minął {formatDate(h.rsvp_deadline)} · bez odpowiedzi: {people(h.pending)}
                </span>
              </span>
            </li>
          ))}
        </ul>
      </Card>
      <p className="text-secondary">
        Warto zadzwonić albo wysłać przypomnienie. <Link to={`/w/${weddingId}/goscie`}>Przejdź do listy gości</Link>
      </p>
    </section>
  );
}

function ReserveSection({ forecast: f, weddingId, canWrite }: { forecast: Forecast; weddingId: string; canWrite: boolean }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const [inviting, setInviting] = useState<Entry | null>(null);
  const [removing, setRemoving] = useState<Entry | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reserve = useQuery({
    queryKey: keys.reserve(weddingId),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/reserve", { params: { path: { wedding_id: weddingId } }, signal })),
  });
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: keys.reserve(weddingId) }),
      queryClient.invalidateQueries({ queryKey: keys.forecast(weddingId) }),
    ]);
  const move = useMutation({
    mutationFn: ({ entry, position }: { entry: Entry; position: number }) =>
      unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/reserve/{entry_id}", {
          params: { path: { wedding_id: weddingId, entry_id: entry.id } },
          body: { position },
          headers: ifMatch(entry.version),
        }),
      ),
    onSuccess: async () => {
      setError(null);
      await refresh();
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [keys.reserve(weddingId)])),
  });
  const remove = useMutation({
    mutationFn: (entry: Entry) =>
      unwrap(api.DELETE("/api/v1/weddings/{wedding_id}/reserve/{entry_id}", { params: { path: { wedding_id: weddingId, entry_id: entry.id } } })),
    onSuccess: async () => {
      setRemoving(null);
      await refresh();
      toast("Usunięto z listy rezerwowej");
    },
    onError: (e) => setError(`Nie usunięto. ${userMessage(e)}`),
  });

  const entries = reserve.data ?? [];
  const waiting = entries.filter((e) => e.status === "waiting");
  const invited = entries.filter((e) => e.status === "invited");
  const suggested = new Set(f.suggestions.map((s) => s.entry_id));

  return (
    <section className="form-stack" aria-labelledby="reserve-h">
      <div className="section-head">
        <h2 id="reserve-h">Lista rezerwowa</h2>
        {canWrite && (
          <Button variant="secondary" icon={<Plus aria-hidden size={18} />} onPress={() => setAdding(true)}>
            Dodaj osobę
          </Button>
        )}
      </div>
      <p className="text-secondary">
        Osoby, które zaprosicie, gdy zwolni się miejsce. Nie liczą się do budżetu, stołów ani liczb dla sali, dopóki ich nie zaprosicie.
        {f.reserve_invite_by && <> Zapraszajcie z rezerwy najpóźniej do {formatDate(f.reserve_invite_by)}.</>}
      </p>
      {f.free_places_safe !== null && (
        <p>
          {f.free_places_safe > 0
            ? `Nawet jeśli przyjdzie więcej osób, niż zakłada prognoza, zostaje ok. ${plural(f.free_places_safe, FREE_PLACES)}.`
            : "Przy górnej granicy prognozy nie ma już wolnych miejsc."}
        </p>
      )}
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      {reserve.isPending && <Skeleton lines={2} />}
      {reserve.data && waiting.length === 0 && (
        <EmptyState title="Lista rezerwowa jest pusta">Dopiszcie osoby, które chętnie zaprosicie, jeśli ktoś odmówi.</EmptyState>
      )}
      {waiting.length > 0 && (
        <Card>
          <ol className="row-list">
            {waiting.map((e, i) => (
              <li key={e.id} className="row reserve-row">
                <span className="row__body">
                  <span className="row__title">
                    <span className="num">{i + 1}.</span> {e.name}
                  </span>
                  <span className="text-secondary">
                    {people(e.persons)} · {SIDES.find((s) => s.id === e.side)?.label}
                    {e.note && ` · ${e.note}`}
                  </span>
                </span>
                {suggested.has(e.id) && <StatusChip tone="info">Można zaprosić</StatusChip>}
                {canWrite && (
                  <span className="reserve__actions">
                    {(
                      [
                        [-1, ArrowUp, "wyżej"],
                        [1, ArrowDown, "niżej"],
                      ] as const
                    ).map(([direction, Icon, word]) => {
                      // Pozycja w całej liście (z zaproszonymi): serwer numeruje wszystkie wpisy.
                      const neighbour = waiting[i + direction];
                      const target = movedPosition(i, direction, waiting.length);
                      return (
                        <AriaButton
                          key={word}
                          className="wp-icon-button"
                          aria-label={`Przesuń ${word}: ${e.name}`}
                          isDisabled={target === null || move.isPending}
                          onPress={() => neighbour && move.mutate({ entry: e, position: entries.indexOf(neighbour) })}
                        >
                          <Icon aria-hidden size={20} />
                        </AriaButton>
                      );
                    })}
                    <AriaButton className="wp-icon-button" aria-label={`Usuń z listy: ${e.name}`} onPress={() => setRemoving(e)}>
                      <Trash2 aria-hidden size={20} />
                    </AriaButton>
                    <Button variant="secondary" icon={<UserPlus aria-hidden size={18} />} onPress={() => setInviting(e)}>
                      Zaproś
                    </Button>
                  </span>
                )}
              </li>
            ))}
          </ol>
        </Card>
      )}
      {invited.length > 0 && (
        <details className="reserve-invited">
          <summary>Zaproszeni z listy rezerwowej ({invited.length})</summary>
          <ul className="row-list">
            {invited.map((e) => (
              <li key={e.id} className="row">
                <span className="row__body">
                  <span className="row__title">{e.name}</span>
                  {e.invited_at && <span className="text-secondary">Zaproszeni {formatDate(e.invited_at.slice(0, 10))}</span>}
                </span>
                <StatusChip tone="success">Na liście gości</StatusChip>
              </li>
            ))}
          </ul>
        </details>
      )}

      <AddReserveSheet weddingId={weddingId} isOpen={adding} onClose={() => setAdding(false)} onSaved={refresh} />
      <InviteSheet weddingId={weddingId} entry={inviting} onClose={() => setInviting(null)} onSaved={refresh} />
      <ConfirmDialog title="Usunąć z listy rezerwowej?" isOpen={removing !== null} onOpenChange={(open) => !open && setRemoving(null)}>
        <p>{removing?.name} zniknie z listy rezerwowej. Lista gości się nie zmieni.</p>
        <div className="wp-sheet__actions">
          <Button variant="secondary" onPress={() => setRemoving(null)}>
            Zostaw
          </Button>
          <Button variant="danger" pending={remove.isPending} onPress={() => removing && remove.mutate(removing)}>
            Usuń z listy
          </Button>
        </div>
      </ConfirmDialog>
    </section>
  );
}

function AddReserveSheet({ weddingId, isOpen, onClose, onSaved }: { weddingId: string; isOpen: boolean; onClose: () => void; onSaved: () => Promise<unknown> }) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [persons, setPersons] = useState("1");
  const [side, setSide] = useState("both");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const key = useRef(newIdempotencyKey());
  const count = Number(persons);
  const valid = name.trim() !== "" && Number.isInteger(count) && count >= 1 && count <= 20;
  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/reserve", {
          params: { path: { wedding_id: weddingId } },
          body: { name: name.trim(), persons: count, side: side as Entry["side"], note: note.trim() || null },
          headers: { "Idempotency-Key": key.current },
        }),
      ),
    onSuccess: async (e) => {
      key.current = newIdempotencyKey();
      setName("");
      setPersons("1");
      setNote("");
      setError(null);
      await onSaved();
      onClose();
      toast(`Dodano do listy rezerwowej: ${e.name}`);
    },
    onError: (e) => setError(`Nie dodano. ${userMessage(e)}`),
  });
  return (
    <Sheet title="Nowa osoba na liście rezerwowej" isOpen={isOpen} onOpenChange={(open) => !open && onClose()} isDirty={name !== ""}>
      <Form
        className="form-stack"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) save.mutate();
        }}
      >
        <TextField label="Kogo zaprosicie" description="Np. „Kuzyn Marek z żoną”." value={name} onChange={setName} isRequired autoComplete="off" />
        <TextField
          label="Ile osób"
          inputMode="numeric"
          value={persons}
          onChange={setPersons}
          isRequired
          error={persons !== "" && !(count >= 1 && count <= 20) ? "Podaj liczbę od 1 do 20." : undefined}
        />
        <Select label="Strona" options={SIDES} value={side} onChange={setSide} />
        <TextField label="Notatka (opcjonalnie)" value={note} onChange={setNote} autoComplete="off" />
        {error && (
          <Notice tone="error" live>
            {error}
          </Notice>
        )}
        <div className="wp-sheet__actions">
          <Button type="submit" isDisabled={!valid} pending={save.isPending}>
            Dodaj do listy
          </Button>
        </div>
      </Form>
    </Sheet>
  );
}

function InviteSheet({ weddingId, entry, onClose, onSaved }: { weddingId: string; entry: Entry | null; onClose: () => void; onSaved: () => Promise<unknown> }) {
  return (
    <Sheet title={entry ? `Zaproś: ${entry.name}` : "Zaproś"} isOpen={entry !== null} onOpenChange={(open) => !open && onClose()}>
      {entry && <InviteForm key={entry.id} weddingId={weddingId} entry={entry} onClose={onClose} onSaved={onSaved} />}
    </Sheet>
  );
}

function InviteForm({ weddingId, entry, onClose, onSaved }: { weddingId: string; entry: Entry; onClose: () => void; onSaved: () => Promise<unknown> }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [guests, setGuests] = useState(() => Array.from({ length: entry.persons }, () => ({ first_name: "", age_group: "adult" })));
  const [error, setError] = useState<string | null>(null);
  const key = useRef(newIdempotencyKey());
  const valid = guests.every((g) => g.first_name.trim() !== "");
  const invite = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/reserve/{entry_id}/invite", {
          params: { path: { wedding_id: weddingId, entry_id: entry.id } },
          body: { guests: guests.map((g) => ({ first_name: g.first_name.trim(), age_group: g.age_group as "adult" })) },
          headers: { "Idempotency-Key": key.current },
        }),
      ),
    onSuccess: async () => {
      await Promise.all([
        onSaved(),
        queryClient.invalidateQueries({ queryKey: keys.households(weddingId) }),
        queryClient.invalidateQueries({ queryKey: keys.guestStats(weddingId) }),
      ]);
      onClose();
      toast(`${entry.name} — dopisani do listy gości. Wyślijcie zaproszenie i link RSVP.`);
    },
    onError: (e) => setError(`Nie zaproszono. ${userMessage(e)}`),
  });
  const update = (i: number, patch: Partial<(typeof guests)[number]>) => setGuests((list) => list.map((g, j) => (j === i ? { ...g, ...patch } : g)));
  return (
    <Form
      className="form-stack"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) invite.mutate();
      }}
    >
      <p className="text-secondary">
        Powstanie zaproszenie na liście gości. Wpiszcie imiona — potem możecie dodać nazwiska, diety i wysłać link RSVP.
      </p>
      {guests.map((g, i) => (
        <fieldset key={i} className="form-stack invite-person">
          <legend>Osoba {i + 1}</legend>
          <TextField label="Imię" value={g.first_name} onChange={(v) => update(i, { first_name: v })} isRequired autoComplete="off" />
          <Select label="Wiek" options={AGE_GROUPS} value={g.age_group} onChange={(v) => update(i, { age_group: v })} />
        </fieldset>
      ))}
      <div className="wp-sheet__actions">
        {guests.length < 20 && (
          <Button variant="text" icon={<Plus aria-hidden size={18} />} onPress={() => setGuests((l) => [...l, { first_name: "", age_group: "adult" }])}>
            Dodaj osobę
          </Button>
        )}
        {guests.length > 1 && (
          <Button variant="text" onPress={() => setGuests((l) => l.slice(0, -1))}>
            Usuń ostatnią osobę
          </Button>
        )}
      </div>
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      <div className="wp-sheet__actions">
        <Button type="submit" isDisabled={!valid} pending={invite.isPending}>
          Zaproś na wesele
        </Button>
      </div>
    </Form>
  );
}
