/** Komentarze przy zadaniu: krótka rozmowa pary i współorganizatorów (ustalenia nie giną w komunikatorach). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { TextAreaField } from "../../components/Field";
import { Notice } from "../../components/Surface";
import { formatTime } from "../../lib/format";
import { useCanWrite, useWedding } from "./data";

/** „22.10, 14:05” — dzień i godzina wpisu (czas polski). */
export function commentWhen(iso: string): string {
  const day = new Date(iso).toLocaleDateString("pl-PL", { timeZone: "Europe/Warsaw", day: "2-digit", month: "2-digit" });
  return `${day}, ${formatTime(iso)}`;
}

export function TaskComments({ weddingId, taskId }: { weddingId: string; taskId: string }) {
  const queryClient = useQueryClient();
  const canWrite = useCanWrite(weddingId);
  const owner = useWedding(weddingId).data?.my_role === "owner";
  const key = ["wedding", weddingId, "tasks", taskId, "comments"];
  const params = { params: { path: { wedding_id: weddingId, task_id: taskId } } };
  const list = useQuery({ queryKey: key, queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/tasks/{task_id}/comments", { ...params, signal })) });
  const [text, setText] = useState("");
  const add = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/weddings/{wedding_id}/tasks/{task_id}/comments", { ...params, body: { text: text.trim() } })),
    onSuccess: (rows) => {
      queryClient.setQueryData(key, rows);
      setText("");
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) =>
      unwrap(api.DELETE("/api/v1/weddings/{wedding_id}/tasks/{task_id}/comments/{comment_id}", { params: { path: { wedding_id: weddingId, task_id: taskId, comment_id: id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });
  const rows = list.data ?? [];
  if (!canWrite && rows.length === 0) return null;

  return (
    <section className="form-stack item-payments" aria-labelledby={`comments-${taskId}`}>
      <h3 id={`comments-${taskId}`}>Komentarze{rows.length > 0 && <span className="text-secondary num"> · {rows.length}</span>}</h3>
      {rows.length > 0 && (
        <ul className="row-list">
          {rows.map((c) => (
            <li key={c.id} className="row">
              <span className="row__body">
                <span className="prewrap">{c.text}</span>
                <span className="text-secondary num">
                  {c.mine ? "Ty" : c.author_name} · {commentWhen(c.created_at)}
                </span>
              </span>
              {(c.mine || owner) && canWrite && (
                <AriaButton className="wp-icon-button" aria-label={`Usuń komentarz: ${c.text.slice(0, 30)}`} onPress={() => remove.mutate(c.id)}>
                  <Trash2 aria-hidden size={20} />
                </AriaButton>
              )}
            </li>
          ))}
        </ul>
      )}
      {(add.isError || remove.isError) && (
        <Notice tone="error" live>
          {userMessage(add.error ?? remove.error)}
        </Notice>
      )}
      {canWrite && (
        <Form
          className="form-stack"
          aria-label="Nowy komentarz"
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim()) add.mutate();
          }}
        >
          <TextAreaField label="Dopisz komentarz" value={text} onChange={setText} maxLength={1000} rows={2} />
          <Button type="submit" variant="secondary" pending={add.isPending} isDisabled={!text.trim()}>
            Dodaj komentarz
          </Button>
        </Form>
      )}
    </section>
  );
}
