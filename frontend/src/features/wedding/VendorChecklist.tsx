/** Pytania do usługodawcy i lista kontrolna umowy (bez oceny prawnej). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { TextField } from "../../components/Field";
import { Sheet } from "../../components/Overlay";
import { PremiumBadge } from "../../components/Premium";
import { Segmented } from "../../components/Segmented";
import { Card, Notice, StatusChip } from "../../components/Surface";
import { ifMatch, saveErrorMessage } from "./mutations";

export type ChecklistItem = components["schemas"]["ChecklistItemOut"];
type Kind = ChecklistItem["kind"];
type Status = ChecklistItem["status"];

export const checklistKey = (weddingId: string) => ["wedding", weddingId, "vendor-checklist"] as const;

/** Wszystkie pozycje wesela (małe listy) — używane też w porównaniu ofert. */
export function useChecklist(weddingId: string) {
  return useQuery({
    queryKey: checklistKey(weddingId),
    queryFn: ({ signal }) =>
      unwrap(api.GET("/api/v1/weddings/{wedding_id}/vendor-checklist", { params: { path: { wedding_id: weddingId } }, signal })),
  });
}

const COPY: Record<Kind, { title: string; empty: string; add: string; custom: string }> = {
  question: {
    title: "Pytania przed rezerwacją",
    empty: "Lista pytań, które warto zadać tej firmie przed podpisaniem umowy. Odpowiedzi zobaczycie też w porównaniu ofert.",
    add: "Dodaj podpowiadane pytania",
    custom: "Własne pytanie",
  },
  contract: {
    title: "Co sprawdzić w umowie",
    empty: "Lista zapisów, które powinny znaleźć się w umowie. Zaznaczacie tylko, czy zapis jest — oceny prawnej dokona prawnik.",
    add: "Dodaj listę kontrolną umowy",
    custom: "Własny punkt",
  },
};

const STATUS_OPTIONS: { value: Status; label: string }[] = [
  { value: "ok", label: "Jest" },
  { value: "missing", label: "Brakuje" },
  { value: "open", label: "Nie sprawdzone" },
];

export function VendorChecklist({ weddingId, vendorId, kind, canWrite }: { weddingId: string; vendorId: string; kind: Kind; canWrite: boolean }) {
  const queryClient = useQueryClient();
  const checklist = useChecklist(weddingId);
  const items = (checklist.data ?? []).filter((i) => i.vendor_id === vendorId && i.kind === kind);
  const [error, setError] = useState<string | null>(null);
  const [answering, setAnswering] = useState<ChecklistItem | null>(null);
  const [custom, setCustom] = useState("");
  const copy = COPY[kind];
  const refresh = () => queryClient.invalidateQueries({ queryKey: checklistKey(weddingId) });
  const params = { path: { wedding_id: weddingId, vendor_id: vendorId } };

  const addStandard = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/weddings/{wedding_id}/vendors/{vendor_id}/checklist/standard", { params, body: { kind } })),
    onSuccess: refresh,
    onError: (e) => setError(userMessage(e)),
  });
  const addCustom = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/weddings/{wedding_id}/vendors/{vendor_id}/checklist", { params, body: { kind, text: custom.trim() } })),
    onSuccess: async () => {
      setCustom("");
      await refresh();
    },
    onError: (e) => setError(userMessage(e)),
  });
  const setStatus = useMutation({
    mutationFn: ({ item, status }: { item: ChecklistItem; status: Status }) =>
      unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/vendor-checklist/{item_id}", {
          params: { path: { wedding_id: weddingId, item_id: item.id } },
          body: { status },
          headers: ifMatch(item.version),
        }),
      ),
    onSuccess: refresh,
    onError: (e) => setError(saveErrorMessage(e, queryClient, [checklistKey(weddingId)])),
  });

  const done = items.filter((i) => i.status === "ok").length;
  const missing = items.filter((i) => i.status === "missing").length;

  return (
    <section className="form-stack" aria-labelledby={`cl-${kind}-${vendorId}`}>
      <div className="section-head">
        <h2 id={`cl-${kind}-${vendorId}`}>
          {copy.title} {kind === "contract" && <PremiumBadge />}
        </h2>
        {items.length > 0 && (
          <span className="text-secondary num">
            {done} z {items.length}
            {missing > 0 && ` · brakuje: ${missing}`}
          </span>
        )}
      </div>
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      <Card>
        {items.length === 0 ? (
          <div className="form-stack">
            <p className="text-secondary">{copy.empty}</p>
            {canWrite && (
              <Button variant="secondary" pending={addStandard.isPending} onPress={() => addStandard.mutate()}>
                {copy.add}
              </Button>
            )}
          </div>
        ) : kind === "question" ? (
          <ul className="row-list">
            {items.map((i) => (
              <li key={i.id}>
                {canWrite ? (
                  <AriaButton className="row-edit" onPress={() => setAnswering(i)}>
                    <span className="row__title">{i.text}</span>
                    <span className="text-secondary">{i.answer ?? "Dotknijcie, aby wpisać odpowiedź"}</span>
                  </AriaButton>
                ) : (
                  <div className="row__body">
                    <span className="row__title">{i.text}</span>
                    <span className="text-secondary">{i.answer ?? "Bez odpowiedzi"}</span>
                  </div>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <ul className="row-list">
            {items.map((i) => (
              <li key={i.id} className="checklist-row">
                {canWrite ? (
                  <Segmented<Status>
                    label={i.text}
                    variant="chips"
                    value={i.status}
                    options={STATUS_OPTIONS}
                    onChange={(status) => setStatus.mutate({ item: i, status })}
                  />
                ) : (
                  <div className="row">
                    <span className="row__body">{i.text}</span>
                    <StatusChip tone={i.status === "ok" ? "success" : i.status === "missing" ? "warning" : "neutral"}>
                      {STATUS_OPTIONS.find((o) => o.value === i.status)?.label}
                    </StatusChip>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
      {kind === "contract" && missing > 0 && (
        <Notice tone="warning" title="Czegoś brakuje w umowie">
          Poproście usługodawcę o dopisanie brakujących punktów przed podpisaniem. Jeśli macie wątpliwości co do treści umowy, skonsultujcie ją
          z prawnikiem — aplikacja nie ocenia umów.
        </Notice>
      )}
      {canWrite && items.length > 0 && (
        <Form
          className="inline-add"
          onSubmit={(e) => {
            e.preventDefault();
            if (custom.trim()) addCustom.mutate();
          }}
        >
          <TextField label={copy.custom} value={custom} onChange={setCustom} maxLength={300} />
          <Button type="submit" variant="secondary" icon={<Plus aria-hidden size={18} />} pending={addCustom.isPending}>
            Dodaj
          </Button>
        </Form>
      )}
      <AnswerSheet weddingId={weddingId} item={answering} onClose={() => setAnswering(null)} />
    </section>
  );
}

function AnswerSheet({ weddingId, item, onClose }: { weddingId: string; item: ChecklistItem | null; onClose: () => void }) {
  return (
    <Sheet title="Odpowiedź" isOpen={!!item} onOpenChange={(o) => !o && onClose()}>
      {item && <AnswerForm key={`${item.id}-${item.version}`} weddingId={weddingId} item={item} onClose={onClose} />}
    </Sheet>
  );
}

function AnswerForm({ weddingId, item, onClose }: { weddingId: string; item: ChecklistItem; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [answer, setAnswer] = useState(item.answer ?? "");
  const [error, setError] = useState<string | null>(null);
  const path = { wedding_id: weddingId, item_id: item.id };
  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/vendor-checklist/{item_id}", {
          params: { path },
          body: { answer: answer.trim() || null },
          headers: ifMatch(item.version),
        }),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: checklistKey(weddingId) });
      onClose();
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [checklistKey(weddingId)])),
  });
  const remove = useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/v1/weddings/{wedding_id}/vendor-checklist/{item_id}", { params: { path } })),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: checklistKey(weddingId) });
      onClose();
    },
    onError: (e) => setError(userMessage(e)),
  });
  return (
    <Form
      className="form-stack"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      <TextField label={item.text} value={answer} onChange={setAnswer} maxLength={2000} autoFocus />
      <Button type="submit" block pending={save.isPending}>
        Zapisz
      </Button>
      <Button variant="text" pending={remove.isPending} onPress={() => remove.mutate()}>
        Usuń pytanie
      </Button>
    </Form>
  );
}
