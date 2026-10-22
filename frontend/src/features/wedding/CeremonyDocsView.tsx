/** Dokumenty do ślubu: kiedy najwcześniej i najpóźniej je załatwić, żeby były ważne w dniu ślubu. */
import { parseDate, type CalendarDate } from "@internationalized/date";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { DateField } from "../../components/DateField";
import { Checkbox, TextField } from "../../components/Field";
import {
  Card,
  EmptyState,
  Notice,
  Skeleton,
  StatusChip,
  type Tone,
} from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate } from "../../lib/format";
import { PLAN_SECTIONS, SectionNav } from "./SectionNav";
import { useCanWrite, useWeddingId } from "./data";

type Doc = components["schemas"]["CeremonyDocumentOut"];
type Docs = components["schemas"]["CeremonyDocumentsOut"];

/** Etykieta i kolor stanu dokumentu. */
export function docState(
  d: Pick<Doc, "status" | "earliest" | "latest" | "expires_on">,
): { label: string; tone: Tone } {
  switch (d.status) {
    case "too_early":
      return {
        label: d.earliest
          ? `Najwcześniej od ${formatDate(d.earliest)}`
          : "Za wcześnie",
        tone: "neutral",
      };
    case "now":
      return {
        label: d.latest
          ? `Teraz — najpóźniej do ${formatDate(d.latest)}`
          : "Teraz",
        tone: "info",
      };
    case "late":
      return { label: "Po zalecanym terminie", tone: "warning" };
    case "ok":
      return {
        label: d.expires_on ? `Ważny do ${formatDate(d.expires_on)}` : "Ważny",
        tone: "success",
      };
    case "expires":
      return {
        label: d.expires_on
          ? `Straci ważność ${formatDate(d.expires_on)} — przed ślubem`
          : "Straci ważność przed ślubem",
        tone: "error",
      };
    case "done":
      return { label: "Zrobione", tone: "success" };
    default:
      return { label: "Ustawcie datę ślubu", tone: "neutral" };
  }
}

export function CeremonyDocsView() {
  const id = useWeddingId();
  const canWrite = useCanWrite(id);
  const key = ["wedding", id, "ceremony-documents"];
  const docs = useQuery({
    queryKey: key,
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/weddings/{wedding_id}/ceremony-documents", {
          params: { path: { wedding_id: id } },
          signal,
        }),
      ),
  });
  const d = docs.data;
  return (
    <main className="page enter-tab" aria-labelledby="cdocs-h">
      <SectionNav label="Plan" sections={PLAN_SECTIONS} />
      <div>
        <h1 id="cdocs-h">Dokumenty do ślubu</h1>
        <p className="text-secondary">
          Kiedy najwcześniej i najpóźniej je załatwić, żeby były ważne w dniu
          ślubu.
        </p>
      </div>
      {docs.isPending && <Skeleton lines={4} />}
      {docs.isError && (
        <Notice tone="error" live>
          {userMessage(docs.error)}
        </Notice>
      )}
      {d && (
        <DocsBody docs={d} weddingId={id} canWrite={canWrite} queryKey={key} />
      )}
    </main>
  );
}

function DocsBody({
  docs: d,
  weddingId,
  canWrite,
  queryKey,
}: {
  docs: Docs;
  weddingId: string;
  canWrite: boolean;
  queryKey: string[];
}) {
  if (d.ceremony_type === "humanist" || d.ceremony_type === "undecided") {
    return (
      <EmptyState
        title={
          d.ceremony_type === "undecided"
            ? "Wybierzcie rodzaj ślubu"
            : "Ślub humanistyczny nie ma skutków cywilnych"
        }
      >
        {d.ceremony_type === "undecided"
          ? "Lista zależy od tego, czy bierzecie ślub cywilny, czy kościelny. Ustawcie to w ustawieniach wesela."
          : "Jeśli chcecie, by małżeństwo było uznane przez prawo, potrzebny jest też ślub cywilny."}{" "}
        <Link to={`/w/${weddingId}/ustawienia`}>Ustawienia wesela</Link>
      </EmptyState>
    );
  }
  return (
    <>
      {!d.wedding_day && (
        <Notice tone="info">
          Ustawcie datę ślubu — wtedy policzymy terminy.
        </Notice>
      )}
      {d.approximate && d.wedding_day && (
        <Notice tone="warning">
          Liczymy od 1. dnia planowanego miesiąca. Po ustaleniu dokładnej daty
          terminy się poprawią.
        </Notice>
      )}
      <ol className="cdocs">
        {d.items.map((doc) => (
          <li key={doc.code}>
            <DocCard
              doc={doc}
              weddingId={weddingId}
              canWrite={canWrite}
              queryKey={queryKey}
            />
          </li>
        ))}
      </ol>
      <p className="text-secondary">
        To informacja, nie porada prawna. Terminy urzędowe pochodzą z gov.pl, a
        wymagania parafii się różnią — potwierdźcie je w USC i w swojej
        kancelarii parafialnej.
      </p>
    </>
  );
}

function DocCard({
  doc,
  weddingId,
  canWrite,
  queryKey,
}: {
  doc: Doc;
  weddingId: string;
  canWrite: boolean;
  queryKey: string[];
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [issued, setIssued] = useState<CalendarDate | null>(
    doc.issued_on ? parseDate(doc.issued_on) : null,
  );
  const [months, setMonths] = useState(
    doc.valid_months ? String(doc.valid_months) : "",
  );
  const state = docState(doc);
  const save = useMutation({
    mutationFn: (body: {
      issued_on?: string | null;
      done?: boolean;
      valid_months?: number | null;
    }) =>
      unwrap(
        api.PUT("/api/v1/weddings/{wedding_id}/ceremony-documents/{code}", {
          params: { path: { wedding_id: weddingId, code: doc.code } },
          body: {
            issued_on: doc.issued_on,
            done: doc.done,
            valid_months: doc.editable_validity ? doc.valid_months : null,
            ...body,
          },
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKey, data);
      toast("Zapisano");
    },
  });
  const monthsNumber = Number(months);
  const monthsValid =
    months === "" ||
    (Number.isInteger(monthsNumber) && monthsNumber >= 1 && monthsNumber <= 24);
  return (
    <Card className="form-stack">
      <div className="section-head section-head--wrap">
        <h2 className="cdocs__title">{doc.title}</h2>
        <StatusChip tone={state.tone}>{state.label}</StatusChip>
      </div>
      <dl className="cdocs__window">
        {doc.earliest && (
          <div>
            <dt>Najwcześniej</dt>
            <dd>{formatDate(doc.earliest)}</dd>
          </div>
        )}
        {doc.latest && (
          <div>
            <dt>Najpóźniej</dt>
            <dd>{formatDate(doc.latest)}</dd>
          </div>
        )}
        {doc.valid_months && (
          <div>
            <dt>Ważność</dt>
            <dd>{doc.valid_months} mies. od wydania</dd>
          </div>
        )}
      </dl>
      <p className="text-secondary">{doc.hint}</p>
      <a
        href={doc.source}
        target="_blank"
        rel="noreferrer noopener"
        className="cdocs__source"
      >
        Źródło: {doc.source_label}
        <ExternalLink aria-hidden size={16} />
      </a>
      {save.isError && (
        <Notice tone="error" live>
          Nie zapisano. {userMessage(save.error)}
        </Notice>
      )}
      {canWrite &&
        (doc.has_validity ? (
          <div className="cdocs__edit">
            <DateField
              label="Data wydania"
              value={issued}
              onChange={setIssued}
            />
            {doc.editable_validity && (
              <TextField
                label="Ważność w Waszej parafii (miesiące)"
                inputMode="numeric"
                value={months}
                onChange={setMonths}
                error={monthsValid ? undefined : "Od 1 do 24 miesięcy."}
              />
            )}
            <div className="wp-sheet__actions">
              <Button
                variant="secondary"
                pending={save.isPending}
                isDisabled={!monthsValid}
                onPress={() =>
                  save.mutate({
                    issued_on: issued ? issued.toString() : null,
                    ...(doc.editable_validity
                      ? { valid_months: months ? monthsNumber : null }
                      : {}),
                  })
                }
              >
                Zapisz
              </Button>
            </div>
          </div>
        ) : (
          <Checkbox
            isSelected={doc.done}
            onChange={(done) => save.mutate({ done })}
          >
            Zrobione
          </Checkbox>
        ))}
    </Card>
  );
}
