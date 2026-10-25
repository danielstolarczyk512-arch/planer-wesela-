import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { Checkbox, TextAreaField, TextField } from "../../components/Field";
import { Sheet } from "../../components/Overlay";
import { Card, EmptyState, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { useCanWrite } from "../wedding/data";
import { INQUIRY_STATUS, aKeys, formatDay, useInquiries, type Inquiry } from "./assistant";

function ReviewSheet({
  id,
  inquiries,
  isOpen,
  onClose,
}: {
  id: string;
  inquiries: Inquiry[];
  isOpen: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [edits, setEdits] = useState<Record<string, { to: string; subject: string; body: string }>>({});
  const [ack, setAck] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [key] = useState(newIdempotencyKey);
  const single = inquiries.length === 1;

  const view = (i: Inquiry) => edits[i.id] ?? { to: i.revision.to_email, subject: i.revision.subject, body: i.revision.body };
  const dirty = (i: Inquiry) => {
    const v = view(i);
    return v.to !== i.revision.to_email || v.subject !== i.revision.subject || v.body !== i.revision.body;
  };
  const warnings = inquiries.flatMap((i) => i.warnings);

  const send = useMutation({
    mutationFn: async () => {
      // Zmieniona treść albo adresat = nowa rewizja; zgoda dotyczy dokładnie tego, co widać na ekranie.
      const current: Inquiry[] = [];
      for (const i of inquiries) {
        if (dirty(i)) {
          const v = view(i);
          current.push(
            await unwrap(
              api.PUT("/api/v1/weddings/{wedding_id}/inquiries/{inquiry_id}", {
                params: { path: { wedding_id: id, inquiry_id: i.id } },
                body: { base_revision: i.revision.number, to_email: v.to, subject: v.subject, body: v.body },
              }),
            ),
          );
        } else current.push(i);
      }
      const stillWarned = current.some((i) => i.warnings.length > 0);
      if (stillWarned && !ack) throw new Error("ack");
      return unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/inquiries-approve-and-send", {
          params: { path: { wedding_id: id } },
          headers: { "Idempotency-Key": key },
          body: {
            items: current.map((i) => [
              i.id,
              {
                revision_id: i.revision.id,
                content_hash: i.revision.content_hash,
                to_email: i.revision.to_email,
                acknowledge_warnings: ack,
              },
            ]),
          },
        }),
      );
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: aKeys.inquiries(id) });
      toast(single ? "Zapytanie przekazane do wysyłki." : `Zapytań przekazanych do wysyłki: ${inquiries.length}.`);
      onClose();
    },
    onError: (e) => {
      if (e instanceof Error && e.message === "ack") setError("Treść zawiera ostrzeżenia. Zaznacz, że to zamierzone, albo popraw treść.");
      else setError(userMessage(e));
      void qc.invalidateQueries({ queryKey: aKeys.inquiries(id) });
    },
  });

  const disclosed = inquiries[0]?.disclosed ?? [];
  const outbound = inquiries.every((i) => i.outbound_enabled);
  return (
    <Sheet
      title={single ? "Zatwierdź zapytanie" : `Zatwierdź ${inquiries.length} zapytania`}
      isOpen={isOpen}
      onOpenChange={(o) => !o && onClose()}
      isDirty={inquiries.some(dirty)}
    >
      <div className="form-stack">
        <Notice tone="info" title="Co zobaczy firma">
          <ul className="match__list">
            {disclosed.map((d) => (
              <li key={d.label}>
                {d.label}: <strong>{d.value}</strong>
              </li>
            ))}
          </ul>
          Nie ujawniamy budżetu. Odpowiedź firmy trafi na adres do odpowiedzi.
        </Notice>
        {!outbound && (
          <Notice tone="warning" title="Wysyłka do firm jest wyłączona">
            Na razie możesz skopiować treść i wysłać ją samodzielnie.
          </Notice>
        )}
        {inquiries.map((i) => {
          const v = view(i);
          const set = (patch: Partial<typeof v>) => setEdits((e) => ({ ...e, [i.id]: { ...v, ...patch } }));
          return (
            <Card key={i.id} as="div">
              <h3>{i.vendor_name}</h3>
              <TextField label="Adres e-mail firmy" value={v.to} onChange={(to) => set({ to })} />
              <TextField label="Temat" value={v.subject} onChange={(subject) => set({ subject })} />
              <TextAreaField label="Treść" value={v.body} onChange={(body) => set({ body })} rows={12} />
              {dirty(i) && <p className="text-secondary">Zmiana treści albo adresata tworzy nową wersję — zgoda dotyczy tego, co widzisz teraz.</p>}
            </Card>
          );
        })}
        {warnings.length > 0 && (
          <Notice tone="warning" title="Sprawdź przed wysłaniem">
            <ul className="match__list">
              {warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
            <Checkbox isSelected={ack} onChange={setAck}>
              To zamierzone, wyślij mimo to
            </Checkbox>
          </Notice>
        )}
        {error && <Notice tone="error" live>{error}</Notice>}
        <Button pending={send.isPending} isDisabled={!outbound} onPress={() => send.mutate()}>
          {single ? "Zatwierdź i wyślij 1 zapytanie" : `Zatwierdź i wyślij ${inquiries.length} zapytania`}
        </Button>
        <Button variant="text" onPress={onClose}>
          Anuluj — nic nie wysyłaj
        </Button>
      </div>
    </Sheet>
  );
}

function ResponseSheet({ id, inquiry, isOpen, onClose }: { id: string; inquiry: Inquiry; isOpen: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const add = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/inquiries/{inquiry_id}/import-response", {
          params: { path: { wedding_id: id, inquiry_id: inquiry.id } },
          body: { text, subject: `Odpowiedź: ${inquiry.vendor_name}` },
        }),
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: aKeys.inquiries(id) });
      toast("Dodano odpowiedź firmy.");
      setText("");
      onClose();
    },
    onError: (e) => setError(userMessage(e)),
  });
  return (
    <Sheet title={`Odpowiedź: ${inquiry.vendor_name}`} isOpen={isOpen} onOpenChange={(o) => !o && onClose()} isDirty={text.length > 0}>
      <div className="form-stack">
        <p className="text-secondary">
          Wklej treść odpowiedzi z poczty. Zapiszemy ją w wątku zapytania i jako dokument, który możesz przeanalizować — wynik to szkic
          oferty do sprawdzenia, a nie gotowa cena.
        </p>
        <TextAreaField label="Treść odpowiedzi firmy" value={text} onChange={setText} rows={10} error={error} />
        <Button pending={add.isPending} isDisabled={!text.trim()} onPress={() => add.mutate()}>
          Dodaj odpowiedź
        </Button>
      </div>
    </Sheet>
  );
}

function InquiryRow({ id, inquiry, picked, onPick, onReview }: { id: string; inquiry: Inquiry; picked: boolean; onPick: (on: boolean) => void; onReview: () => void }) {
  const canWrite = useCanWrite(id);
  const qc = useQueryClient();
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const st = INQUIRY_STATUS[inquiry.status] ?? INQUIRY_STATUS.draft!;
  const isDraft = inquiry.status === "draft" || inquiry.status === "draft_revised";
  const analyze = useMutation({
    mutationFn: (responseId: string) =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/inquiries/{inquiry_id}/responses/{response_id}/analyze", {
          params: { path: { wedding_id: id, inquiry_id: inquiry.id, response_id: responseId } },
        }),
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["wedding", id, "offers"] });
      toast("Analiza uruchomiona. Szkic oferty pojawi się w usługodawcy do sprawdzenia.");
    },
  });
  return (
    <li className="row inq">
      {canWrite && isDraft && (
        <Checkbox isSelected={picked} onChange={onPick}>
          <span className="visually-hidden">Wybierz zapytanie do {inquiry.vendor_name}</span>
        </Checkbox>
      )}
      <span className="row__body">
        <span className="row__title">{inquiry.vendor_name}</span>
        <span className="text-secondary">{inquiry.revision.subject}</span>
        {inquiry.delivery && <span className="text-secondary">{inquiry.delivery.note}</span>}
        {inquiry.responses.map((r) => (
          <span key={r.id} className="text-secondary">
            Odpowiedź z {formatDay(r.created_at)}:{" "}
            {canWrite && (
              <Button variant="text" pending={analyze.isPending} onPress={() => analyze.mutate(r.id)}>
                Przeanalizuj (szkic oferty)
              </Button>
            )}
          </span>
        ))}
        {analyze.isError && <Notice tone="error" live>{userMessage(analyze.error)}</Notice>}
      </span>
      <StatusChip tone={st.tone}>{st.label}</StatusChip>
      {canWrite && isDraft && (
        <Button variant="secondary" onPress={onReview}>
          Przejrzyj i zatwierdź
        </Button>
      )}
      {canWrite && !isDraft && (
        <Button variant="text" onPress={() => setAdding(true)}>
          Dodaj odpowiedź
        </Button>
      )}
      {adding && <ResponseSheet id={id} inquiry={inquiry} isOpen onClose={() => setAdding(false)} />}
    </li>
  );
}

export function InquiriesPanel({ id }: { id: string }) {
  const inquiries = useInquiries(id);
  const [picked, setPicked] = useState<string[]>([]);
  const [reviewing, setReviewing] = useState<string[] | null>(null);
  if (inquiries.isPending) return <Skeleton lines={4} />;
  if (inquiries.isError) return <Notice tone="error" live>{userMessage(inquiries.error)}</Notice>;
  const list = inquiries.data ?? [];
  if (list.length === 0)
    return (
      <EmptyState title="Nie ma jeszcze zapytań">
        Wybierzcie firmy na liście kandydatów albo poproście asystenta: „Zapytaj tych trzech o termin”. Szkic zawsze najpierw oglądacie.
      </EmptyState>
    );
  const toReview = list.filter((i) => reviewing?.includes(i.id));
  return (
    <div className="form-stack">
      <Notice tone="info">
        „Wysłano” oznacza przyjęcie wiadomości przez serwer pocztowy — nie doręczenie ani przeczytanie. Odpowiedzi firm dodajecie na razie ręcznie
        (<Link to={`/w/${id}/uslugodawcy`}>oferty</Link> trafiają do porównania dopiero po Waszym zatwierdzeniu).
      </Notice>
      <Card>
        <ul className="row-list">
          {list.map((i) => (
            <InquiryRow
              key={i.id}
              id={id}
              inquiry={i}
              picked={picked.includes(i.id)}
              onPick={(on) => setPicked((p) => (on ? [...p, i.id] : p.filter((x) => x !== i.id)))}
              onReview={() => setReviewing([i.id])}
            />
          ))}
        </ul>
      </Card>
      {picked.length > 1 && (
        <Button onPress={() => setReviewing(picked)}>{`Przejrzyj i zatwierdź ${picked.length} zapytania`}</Button>
      )}
      {reviewing && toReview.length > 0 && (
        <ReviewSheet
          key={reviewing.join(",")}
          id={id}
          inquiries={toReview}
          isOpen
          onClose={() => {
            setReviewing(null);
            setPicked([]);
          }}
        />
      )}
    </div>
  );
}
