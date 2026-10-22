/** Zdjęcia grupowe dla fotografa: kto, w jakiej kolejności, ile to potrwa; świadek odhacza w dniu ślubu. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, ListChecks, Pencil } from "lucide-react";
import { useRef, useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { Checkbox, TextField } from "../../components/Field";
import { ConfirmDialog, Sheet } from "../../components/Overlay";
import { Card, EmptyState, Notice, Skeleton } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { plural } from "../../lib/format";
import { DaySectionNav } from "./SectionNav";
import { useCanRunDay, useCanWrite, useHouseholds, useWeddingId } from "./data";
import { ifMatch, saveErrorMessage } from "./mutations";

type Overview = components["schemas"]["PhotoOverview"];
type Group = Overview["groups"][number];

const MINUTES = { one: "# minuta", few: "# minuty", many: "# minut", other: "# minuty" };
const GROUPS = { one: "# grupa", few: "# grupy", many: "# grup", other: "# grupy" };

/** Czas zdjęć: „ok. 1 h 5 min” albo „ok. 35 min”. */
export function duration(minutes: number): string {
  if (minutes < 60) return `ok. ${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `ok. ${h} h ${m} min` : `ok. ${h} h`;
}

export function PhotoGroupsView() {
  const id = useWeddingId();
  const canWrite = useCanWrite(id);
  const canRun = useCanRunDay(id);
  const queryClient = useQueryClient();
  const toast = useToast();
  const key = ["wedding", id, "photo-groups"];
  const path = { params: { path: { wedding_id: id } } };
  const data = useQuery({ queryKey: key, queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/photo-groups", { ...path, signal })) });
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Group | null>(null);
  const idem = useRef(newIdempotencyKey());
  const set = (o: Overview) => queryClient.setQueryData(key, o);

  const typical = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/weddings/{wedding_id}/photo-groups/typical", path)),
    onSuccess: (o) => {
      set(o);
      toast("Wczytano typowe grupy");
    },
    onError: (e) => setError(userMessage(e)),
  });
  const add = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/photo-groups", {
          ...path,
          body: { title: title.trim(), minutes: 3 },
          headers: { "Idempotency-Key": idem.current },
        }),
      ),
    onSuccess: (o) => {
      idem.current = newIdempotencyKey();
      set(o);
      setTitle("");
      setError(null);
    },
    onError: (e) => setError(`Nie dodano. ${userMessage(e)}`),
  });
  const done = useMutation({
    mutationFn: ({ group, value }: { group: string; value: boolean }) =>
      unwrap(api.PUT("/api/v1/weddings/{wedding_id}/photo-groups/{group_id}/done", { params: { path: { wedding_id: id, group_id: group } }, body: { done: value } })),
    onSuccess: set,
    onError: (e) => setError(userMessage(e)),
  });
  const move = useMutation({
    mutationFn: ({ group, direction }: { group: string; direction: "up" | "down" }) =>
      unwrap(api.POST("/api/v1/weddings/{wedding_id}/photo-groups/{group_id}/move", { params: { path: { wedding_id: id, group_id: group } }, body: { direction } })),
    onSuccess: set,
    onError: (e) => setError(userMessage(e)),
  });
  const o = data.data;
  const groups = o?.groups ?? [];

  return (
    <main className="page enter-tab" aria-labelledby="photos-h">
      <DaySectionNav />
      <div className="section-head section-head--wrap">
        <div>
          <h1 id="photos-h">Zdjęcia grupowe</h1>
          <p className="text-secondary">
            Kto staje do zdjęcia i w jakiej kolejności — fotograf widzi tę listę na swoim linku, a świadek odhacza zrobione.
          </p>
        </div>
        {canWrite && (
          <Button variant="text" icon={<ListChecks aria-hidden size={18} />} pending={typical.isPending} onPress={() => typical.mutate()}>
            Wczytaj typowe grupy
          </Button>
        )}
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
      {o && groups.length > 0 && (
        <Notice tone="info">
          {plural(groups.length, GROUPS)} · {duration(o.total_minutes)}
          {o.remaining_minutes < o.total_minutes && ` · zostało ${duration(o.remaining_minutes)}`}. Zarezerwujcie ten czas w harmonogramie (zwykle
          zaraz po ceremonii albo przed obiadem); najstarszych gości fotografujcie na początku.
        </Notice>
      )}
      {o && groups.length === 0 && (
        <EmptyState title="Brak grup">
          {canWrite ? "Wczytajcie typowe grupy (dziadkowie, rodzice, świadkowie…) albo dopiszcie własne." : "Para nie ułożyła jeszcze listy zdjęć."}
        </EmptyState>
      )}
      {groups.length > 0 && (
        <Card>
          <ol className="row-list photo-groups">
            {groups.map((g, i) => {
              const people = [...g.guests.map((p) => p.name), ...(g.extra ? [g.extra] : [])].join(", ");
              const body = (
                <span className="row__body">
                  <span className={g.done ? "done-title" : "row__title"}>{g.title}</span>
                  <span className="text-secondary">
                    {people || "osoby do uzupełnienia"} · {plural(g.minutes, MINUTES)}
                  </span>
                </span>
              );
              return (
                <li key={g.id} className="row">
                  {canRun ? (
                    <Checkbox isSelected={g.done} onChange={(value) => done.mutate({ group: g.id, value })}>
                      {body}
                    </Checkbox>
                  ) : (
                    body
                  )}
                  {canWrite && (
                    <span className="row-actions">
                      <AriaButton
                        className="wp-icon-button"
                        aria-label={`Wyżej: ${g.title}`}
                        isDisabled={i === 0}
                        onPress={() => move.mutate({ group: g.id, direction: "up" })}
                      >
                        <ArrowUp aria-hidden size={20} />
                      </AriaButton>
                      <AriaButton
                        className="wp-icon-button"
                        aria-label={`Niżej: ${g.title}`}
                        isDisabled={i === groups.length - 1}
                        onPress={() => move.mutate({ group: g.id, direction: "down" })}
                      >
                        <ArrowDown aria-hidden size={20} />
                      </AriaButton>
                      <AriaButton className="wp-icon-button" aria-label={`Edytuj: ${g.title}`} onPress={() => setEditing(g)}>
                        <Pencil aria-hidden size={20} />
                      </AriaButton>
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
        </Card>
      )}
      {canWrite && (
        <Form
          className="delivery-plan checklist__add"
          aria-label="Nowa grupa do zdjęcia"
          onSubmit={(e) => {
            e.preventDefault();
            if (title.trim()) add.mutate();
          }}
        >
          <TextField label="Nowa grupa" value={title} onChange={setTitle} maxLength={200} autoComplete="off" placeholder="np. Para Młoda z kuzynostwem" />
          <Button type="submit" variant="secondary" pending={add.isPending} isDisabled={!title.trim()}>
            Dodaj
          </Button>
        </Form>
      )}
      <Sheet title={editing ? editing.title : "Grupa"} isOpen={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        {editing && <GroupForm key={editing.id} weddingId={id} group={editing} queryKey={key} onClose={() => setEditing(null)} />}
      </Sheet>
    </main>
  );
}

function GroupForm({ weddingId, group, queryKey, onClose }: { weddingId: string; group: Group; queryKey: unknown[]; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const households = useHouseholds(weddingId);
  const [title, setTitle] = useState(group.title);
  const [extra, setExtra] = useState(group.extra ?? "");
  const [minutes, setMinutes] = useState(String(group.minutes));
  const [selected, setSelected] = useState<Set<string>>(new Set(group.guests.map((g) => g.id)));
  const [filter, setFilter] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const params = { params: { path: { wedding_id: weddingId, group_id: group.id } } };
  const needle = filter.trim().toLocaleLowerCase("pl");
  const guests = (households.data ?? [])
    .flatMap((h) => h.guests.map((g) => ({ ...g, household: h.name })))
    .filter((g) => !needle || `${g.first_name} ${g.last_name ?? ""} ${g.household}`.toLocaleLowerCase("pl").includes(needle))
    .sort((a, b) => Number(selected.has(b.id)) - Number(selected.has(a.id)) || a.first_name.localeCompare(b.first_name, "pl"));
  const minutesN = Number(minutes);
  const valid = title.trim() && Number.isInteger(minutesN) && minutesN >= 1 && minutesN <= 60;

  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/photo-groups/{group_id}", {
          ...params,
          body: { title: title.trim(), extra: extra.trim() || null, minutes: minutesN, guest_ids: [...selected] },
          headers: ifMatch(group.version),
        }),
      ),
    onSuccess: (o) => {
      queryClient.setQueryData(queryKey, o);
      toast("Zapisano grupę");
      onClose();
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [queryKey])),
  });
  const remove = useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/v1/weddings/{wedding_id}/photo-groups/{group_id}", params)),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey });
      toast("Usunięto grupę");
      onClose();
    },
    onError: (e) => setError(userMessage(e)),
  });

  return (
    <Form
      className="form-stack"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) save.mutate();
      }}
    >
      <TextField label="Nazwa grupy" value={title} onChange={setTitle} maxLength={200} isRequired />
      <TextField label="Osoby spoza listy gości (opcjonalnie)" value={extra} onChange={setExtra} maxLength={200} placeholder="np. ksiądz, świadkowie z partnerami" />
      <TextField label="Ile minut" value={minutes} onChange={setMinutes} inputMode="numeric" description="Zwykle 2–3 minuty na grupę, duże grupy dłużej." />
      <h3 className="card-title">Kto staje do zdjęcia ({selected.size})</h3>
      <TextField label="Szukaj gościa" value={filter} onChange={setFilter} autoComplete="off" />
      {households.isPending && <Skeleton lines={3} />}
      <ul className="row-list">
        {guests.map((g) => (
          <li key={g.id} className="row">
            <Checkbox
              isSelected={selected.has(g.id)}
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
                <span className="text-secondary">{g.household}</span>
              </span>
            </Checkbox>
          </li>
        ))}
      </ul>
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      <div className="wp-sheet__actions">
        <Button type="submit" pending={save.isPending} isDisabled={!valid}>
          Zapisz
        </Button>
        <Button variant="text" onPress={() => setConfirm(true)}>
          Usuń grupę
        </Button>
      </div>
      <ConfirmDialog title="Usunąć grupę?" isOpen={confirm} onOpenChange={setConfirm}>
        <p>Grupa „{group.title}” zniknie z listy fotografa.</p>
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
