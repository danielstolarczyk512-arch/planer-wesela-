/** Lista prezentów: pomysły pary, które goście rezerwują na swojej stronie (bez dublowania prezentów). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { Checkbox, TextField } from "../../components/Field";
import { Segmented } from "../../components/Segmented";
import { Card, Notice, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";

type Gift = components["schemas"]["GiftOut"];
type Kind = Gift["kind"];

/** Stan pomysłu dla pary: „fundusz”, „wolne” albo kto zarezerwował. */
export function giftState(g: Pick<Gift, "kind" | "reserved" | "reserved_by">): string {
  if (g.kind === "fund") return "fundusz — bez rezerwacji";
  if (!g.reserved) return "wolne";
  return g.reserved_by ? `wybrali: ${g.reserved_by}` : "zarezerwowane";
}

export function GiftsSection({ weddingId, enabled, canWrite, onToggle, pending }: { weddingId: string; enabled: boolean; canWrite: boolean; onToggle: (v: boolean) => void; pending: boolean }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const key = ["wedding", weddingId, "gifts"];
  const path = { params: { path: { wedding_id: weddingId } } };
  const data = useQuery({ queryKey: key, queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/gifts", { ...path, signal })) });
  const [kind, setKind] = useState<Kind>("item");
  const [title, setTitle] = useState("");
  const [link, setLink] = useState("");
  const [error, setError] = useState<string | null>(null);
  const idem = useRef(newIdempotencyKey());
  const add = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/gifts", {
          ...path,
          body: { kind, title: title.trim(), link: link.trim() || null },
          headers: { "Idempotency-Key": idem.current },
        }),
      ),
    onSuccess: (o) => {
      idem.current = newIdempotencyKey();
      queryClient.setQueryData(key, o);
      setTitle("");
      setLink("");
      setError(null);
    },
    onError: (e) => setError(`Nie dodano. ${userMessage(e)}`),
  });
  const restore = useMutation({
    mutationFn: (g: Gift) => unwrap(api.POST("/api/v1/weddings/{wedding_id}/gifts", { ...path, body: { kind: g.kind, title: g.title, note: g.note, link: g.link } })),
    onSuccess: (o) => queryClient.setQueryData(key, o),
  });
  const remove = useMutation({
    mutationFn: (g: Gift) => unwrap(api.DELETE("/api/v1/weddings/{wedding_id}/gifts/{gift_id}", { params: { path: { wedding_id: weddingId, gift_id: g.id } } })),
    onSuccess: async (_, g) => {
      await queryClient.invalidateQueries({ queryKey: key });
      toast(`Usunięto: ${g.title}`, g.reserved ? undefined : () => restore.mutate(g));
    },
    onError: (e) => setError(userMessage(e)),
  });
  const ideas = data.data?.ideas ?? [];

  return (
    <section className="form-stack" aria-labelledby="gifts-h">
      <h2 id="gifts-h">
        Lista prezentów{ideas.length > 0 && <span className="text-secondary num"> · wybrane {data.data?.reserved_count ?? 0} z {ideas.filter((g) => g.kind === "item").length}</span>}
      </h2>
      <Card className="form-stack">
        <Checkbox isSelected={enabled} isDisabled={!canWrite || pending} onChange={onToggle}>
          Pokaż gościom listę prezentów — każdy wybierze coś innego (rezerwacje widzicie tylko Wy)
        </Checkbox>
        {ideas.length > 0 && (
          <ul className="row-list">
            {ideas.map((g) => (
              <li key={g.id} className="row">
                <span className="row__body">
                  <span className="row__title">{g.title}</span>
                  {g.link && (
                    <a href={g.link} target="_blank" rel="noopener noreferrer" className="text-secondary link-text">
                      {g.link}
                    </a>
                  )}
                </span>
                <StatusChip tone={g.reserved ? "success" : "neutral"}>{giftState(g)}</StatusChip>
                {canWrite && (
                  <AriaButton className="wp-icon-button" aria-label={`Usuń: ${g.title}`} onPress={() => remove.mutate(g)}>
                    <Trash2 aria-hidden size={20} />
                  </AriaButton>
                )}
              </li>
            ))}
          </ul>
        )}
        {canWrite && (
          <Form
            className="form-stack"
            aria-label="Nowy pomysł na prezent"
            onSubmit={(e) => {
              e.preventDefault();
              if (title.trim()) add.mutate();
            }}
          >
            <Segmented
              label="Rodzaj"
              value={kind}
              options={[
                { value: "item", label: "Rzecz (rezerwacja)" },
                { value: "fund", label: "Fundusz (np. podróż)" },
              ]}
              onChange={setKind}
            />
            <TextField label="Co" value={title} onChange={setTitle} maxLength={200} autoComplete="off" placeholder={kind === "fund" ? "np. Podróż poślubna do Grecji" : "np. Ekspres do kawy"} />
            <TextField label="Link do sklepu (opcjonalnie)" value={link} onChange={setLink} maxLength={500} autoComplete="off" inputMode="url" />
            {error && (
              <Notice tone="error" live>
                {error}
              </Notice>
            )}
            <Button type="submit" variant="secondary" pending={add.isPending} isDisabled={!title.trim()}>
              Dodaj pomysł
            </Button>
          </Form>
        )}
      </Card>
    </section>
  );
}
