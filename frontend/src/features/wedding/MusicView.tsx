/** Muzyka: utwory na momenty wesela, „koniecznie” i „nie grać”, propozycje gości z RSVP. Trafia do linku DJ-a. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Trash2, X } from "lucide-react";
import { useRef, useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { Checkbox, TextField } from "../../components/Field";
import { Select } from "../../components/Select";
import { Card, Notice, Skeleton } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { byMoment, MOMENTS, songLabel, type Moment } from "../../lib/music";
import { DaySectionNav } from "./SectionNav";
import { useCanWrite, useWeddingId } from "./data";
import { ifMatch, saveErrorMessage } from "./mutations";

type Entry = components["schemas"]["MusicOut"];
export function MusicView() {
  const id = useWeddingId();
  const canWrite = useCanWrite(id);
  const queryClient = useQueryClient();
  const toast = useToast();
  const key = ["wedding", id, "music"];
  const path = { params: { path: { wedding_id: id } } };
  const data = useQuery({ queryKey: key, queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/music", { ...path, signal })) });
  const [moment, setMoment] = useState<Moment>("first_dance");
  const [title, setTitle] = useState("");
  const [artist, setArtist] = useState("");
  const [error, setError] = useState<string | null>(null);
  const idem = useRef(newIdempotencyKey());
  const refresh = () => queryClient.invalidateQueries({ queryKey: key });

  const add = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/music", {
          ...path,
          body: { moment, title: title.trim(), artist: artist.trim() || null },
          headers: { "Idempotency-Key": idem.current },
        }),
      ),
    onSuccess: async () => {
      idem.current = newIdempotencyKey();
      setTitle("");
      setArtist("");
      setError(null);
      await refresh();
    },
    onError: (e) => setError(`Nie dodano. ${userMessage(e)}`),
  });
  const requests = useMutation({
    mutationFn: (enabled: boolean) => unwrap(api.PUT("/api/v1/weddings/{wedding_id}/music/song-requests", { ...path, body: { enabled } })),
    onSuccess: async (r) => {
      await refresh();
      toast(r.enabled ? "Goście mogą proponować utwory" : "Propozycje gości wyłączone");
    },
    onError: (e) => setError(userMessage(e)),
  });
  const decide = useMutation({
    mutationFn: ({ entry, status }: { entry: Entry; status: "approved" | "rejected" }) =>
      unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/music/{entry_id}", {
          params: { path: { wedding_id: id, entry_id: entry.id } },
          body: { status },
          headers: ifMatch(entry.version),
        }),
      ),
    onSuccess: refresh,
    onError: (e) => setError(saveErrorMessage(e, queryClient, [key])),
  });
  const restore = useMutation({
    mutationFn: (e: Entry) => unwrap(api.POST("/api/v1/weddings/{wedding_id}/music", { ...path, body: { moment: e.moment, title: e.title, artist: e.artist, note: e.note } })),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (entry: Entry) => unwrap(api.DELETE("/api/v1/weddings/{wedding_id}/music/{entry_id}", { params: { path: { wedding_id: id, entry_id: entry.id } } })),
    onSuccess: async (_, entry) => {
      await refresh();
      toast(`Usunięto: ${entry.title}`, () => restore.mutate(entry));
    },
    onError: (e) => setError(userMessage(e)),
  });

  const o = data.data;
  const entries = o?.entries ?? [];
  const waiting = entries.filter((e) => e.status === "suggested");
  const approved = entries.filter((e) => e.status === "approved");

  return (
    <main className="page enter-tab" aria-labelledby="music-h">
      <DaySectionNav />
      <div>
        <h1 id="music-h">Muzyka</h1>
        <p className="text-secondary">
          Utwory na ważne momenty i lista „nie grać” — DJ lub zespół zobaczy je na swoim linku i potwierdzi nową wersję.
        </p>
      </div>
      {data.isPending && <Skeleton lines={5} />}
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
      {o && canWrite && (
        <Card className="form-stack">
          <Checkbox isSelected={o.song_requests} isDisabled={requests.isPending} onChange={(v) => requests.mutate(v)}>
            Goście mogą zaproponować utwór w formularzu RSVP (do 3 na zaproszenie; Wy decydujecie, co trafi do DJ-a)
          </Checkbox>
        </Card>
      )}
      {waiting.length > 0 && (
        <section className="form-stack" aria-labelledby="waiting-h">
          <h2 id="waiting-h">Propozycje gości ({waiting.length})</h2>
          <Card>
            <ul className="row-list">
              {waiting.map((e) => (
                <li key={e.id} className="row">
                  <span className="row__body">
                    <span className="row__title">{songLabel(e)}</span>
                    {e.suggested_by && <span className="text-secondary">od: {e.suggested_by}</span>}
                  </span>
                  {canWrite && (
                    <span className="row-actions">
                      <AriaButton className="wp-icon-button" aria-label={`Dodaj do listy DJ-a: ${e.title}`} onPress={() => decide.mutate({ entry: e, status: "approved" })}>
                        <Check aria-hidden size={20} />
                      </AriaButton>
                      <AriaButton className="wp-icon-button" aria-label={`Odrzuć: ${e.title}`} onPress={() => decide.mutate({ entry: e, status: "rejected" })}>
                        <X aria-hidden size={20} />
                      </AriaButton>
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        </section>
      )}
      {byMoment(approved).map((m) => (
        <section key={m.id} className="form-stack" aria-labelledby={`music-${m.id}`}>
          <h2 id={`music-${m.id}`}>{m.label}</h2>
          <Card>
            <ul className="row-list">
              {m.items.map((e) => (
                <li key={e.id} className="row">
                  <span className="row__body">
                    <span className="row__title">{songLabel(e)}</span>
                    {(e.note || e.suggested_by) && (
                      <span className="text-secondary">{[e.note, e.suggested_by && `propozycja: ${e.suggested_by}`].filter(Boolean).join(" · ")}</span>
                    )}
                  </span>
                  {canWrite && (
                    <AriaButton className="wp-icon-button" aria-label={`Usuń: ${e.title}`} onPress={() => remove.mutate(e)}>
                      <Trash2 aria-hidden size={20} />
                    </AriaButton>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        </section>
      ))}
      {o && approved.length === 0 && waiting.length === 0 && (
        <p className="text-secondary">Na początek: utwór na wejście i pierwszy taniec oraz to, czego DJ ma nie grać.</p>
      )}
      {canWrite && (
        <Card className="form-stack">
          <h2 className="card-title">Dodaj utwór</h2>
          <Form
            className="form-stack"
            aria-label="Nowy utwór"
            onSubmit={(e) => {
              e.preventDefault();
              if (title.trim()) add.mutate();
            }}
          >
            <Select label="Kiedy" options={MOMENTS.map((m) => ({ id: m.id, label: m.label }))} value={moment} onChange={(v) => setMoment(v as Moment)} />
            <TextField label="Tytuł" value={title} onChange={setTitle} maxLength={200} autoComplete="off" isRequired />
            <TextField label="Wykonawca (opcjonalnie)" value={artist} onChange={setArtist} maxLength={120} autoComplete="off" />
            <Button type="submit" variant="secondary" pending={add.isPending} isDisabled={!title.trim()}>
              Dodaj
            </Button>
          </Form>
        </Card>
      )}
    </main>
  );
}
