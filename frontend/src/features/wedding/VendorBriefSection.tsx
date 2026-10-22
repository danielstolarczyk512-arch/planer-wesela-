/** Informacje dla usługodawcy (na jego linku z programem dnia) i stan potwierdzenia wersji. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Form } from "react-aria-components";
import { Link } from "react-router";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { TextAreaField, TextField } from "../../components/Field";
import { BriefView } from "../../components/BriefView";
import { Card, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate } from "../../lib/format";
import { briefLabels, linesToList, linesToPeople, peopleToLines } from "../../lib/vendorBrief";
import { ifMatch, saveErrorMessage } from "./mutations";

type Brief = components["schemas"]["BriefOut"];
export type BriefStatus = components["schemas"]["BriefStatus"];

const NL = String.fromCharCode(10);

export const briefKeys = {
  brief: (weddingId: string, vendorId: string) => ["wedding", weddingId, "vendors", vendorId, "brief"] as const,
  statuses: (weddingId: string) => ["wedding", weddingId, "vendor-briefs"] as const,
};

/** Krótki opis stanu potwierdzenia (lista „kto zna aktualny program” i karta usługodawcy). */
export function ackText(s: Pick<BriefStatus, "version" | "acknowledged_version" | "acknowledged_at" | "up_to_date">): string {
  if (s.up_to_date) return `Potwierdził wersję ${s.version}${s.acknowledged_at ? ` (${formatDate(s.acknowledged_at.slice(0, 10))})` : ""}.`;
  if (s.acknowledged_version) return `Zna wersję ${s.acknowledged_version}, a aktualna to ${s.version} — po zmianach jeszcze nie potwierdził.`;
  return `Nie potwierdził jeszcze programu (aktualna wersja ${s.version}).`;
}

export function VendorBriefSection({
  weddingId,
  vendorId,
  vendorCategory,
  canWrite,
}: {
  weddingId: string;
  vendorId: string;
  vendorCategory: string;
  canWrite: boolean;
}) {
  const brief = useQuery({
    queryKey: briefKeys.brief(weddingId, vendorId),
    queryFn: ({ signal }) =>
      unwrap(api.GET("/api/v1/weddings/{wedding_id}/vendors/{vendor_id}/brief", { params: { path: { wedding_id: weddingId, vendor_id: vendorId } }, signal })),
  });
  const statuses = useQuery({
    queryKey: briefKeys.statuses(weddingId),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/vendor-briefs", { params: { path: { wedding_id: weddingId } }, signal })),
  });
  const status = statuses.data?.find((s) => s.vendor_id === vendorId);
  const labels = briefLabels(vendorCategory);

  return (
    <section className="form-stack" aria-labelledby={`brief-${vendorId}`}>
      <h2 id={`brief-${vendorId}`}>Informacje dla usługodawcy</h2>
      <p className="text-secondary">
        Usługodawca zobaczy je na swoim linku z programem dnia. Każda zmiana programu lub tych informacji to nowa wersja — usługodawca
        potwierdza, że ją przeczytał.
      </p>
      {status && (
        <Notice tone={status.up_to_date ? "success" : "warning"}>
          {ackText(status)}
          {!status.up_to_date && " Dajcie znać usługodawcy, żeby otworzył link i potwierdził."}
        </Notice>
      )}
      {brief.isPending && <Skeleton lines={3} />}
      {brief.isError && (
        <Notice tone="error" live>
          {userMessage(brief.error)}
        </Notice>
      )}
      {brief.data && <BriefForm key={brief.data.version} weddingId={weddingId} brief={brief.data} labels={labels} canWrite={canWrite} />}
    </section>
  );
}

function BriefForm({
  weddingId,
  brief,
  labels,
  canWrite,
}: {
  weddingId: string;
  brief: Brief;
  labels: ReturnType<typeof briefLabels>;
  canWrite: boolean;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [must, setMust] = useState(brief.must?.join(NL) ?? "");
  const [avoid, setAvoid] = useState(brief.avoid?.join(NL) ?? "");
  const [people, setPeople] = useState(peopleToLines(brief.people ?? []));
  const [notes, setNotes] = useState(brief.notes ?? "");
  const [contact, setContact] = useState(brief.contact ?? "");
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.PUT("/api/v1/weddings/{wedding_id}/vendors/{vendor_id}/brief", {
          params: { path: { wedding_id: weddingId, vendor_id: brief.vendor_id } },
          body: {
            must: linesToList(must),
            avoid: linesToList(avoid),
            people: linesToPeople(people),
            notes: notes.trim() || null,
            contact: contact.trim() || null,
          },
          headers: ifMatch(brief.version),
        }),
      ),
    onSuccess: async (saved) => {
      setError(null);
      queryClient.setQueryData(briefKeys.brief(weddingId, brief.vendor_id), saved);
      await queryClient.invalidateQueries({ queryKey: briefKeys.statuses(weddingId) });
      toast("Zapisano informacje dla usługodawcy");
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [briefKeys.brief(weddingId, brief.vendor_id)])),
  });

  if (!canWrite) {
    const empty = !brief.must?.length && !brief.avoid?.length && !brief.people?.length && !brief.notes && !brief.contact;
    return (
      <Card>
        {empty ? (
          <p className="text-secondary">Bez dodatkowych informacji.</p>
        ) : (
          <BriefView brief={brief} labels={labels} />
        )}
      </Card>
    );
  }
  return (
    <Card>
      <Form
        className="form-stack"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <TextAreaField label={labels.must} description={`${labels.mustHint} Jedna pozycja w wierszu.`} value={must} onChange={setMust} />
        <TextAreaField label={labels.avoid} description="Jedna pozycja w wierszu." value={avoid} onChange={setAvoid} rows={3} />
        <TextAreaField
          label={labels.people}
          description="W wierszu: imię — kim jest, np. „Babcia Halina — mama Pana Młodego”. Wpiszcie tylko to, co potrzebne."
          value={people}
          onChange={setPeople}
          rows={3}
        />
        <TextAreaField label="Inne uwagi" value={notes} onChange={setNotes} rows={3} />
        <TextField label="Kontakt w dniu ślubu" description="Np. świadek albo koordynator dnia (imię i telefon)." value={contact} onChange={setContact} />
        {error && (
          <Notice tone="error" live>
            {error}
          </Notice>
        )}
        <div className="wp-sheet__actions">
          <Button type="submit" variant="secondary" pending={save.isPending}>
            Zapisz informacje
          </Button>
        </div>
      </Form>
    </Card>
  );
}

/** Harmonogram: którzy usługodawcy z linkiem potwierdzili aktualną wersję programu. */
export function VendorAckSummary({ weddingId }: { weddingId: string }) {
  const statuses = useQuery({
    queryKey: briefKeys.statuses(weddingId),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/vendor-briefs", { params: { path: { wedding_id: weddingId } }, signal })),
  });
  const list = statuses.data ?? [];
  if (list.length === 0) return null;
  const behind = list.filter((s) => !s.up_to_date).length;
  return (
    <section className="form-stack" aria-labelledby="ack-h">
      <h2 id="ack-h">Kto zna aktualny program</h2>
      <p className="text-secondary">
        {behind === 0 ? "Wszyscy usługodawcy z linkiem potwierdzili aktualną wersję." : `Bez potwierdzenia aktualnej wersji: ${behind} z ${list.length}.`}
      </p>
      <Card>
        <ul className="row-list">
          {list.map((s) => (
            <li key={s.vendor_id}>
              <Link to={`/w/${weddingId}/uslugodawcy/${s.vendor_id}`} className="row link-card">
                <span className="row__body">
                  <span className="row__title">{s.vendor_name}</span>
                  <span className="text-secondary">{ackText(s)}</span>
                </span>
                <StatusChip tone={s.up_to_date ? "success" : "warning"}>{s.up_to_date ? `Wersja ${s.version}` : "Do potwierdzenia"}</StatusChip>
              </Link>
            </li>
          ))}
        </ul>
      </Card>
    </section>
  );
}
