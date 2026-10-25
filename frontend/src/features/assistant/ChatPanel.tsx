import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { TextAreaField } from "../../components/Field";
import { Notice, Skeleton } from "../../components/Surface";
import { useCanWrite } from "../wedding/data";
import { MatchCard } from "./MatchCard";
import { aKeys, useConversations, useMessages, useSaveCandidate, type Match, type Message } from "./assistant";

const TOOL_LABEL: Record<string, string> = {
  get_wedding_search_context: "Odczytano dane wesela potrzebne do doboru",
  update_search_preferences: "Zapisano preferencje",
  search_catalog: "Przeszukano katalog",
  get_vendor_evidence: "Sprawdzono źródła ceny",
  request_discovery: "Zlecono odświeżenie źródeł",
  save_candidate: "Zapisano na liście kandydatów",
  compare_candidates: "Porównano firmy",
  draft_inquiry: "Przygotowano szkice zapytań",
  get_inquiry_status: "Sprawdzono stan zapytań",
};

function Bubble({ m, id, canWrite }: { m: Message; id: string; canWrite: boolean }) {
  const save = useSaveCandidate(id);
  const mine = m.role === "user";
  if (m.state === "pending") {
    return (
      <li className="chat__msg chat__msg--assistant" aria-live="polite">
        <p className="text-secondary">Asystent przygotowuje odpowiedź… Możesz odświeżyć stronę — zadanie nie przepada.</p>
      </li>
    );
  }
  const drafts = m.actions.flatMap((a) => (Array.isArray(a.inquiry_ids) ? (a.inquiry_ids as string[]) : []));
  return (
    <li className={`chat__msg chat__msg--${mine ? "user" : "assistant"}`}>
      <p className="chat__author">{mine ? "Wy" : "Asystent"}</p>
      <p className="chat__text">{m.content}</p>
      {m.state === "failed" && <Notice tone="error">Nie udało się przygotować odpowiedzi. Spróbuj ponownie.</Notice>}
      {m.actions.length > 0 && (
        <details className="chat__actions">
          <summary>Co zrobił asystent ({m.actions.length})</summary>
          <ul>
            {m.actions.map((a, i) => (
              <li key={i}>
                {TOOL_LABEL[String(a.tool)] ?? String(a.tool)}: {String(a.summary ?? "")}
                {a.ok === false && " (nie udało się)"}
              </li>
            ))}
          </ul>
        </details>
      )}
      {drafts.length > 0 && (
        <Notice tone="info" title="Szkice czekają na Waszą zgodę">
          Nic nie zostało wysłane. <Link to={`/w/${id}/dobor?zakladka=zapytania`}>Przejrzyjcie i zatwierdźcie zapytania</Link>.
        </Notice>
      )}
      {(m.cards as unknown as Match[]).map((card) => (
        <MatchCard
          key={card.catalog_vendor_id}
          match={card}
          actions={
            canWrite && (
              <Button
                variant="secondary"
                pending={save.isPending}
                onPress={() => save.mutate({ catalog_vendor_id: card.catalog_vendor_id })}
              >
                Zapisz na liście
              </Button>
            )
          }
        />
      ))}
    </li>
  );
}

export function ChatPanel({ id }: { id: string }) {
  const canWrite = useCanWrite(id);
  const qc = useQueryClient();
  const conversations = useConversations(id);
  const [chosenId, setConversationId] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const key = useRef(newIdempotencyKey());
  const endRef = useRef<HTMLDivElement>(null);

  // Wracamy do ostatniej rozmowy (odświeżenie strony nie gubi wątku).
  const conversationId = chosenId ?? conversations.data?.[0]?.id ?? null;

  const messages = useMessages(id, conversationId);
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [messages.data?.length]);

  const send = useMutation({
    mutationFn: async (value: string) => {
      let cid = conversationId;
      if (cid === null) {
        const created = await unwrap(api.POST("/api/v1/weddings/{wedding_id}/concierge/conversations", { params: { path: { wedding_id: id } } }));
        cid = created.id;
        setConversationId(cid);
      }
      return unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/concierge/conversations/{conversation_id}/messages", {
          params: { path: { wedding_id: id, conversation_id: cid } },
          body: { text: value },
          headers: { "Idempotency-Key": key.current },
        }),
      );
    },
    onSuccess: () => {
      key.current = newIdempotencyKey();
      setText("");
      setError(null);
      void qc.invalidateQueries({ queryKey: aKeys.conversations(id) });
      if (conversationId) void qc.invalidateQueries({ queryKey: aKeys.messages(id, conversationId) });
    },
    onError: (e) => setError(userMessage(e)),
  });

  const list = messages.data ?? [];
  const busy = list.some((m) => m.state === "pending");
  return (
    <section className="chat" aria-label="Rozmowa z asystentem">
      <Notice tone="info">
        Asystent dobiera firmy z katalogu aplikacji i pokazuje źródła. Niczego nie rezerwuje i nie wysyła do firm —
        zapytania zawsze zatwierdzacie sami. Brak informacji o terminie oznacza „dostępność niepotwierdzona”.
      </Notice>
      {messages.isPending && conversationId !== null && <Skeleton lines={3} />}
      {list.length === 0 && conversationId === null && !conversations.isPending && (
        <p className="text-secondary">
          Napisz, czego szukacie, np. „Szukamy fotografa do 6000 zł, naturalne zdjęcia, bez długiej sesji w dniu ślubu”.
        </p>
      )}
      <ol className="chat__list" aria-label="Wiadomości">
        {list.map((m) => (
          <Bubble key={m.id} m={m} id={id} canWrite={canWrite} />
        ))}
      </ol>
      <div ref={endRef} />
      {canWrite ? (
        <form
          className="chat__form"
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim() && !busy) send.mutate(text.trim());
          }}
        >
          <TextAreaField label="Wiadomość do asystenta" value={text} onChange={setText} rows={3} error={error} />
          <Button type="submit" icon={<Send aria-hidden size={18} />} pending={send.isPending} isDisabled={busy || !text.trim()}>
            Wyślij
          </Button>
        </form>
      ) : (
        <Notice tone="neutral">Masz dostęp tylko do podglądu — rozmowę mogą prowadzić właściciel i współorganizator.</Notice>
      )}
    </section>
  );
}
