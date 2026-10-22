/** Portfel sponsorów: kto poza parą dokłada się do wesela, ile obiecał, co zapłacił i co przekazał. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { AmountField, TextField } from "../../components/Field";
import { ConfirmDialog, Sheet } from "../../components/Overlay";
import { Select } from "../../components/Select";
import { Card, EmptyState, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate, formatMoney } from "../../lib/format";
import { MONEY_SECTIONS, SectionNav } from "./SectionNav";
import { keys, useCanWrite, useWeddingId } from "./data";
import { ifMatch, saveErrorMessage } from "./mutations";

export type FunderSummary = components["schemas"]["FunderSummary"];
type FunderDetail = components["schemas"]["FunderDetail"];

export const FUNDER_SIDES = [
  { id: "bride", label: "Strona Panny Młodej" },
  { id: "groom", label: "Strona Pana Młodego" },
  { id: "both", label: "Wspólnie" },
  { id: "other", label: "Inni" },
];

const PAYMENT_KIND: Record<string, string> = {
  deposit_zadatek: "Zadatek",
  advance_zaliczka: "Zaliczka",
  installment: "Rata",
  final: "Dopłata",
  other: "Inna",
};

/** Lista sponsorów (do wyboru „Kto płaci” przy płatności i roli sponsor). */
export function useFunders(weddingId: string, enabled = true) {
  return useQuery({
    queryKey: keys.funders(weddingId),
    enabled,
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/funders", { params: { path: { wedding_id: weddingId } }, signal })),
  });
}

/** Stan obietnicy po ludzku: ile zostało, czy przypisano więcej niż obiecano. */
export function settleText(f: Pick<FunderSummary, "to_settle" | "pledged_amount">): { text: string; tone: "success" | "warning" | "info" } {
  if (!f.pledged_amount || !f.to_settle) return { text: "Bez ustalonej kwoty", tone: "info" };
  const left = Number(f.to_settle.amount);
  if (left === 0) return { text: "Obietnica w całości rozpisana", tone: "success" };
  if (left > 0) return { text: `Do rozpisania: ${formatMoney(f.to_settle)}`, tone: "info" };
  return { text: `Ponad obietnicę: ${formatMoney({ amount: String(-left), currency: "PLN" })}`, tone: "warning" };
}

/** Pasek „ile z obiecanego już dotarło” (zapłacone + przekazane). */
export function coveredPercent(f: Pick<FunderSummary, "covered" | "pledged_amount">): number | null {
  const pledged = Number(f.pledged_amount?.amount ?? 0);
  if (pledged <= 0) return null;
  return Math.min(100, Math.round((Number(f.covered.amount) / pledged) * 100));
}

export function FundersView() {
  const id = useWeddingId();
  const canWrite = useCanWrite(id);
  const funders = useFunders(id);
  const [editing, setEditing] = useState<FunderSummary | "new" | null>(null);
  const o = funders.data;

  return (
    <main className="page enter-tab" aria-labelledby="funders-h">
      <SectionNav label="Budżet" sections={MONEY_SECTIONS} />
      <div className="view-head">
        <div>
          <h1 id="funders-h">Kto płaci</h1>
          <p className="text-secondary">Rodzice, dziadkowie, chrzestni: ile obiecali, co już zapłacili i co przekazali.</p>
        </div>
        {canWrite && (
          <Button variant="secondary" icon={<Plus aria-hidden size={18} />} onPress={() => setEditing("new")}>
            Dodaj sponsora
          </Button>
        )}
      </div>
      {funders.isPending && <Skeleton lines={4} />}
      {funders.isError && (
        <Notice tone="error" live>
          {userMessage(funders.error)}
        </Notice>
      )}
      {o && (
        <>
          <div className="stat-grid">
            <Card className="stat">
              <span className="text-secondary">Obiecane przez sponsorów</span>
              <span className="stat__value">{formatMoney(o.pledged_total)}</span>
            </Card>
            <Card className="stat">
              <span className="text-secondary">Już dotarło (zapłacone i przekazane)</span>
              <span className="stat__value">{formatMoney(o.covered_total)}</span>
            </Card>
          </div>
          {o.funders.length === 0 ? (
            <EmptyState title="Nikt jeszcze nie jest wpisany">
              Dodajcie np. „Rodzice Panny Młodej” i kwotę, którą obiecali. Przy płatnościach wybierzecie, kto płaci.
            </EmptyState>
          ) : (
            o.funders.map((f) => <FunderCard key={f.id} weddingId={id} funder={f} canWrite={canWrite} onEdit={() => setEditing(f)} />)
          )}
          <Card>
            <p>
              <strong>Para</strong> — zapłacone {formatMoney(o.couple_paid)}, zaplanowane {formatMoney(o.couple_scheduled)}.
            </p>
            <p className="text-secondary">Płatności bez wskazanego sponsora liczą się jako Wasze.</p>
          </Card>
        </>
      )}
      <FunderSheet weddingId={id} funder={editing} onClose={() => setEditing(null)} />
    </main>
  );
}

function FunderCard({ weddingId, funder: f, canWrite, onEdit }: { weddingId: string; funder: FunderSummary; canWrite: boolean; onEdit: () => void }) {
  const [open, setOpen] = useState(false);
  const settle = settleText(f);
  const pct = coveredPercent(f);
  return (
    <Card className="form-stack" aria-labelledby={`funder-${f.id}`}>
      <div className="section-head section-head--wrap">
        <h2 id={`funder-${f.id}`}>{f.name}</h2>
        <StatusChip tone={settle.tone}>{settle.text}</StatusChip>
      </div>
      <dl className="funder-numbers">
        <div>
          <dt>Obiecane</dt>
          <dd className="num">{f.pledged_amount ? formatMoney(f.pledged_amount) : "—"}</dd>
        </div>
        <div>
          <dt>Zapłacili firmom</dt>
          <dd className="num">{formatMoney(f.paid_direct)}</dd>
        </div>
        <div>
          <dt>Przekazali Wam</dt>
          <dd className="num">{formatMoney(f.given)}</dd>
        </div>
        <div>
          <dt>Do zapłaty przez nich</dt>
          <dd className="num">{formatMoney(f.scheduled_direct)}</dd>
        </div>
      </dl>
      {pct !== null && (
        <div className="funder-progress">
          <progress max={100} value={pct} aria-label={`Dotarło ${pct}% obiecanej kwoty`} />
          <span className="text-secondary num">{pct}% obiecanej kwoty już dotarło</span>
        </div>
      )}
      {f.notes && <p className="text-secondary">{f.notes}</p>}
      {Number(f.reported.amount) > 0 && (
        <Notice tone="info">Zgłosili przelew {formatMoney(f.reported)} — potwierdźcie po otrzymaniu (Płatności i wpłaty).</Notice>
      )}
      <div className="wp-sheet__actions">
        <Button variant="text" onPress={() => setOpen((v) => !v)} aria-expanded={open}>
          {open ? "Ukryj szczegóły" : "Płatności i wpłaty"}
        </Button>
        {canWrite && (
          <Button variant="text" onPress={onEdit}>
            Edytuj
          </Button>
        )}
      </div>
      {open && <FunderDetailPanel weddingId={weddingId} funderId={f.id} canWrite={canWrite} />}
    </Card>
  );
}

function FunderDetailPanel({ weddingId, funderId, canWrite }: { weddingId: string; funderId: string; canWrite: boolean }) {
  const detail = useQuery({
    queryKey: [...keys.funders(weddingId), funderId],
    queryFn: ({ signal }) =>
      unwrap(api.GET("/api/v1/weddings/{wedding_id}/funders/{funder_id}", { params: { path: { wedding_id: weddingId, funder_id: funderId } }, signal })),
  });
  if (detail.isPending) return <Skeleton lines={2} />;
  if (detail.isError)
    return (
      <Notice tone="error" live>
        {userMessage(detail.error)}
      </Notice>
    );
  return <FunderDetailList detail={detail.data} weddingId={canWrite ? weddingId : null} />;
}

/** Płatności i wpłaty sponsora (para: z dodawaniem wpłat; sponsor: tylko podgląd). */
export function FunderDetailList({ detail, weddingId }: { detail: FunderDetail; weddingId: string | null }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [amount, setAmount] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const key = useRef(newIdempotencyKey());
  const funderId = detail.funder.id;
  const refresh = () => (weddingId ? queryClient.invalidateQueries({ queryKey: keys.funders(weddingId) }) : Promise.resolve());
  const add = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/funders/{funder_id}/contributions", {
          params: { path: { wedding_id: weddingId!, funder_id: funderId } },
          body: { amount: { amount: amount!, currency: "PLN" }, note: note.trim() || null },
          headers: { "Idempotency-Key": key.current },
        }),
      ),
    onSuccess: async () => {
      key.current = newIdempotencyKey();
      setAmount(null);
      setNote("");
      setError(null);
      await refresh();
      toast("Zapisano wpłatę");
    },
    onError: (e) => setError(`Nie zapisano. ${userMessage(e)}`),
  });
  const confirm = useMutation({
    mutationFn: (contributionId: string) =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/funders/{funder_id}/contributions/{contribution_id}/confirm", {
          params: { path: { wedding_id: weddingId!, funder_id: funderId, contribution_id: contributionId } },
        }),
      ),
    onSuccess: async () => {
      await refresh();
      toast("Potwierdzono wpłatę");
    },
  });
  const remove = useMutation({
    mutationFn: (contributionId: string) =>
      unwrap(
        api.DELETE("/api/v1/weddings/{wedding_id}/funders/{funder_id}/contributions/{contribution_id}", {
          params: { path: { wedding_id: weddingId!, funder_id: funderId, contribution_id: contributionId } },
        }),
      ),
    onSuccess: async () => {
      setRemoving(null);
      await refresh();
      toast("Usunięto wpłatę");
    },
  });

  return (
    <div className="form-stack">
      <h3>Płatności przypisane</h3>
      {detail.payments.length === 0 ? (
        <p className="text-secondary">Brak. Przy płatności w budżecie wybierzcie „Kto płaci”.</p>
      ) : (
        <ul className="row-list">
          {detail.payments.map((p) => (
            <li key={p.id} className="row">
              <span className="row__body">
                <span className="row__title">
                  {p.item_name} · {PAYMENT_KIND[p.kind] ?? p.kind}
                </span>
                <span className="text-secondary">
                  {p.status === "paid" ? `Zapłacone ${p.paid_on ? formatDate(p.paid_on) : ""}` : p.due_date ? `Termin ${formatDate(p.due_date)}` : "Bez terminu"}
                </span>
              </span>
              <span className="num">{formatMoney(p.amount)}</span>
            </li>
          ))}
        </ul>
      )}
      <h3>Przekazane parze</h3>
      {detail.contributions.length === 0 ? (
        <p className="text-secondary">Brak wpłat.</p>
      ) : (
        <ul className="row-list">
          {detail.contributions.map((c) => (
            <li key={c.id} className="row">
              <span className="row__body">
                <span className="row__title num">{formatMoney(c.amount)}</span>
                <span className="text-secondary">{[c.received_on && formatDate(c.received_on), c.note].filter(Boolean).join(" · ") || "—"}</span>
              </span>
              {c.status === "reported" && <StatusChip tone="info">Czeka na potwierdzenie</StatusChip>}
              {weddingId && c.status === "reported" && (
                <Button variant="secondary" pending={confirm.isPending && confirm.variables === c.id} onPress={() => confirm.mutate(c.id)}>
                  Potwierdź
                </Button>
              )}
              {weddingId && (
                <AriaButton className="wp-icon-button" aria-label={`Usuń wpłatę ${formatMoney(c.amount)}`} onPress={() => setRemoving(c.id)}>
                  <Trash2 aria-hidden size={20} />
                </AriaButton>
              )}
            </li>
          ))}
        </ul>
      )}
      {weddingId && (
        <Form
          className="form-stack"
          aria-label="Nowa wpłata"
          onSubmit={(e) => {
            e.preventDefault();
            if (!amount || Number(amount) <= 0) {
              setError("Wpisz kwotę większą od zera.");
              return;
            }
            add.mutate();
          }}
        >
          <AmountField label="Nowa wpłata od sponsora" value={amount} onChange={setAmount} />
          <TextField label="Notatka (opcjonalnie)" description="Np. przelew na konto, gotówka." value={note} onChange={setNote} />
          {error && (
            <Notice tone="error" live>
              {error}
            </Notice>
          )}
          <div className="wp-sheet__actions">
            <Button type="submit" variant="secondary" pending={add.isPending}>
              Zapisz wpłatę
            </Button>
          </div>
        </Form>
      )}
      <ConfirmDialog title="Usunąć wpłatę?" isOpen={removing !== null} onOpenChange={(open) => !open && setRemoving(null)}>
        <p>Wpłata zniknie z podsumowania sponsora.</p>
        <div className="wp-sheet__actions">
          <Button variant="secondary" onPress={() => setRemoving(null)}>
            Zostaw
          </Button>
          <Button variant="danger" pending={remove.isPending} onPress={() => removing && remove.mutate(removing)}>
            Usuń wpłatę
          </Button>
        </div>
      </ConfirmDialog>
    </div>
  );
}

function FunderSheet({ weddingId, funder, onClose }: { weddingId: string; funder: FunderSummary | "new" | null; onClose: () => void }) {
  const title = funder === "new" ? "Nowy sponsor" : funder ? `Edycja: ${funder.name}` : "Sponsor";
  return (
    <Sheet title={title} isOpen={funder !== null} onOpenChange={(open) => !open && onClose()}>
      {funder && <FunderForm key={funder === "new" ? "new" : funder.id} weddingId={weddingId} funder={funder === "new" ? null : funder} onClose={onClose} />}
    </Sheet>
  );
}

function FunderForm({ weddingId, funder, onClose }: { weddingId: string; funder: FunderSummary | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState(funder?.name ?? "");
  const [side, setSide] = useState<string>(funder?.side ?? "bride");
  const [pledged, setPledged] = useState<string | null>(funder?.pledged_amount?.amount ?? null);
  const [notes, setNotes] = useState(funder?.notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const key = useRef(newIdempotencyKey());
  const refresh = () => queryClient.invalidateQueries({ queryKey: keys.funders(weddingId) });
  const body = {
    name: name.trim(),
    side: side as FunderSummary["side"],
    pledged_amount: pledged ? { amount: pledged, currency: "PLN" as const } : null,
    notes: notes.trim() || null,
  };
  const save = useMutation({
    mutationFn: () =>
      funder
        ? unwrap(
            api.PATCH("/api/v1/weddings/{wedding_id}/funders/{funder_id}", {
              params: { path: { wedding_id: weddingId, funder_id: funder.id } },
              body,
              headers: ifMatch(funder.version),
            }),
          )
        : unwrap(
            api.POST("/api/v1/weddings/{wedding_id}/funders", {
              params: { path: { wedding_id: weddingId } },
              body,
              headers: { "Idempotency-Key": key.current },
            }),
          ),
    onSuccess: async () => {
      await refresh();
      onClose();
      toast(funder ? "Zapisano" : `Dodano: ${name.trim()}`);
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [keys.funders(weddingId)])),
  });
  const remove = useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/v1/weddings/{wedding_id}/funders/{funder_id}", { params: { path: { wedding_id: weddingId, funder_id: funder!.id } } })),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["wedding", weddingId] });
      onClose();
      toast("Usunięto sponsora");
    },
    onError: (e) => setError(`Nie usunięto. ${userMessage(e)}`),
  });
  return (
    <Form
      className="form-stack"
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim()) save.mutate();
      }}
    >
      <TextField label="Kto" description="Np. „Rodzice Panny Młodej”, „Babcia Zosia”." value={name} onChange={setName} isRequired autoComplete="off" />
      <Select label="Strona" options={FUNDER_SIDES} value={side} onChange={setSide} />
      <AmountField label="Obiecana kwota (opcjonalnie)" value={pledged} onChange={setPledged} />
      <TextField label="Notatka (opcjonalnie)" description="Np. „płacą za salę i zespół”." value={notes} onChange={setNotes} />
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      <div className="wp-sheet__actions">
        <Button type="submit" pending={save.isPending} isDisabled={!name.trim()}>
          {funder ? "Zapisz" : "Dodaj sponsora"}
        </Button>
        {funder && (
          <Button variant="text" onPress={() => setConfirm(true)}>
            Usuń sponsora
          </Button>
        )}
      </div>
      <ConfirmDialog title="Usunąć sponsora?" isOpen={confirm} onOpenChange={setConfirm}>
        <p>Płatności przypisane do „{funder?.name}” wrócą do pary, a jego wpłaty znikną. Osoba z rolą sponsora straci wgląd.</p>
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
