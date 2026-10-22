/** Fryzura i makijaż: liczone wstecz od godziny „gotowi”. Fryzjerka i makijażystka widzą go na swoim linku. */
import { parseTime, type Time } from "@internationalized/date";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { TimeField } from "../../components/DateField";
import { TextField } from "../../components/Field";
import { Card, EmptyState, Notice, Skeleton } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { DaySectionNav } from "./SectionNav";
import { useCanWrite, useWeddingId } from "./data";
import { ifMatch, saveErrorMessage } from "./mutations";

type Overview = components["schemas"]["PrepOverview"];
type Slot = components["schemas"]["PrepSlot"];

/** „09:30–10:30 (fryzjerka 2)” — numer stanowiska tylko, gdy osób obsługujących jest kilka. */
export function slotText(s: Slot, who: string, many: boolean): string {
  return `${s.start}–${s.end}${many ? ` (${who} ${s.artist})` : ""}`;
}

/** Liczba z pola tekstowego (minuty, osoby); pusta lub błędna → null. */
export function intOrNull(v: string, max: number): number | null {
  const n = Number(v.trim());
  return v.trim() !== "" && Number.isInteger(n) && n >= 0 && n <= max ? n : null;
}

export function PrepView() {
  const id = useWeddingId();
  const canWrite = useCanWrite(id);
  const queryClient = useQueryClient();
  const toast = useToast();
  const key = ["wedding", id, "prep"];
  const path = { params: { path: { wedding_id: id } } };
  const data = useQuery({ queryKey: key, queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/prep", { ...path, signal })) });
  const set = (o: Overview) => queryClient.setQueryData(key, o);
  const [error, setError] = useState<string | null>(null);
  const o = data.data;

  const move = useMutation({
    mutationFn: ({ person, direction }: { person: string; direction: "up" | "down" }) =>
      unwrap(api.POST("/api/v1/weddings/{wedding_id}/prep/people/{person_id}/move", { params: { path: { wedding_id: id, person_id: person } }, body: { direction } })),
    onSuccess: set,
    onError: (e) => setError(userMessage(e)),
  });
  const restore = useMutation({
    mutationFn: (p: Overview["people"][number]) =>
      unwrap(api.POST("/api/v1/weddings/{wedding_id}/prep/people", { ...path, body: { name: p.name, hair_minutes: p.hair_minutes, makeup_minutes: p.makeup_minutes } })),
    onSuccess: set,
  });
  const remove = useMutation({
    mutationFn: (p: Overview["people"][number]) => unwrap(api.DELETE("/api/v1/weddings/{wedding_id}/prep/people/{person_id}", { params: { path: { wedding_id: id, person_id: p.id } } })),
    onSuccess: async (_, p) => {
      await queryClient.invalidateQueries({ queryKey: key });
      toast(`Usunięto: ${p.name}`, () => restore.mutate(p));
    },
    onError: (e) => setError(userMessage(e)),
  });

  return (
    <main className="page enter-tab" aria-labelledby="prep-h">
      <DaySectionNav />
      <div>
        <h1 id="prep-h">Fryzura i makijaż</h1>
        <p className="text-secondary">
          Fryzura i makijaż liczone wstecz od godziny, na którą wszyscy mają być gotowi. Osoba na końcu listy (zwykle Panna Młoda)
          kończy ostatnia. Fryzjerka i makijażystka zobaczą swoje godziny na linku.
        </p>
      </div>
      {data.isPending && <Skeleton lines={4} />}
      {data.isError && (
        <Notice tone="error" live>
          {userMessage(data.error)}
        </Notice>
      )}
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      {o && <PlanCard key={o.version} weddingId={id} plan={o} canWrite={canWrite} onSaved={set} />}
      {o?.start && (
        <Notice tone="info">
          Pierwsza osoba siada na fotel o <strong className="num">{o.start}</strong>
          {o.hair_start && ` (fryzjerka od ${o.hair_start}`}
          {o.makeup_start && `${o.hair_start ? ", " : " ("}makijażystka od ${o.makeup_start}`}
          {(o.hair_start || o.makeup_start) && ")"}. Gotowi o <span className="num">{o.ready_by}</span>.
        </Notice>
      )}
      {o?.warnings.map((w) => (
        <Notice key={w} tone="warning">
          {w}
        </Notice>
      ))}
      {o && o.people.length === 0 && (
        <EmptyState title="Nikt jeszcze nie siedzi na fotelu">
          Dopiszcie osoby: Pannę Młodą, mamy, świadkową, druhny — z czasem fryzury i makijażu (zapytajcie fryzjerkę, ile trwa).
        </EmptyState>
      )}
      {o && o.people.length > 0 && (
        <Card>
          <ol className="row-list photo-groups">
            {o.people.map((p, i) => (
              <li key={p.id} className="row">
                <span className="row__body">
                  <span className="row__title">{p.name}</span>
                  <span className="text-secondary num">
                    {[
                      p.hair && `fryzura ${slotText(p.hair, "fryzjerka", o.hair_artists > 1)}`,
                      p.makeup && `makijaż ${slotText(p.makeup, "makijażystka", o.makeup_artists > 1)}`,
                    ]
                      .filter(Boolean)
                      .join(" · ") || "bez fryzury i makijażu"}
                  </span>
                </span>
                {canWrite && (
                  <span className="row-actions">
                    <AriaButton className="wp-icon-button" aria-label={`Wcześniej: ${p.name}`} isDisabled={i === 0} onPress={() => move.mutate({ person: p.id, direction: "up" })}>
                      <ArrowUp aria-hidden size={20} />
                    </AriaButton>
                    <AriaButton
                      className="wp-icon-button"
                      aria-label={`Później: ${p.name}`}
                      isDisabled={i === o.people.length - 1}
                      onPress={() => move.mutate({ person: p.id, direction: "down" })}
                    >
                      <ArrowDown aria-hidden size={20} />
                    </AriaButton>
                    <AriaButton className="wp-icon-button" aria-label={`Usuń: ${p.name}`} onPress={() => remove.mutate(p)}>
                      <Trash2 aria-hidden size={20} />
                    </AriaButton>
                  </span>
                )}
              </li>
            ))}
          </ol>
        </Card>
      )}
      {canWrite && <AddPerson weddingId={id} onAdded={set} />}
    </main>
  );
}

function PlanCard({ weddingId, plan, canWrite, onSaved }: { weddingId: string; plan: Overview; canWrite: boolean; onSaved: (o: Overview) => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [ready, setReady] = useState<Time | null>(parseTime(plan.ready_by));
  const [hair, setHair] = useState(String(plan.hair_artists));
  const [makeup, setMakeup] = useState(String(plan.makeup_artists));
  const [error, setError] = useState<string | null>(null);
  const hairN = intOrNull(hair, 10);
  const makeupN = intOrNull(makeup, 10);
  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.PUT("/api/v1/weddings/{wedding_id}/prep", {
          params: { path: { wedding_id: weddingId } },
          body: { ready_by: ready!.toString(), hair_artists: hairN, makeup_artists: makeupN },
          headers: ifMatch(plan.version),
        }),
      ),
    onSuccess: (o) => {
      onSaved(o);
      toast("Zapisano godziny");
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [["wedding", weddingId, "prep"]])),
  });
  if (!canWrite) {
    return (
      <p className="text-secondary num">
        Gotowi o {plan.ready_by} · fryzjerek: {plan.hair_artists} · makijażystek: {plan.makeup_artists}
      </p>
    );
  }
  return (
    <Card className="form-stack">
      <Form
        className="form-stack"
        aria-label="Godzina gotowości i osoby obsługujące"
        onSubmit={(e) => {
          e.preventDefault();
          if (ready && hairN !== null && makeupN !== null) save.mutate();
        }}
      >
        <TimeField label="Na którą wszyscy gotowi" value={ready} onChange={setReady} description="Np. godzinę przed wyjazdem do kościoła lub USC (zdjęcia, ubieranie)." />
        <div className="stat-grid">
          <TextField label="Ile fryzjerek" value={hair} onChange={setHair} inputMode="numeric" error={hairN === null ? "Od 0 do 10" : undefined} />
          <TextField label="Ile makijażystek" value={makeup} onChange={setMakeup} inputMode="numeric" error={makeupN === null ? "Od 0 do 10" : undefined} />
        </div>
        {error && (
          <Notice tone="error" live>
            {error}
          </Notice>
        )}
        <Button type="submit" variant="secondary" pending={save.isPending} isDisabled={!ready || hairN === null || makeupN === null}>
          Zapisz plan
        </Button>
      </Form>
    </Card>
  );
}

function AddPerson({ weddingId, onAdded }: { weddingId: string; onAdded: (o: Overview) => void }) {
  const [name, setName] = useState("");
  const [hair, setHair] = useState("60");
  const [makeup, setMakeup] = useState("45");
  const [error, setError] = useState<string | null>(null);
  const idem = useRef(newIdempotencyKey());
  const hairN = intOrNull(hair, 300);
  const makeupN = intOrNull(makeup, 300);
  const valid = name.trim() && hairN !== null && makeupN !== null;
  const add = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/prep/people", {
          params: { path: { wedding_id: weddingId } },
          body: { name: name.trim(), hair_minutes: hairN!, makeup_minutes: makeupN! },
          headers: { "Idempotency-Key": idem.current },
        }),
      ),
    onSuccess: (o) => {
      idem.current = newIdempotencyKey();
      onAdded(o);
      setName("");
      setError(null);
    },
    onError: (e) => setError(`Nie dodano. ${userMessage(e)}`),
  });
  return (
    <Card className="form-stack">
      <h2 className="card-title">Dodaj osobę</h2>
      <Form
        className="form-stack"
        aria-label="Nowa osoba na fotel"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) add.mutate();
        }}
      >
        <TextField label="Kto" value={name} onChange={setName} maxLength={80} autoComplete="off" placeholder="np. Mama Panny Młodej" isRequired />
        <div className="stat-grid">
          <TextField label="Fryzura (minuty)" value={hair} onChange={setHair} inputMode="numeric" error={hairN === null ? "Od 0 do 300" : undefined} />
          <TextField label="Makijaż (minuty)" value={makeup} onChange={setMakeup} inputMode="numeric" error={makeupN === null ? "Od 0 do 300" : undefined} />
        </div>
        {error && (
          <Notice tone="error" live>
            {error}
          </Notice>
        )}
        <Button type="submit" variant="secondary" pending={add.isPending} isDisabled={!valid}>
          Dodaj
        </Button>
      </Form>
    </Card>
  );
}
