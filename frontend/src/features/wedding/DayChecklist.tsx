/** „Co zabrać” na dzień ślubu: para układa listę, koordynator dnia odhacza ją w trakcie. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ListChecks, Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { Checkbox, TextField } from "../../components/Field";
import { Card, Notice } from "../../components/Surface";
import { useToast } from "../../components/Toast";

type Item = components["schemas"]["ChecklistOut"];

/** Postęp listy, np. „3 z 12”. */
export function progress(items: Pick<Item, "done">[]): string {
  return `${items.filter((i) => i.done).length} z ${items.length}`;
}

export function DayChecklist({ weddingId, canWrite, canRun }: { weddingId: string; canWrite: boolean; canRun: boolean }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const key = ["wedding", weddingId, "day-checklist"];
  const path = { params: { path: { wedding_id: weddingId } } };
  const items = useQuery({ queryKey: key, queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/day-checklist", { ...path, signal })) });
  const [title, setTitle] = useState("");
  const [who, setWho] = useState("");
  const [error, setError] = useState<string | null>(null);
  const idem = useRef(newIdempotencyKey());
  const refresh = () => queryClient.invalidateQueries({ queryKey: key });
  const typical = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/weddings/{wedding_id}/day-checklist/typical", path)),
    onSuccess: (data) => {
      queryClient.setQueryData(key, data);
      toast("Wczytano typową listę");
    },
    onError: (e) => setError(userMessage(e)),
  });
  const add = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/day-checklist", {
          ...path,
          body: { title: title.trim(), who: who.trim() || null },
          headers: { "Idempotency-Key": idem.current },
        }),
      ),
    onSuccess: async () => {
      idem.current = newIdempotencyKey();
      setTitle("");
      setWho("");
      setError(null);
      await refresh();
    },
    onError: (e) => setError(`Nie dodano. ${userMessage(e)}`),
  });
  const done = useMutation({
    mutationFn: ({ id, value }: { id: string; value: boolean }) =>
      unwrap(api.PUT("/api/v1/weddings/{wedding_id}/day-checklist/{item_id}/done", { params: { path: { wedding_id: weddingId, item_id: id } }, body: { done: value } })),
    onSuccess: refresh,
    onError: (e) => setError(userMessage(e)),
  });
  // Krótka lista: usuwamy od razu, z „Cofnij” w powiadomieniu (jak przy odhaczaniu zadań).
  const restore = useMutation({
    mutationFn: (i: Item) => unwrap(api.POST("/api/v1/weddings/{wedding_id}/day-checklist", { ...path, body: { title: i.title, who: i.who } })),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (i: Item) => unwrap(api.DELETE("/api/v1/weddings/{wedding_id}/day-checklist/{item_id}", { params: { path: { wedding_id: weddingId, item_id: i.id } } })),
    onSuccess: async (_, i) => {
      await refresh();
      toast(`Usunięto: ${i.title}`, () => restore.mutate(i));
    },
    onError: (e) => setError(userMessage(e)),
  });
  const list = items.data ?? [];
  if (!canWrite && list.length === 0) return null;

  return (
    <section className="form-stack" aria-labelledby="checklist-h">
      <div className="section-head section-head--wrap">
        <h2 id="checklist-h">Co zabrać{list.length > 0 && <span className="text-secondary num"> · {progress(list)}</span>}</h2>
        {canWrite && (
          <Button variant="text" icon={<ListChecks aria-hidden size={18} />} pending={typical.isPending} onPress={() => typical.mutate()}>
            Wczytaj typową listę
          </Button>
        )}
      </div>
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      <Card>
        {list.length === 0 ? (
          <p className="text-secondary">Obrączki, dokumenty, koperty dla usługodawców… Wczytajcie typową listę albo dopiszcie swoje.</p>
        ) : (
          <ul className="row-list">
            {list.map((i) => (
              <li key={i.id} className="row">
                {canRun ? (
                  <Checkbox isSelected={i.done} onChange={(value) => done.mutate({ id: i.id, value })}>
                    <span className={i.done ? "done-title" : undefined}>{i.title}</span>
                    {i.who && <span className="text-secondary"> · {i.who}</span>}
                  </Checkbox>
                ) : (
                  <span className="row__body">
                    {i.title}
                    {i.who && <span className="text-secondary"> · {i.who}</span>}
                  </span>
                )}
                {canWrite && (
                  <AriaButton className="wp-icon-button checklist__remove" aria-label={`Usuń: ${i.title}`} onPress={() => remove.mutate(i)}>
                    <Trash2 aria-hidden size={20} />
                  </AriaButton>
                )}
              </li>
            ))}
          </ul>
        )}
        {canWrite && (
          <Form
            className="delivery-plan checklist__add"
            aria-label="Nowa rzecz do zabrania"
            onSubmit={(e) => {
              e.preventDefault();
              if (title.trim()) add.mutate();
            }}
          >
            <TextField label="Co zabrać" value={title} onChange={setTitle} maxLength={200} autoComplete="off" />
            <TextField label="Kto bierze (opcjonalnie)" value={who} onChange={setWho} maxLength={80} autoComplete="off" />
            <Button type="submit" variant="secondary" pending={add.isPending} isDisabled={!title.trim()}>
              Dodaj
            </Button>
          </Form>
        )}
      </Card>
    </section>
  );
}
