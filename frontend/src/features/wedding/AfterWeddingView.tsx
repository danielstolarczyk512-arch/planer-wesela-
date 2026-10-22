/** Po weselu: dopłaty, co mają oddać usługodawcy, zmiana nazwiska, podziękowania i archiwum. */
import { parseDate, type CalendarDate } from "@internationalized/date";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Download, ExternalLink, Plus } from "lucide-react";
import { useRef, useState } from "react";
import { Form } from "react-aria-components";
import { Link } from "react-router";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { downloadAuthorized } from "../../api/download";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { DateField } from "../../components/DateField";
import { Checkbox, TextField } from "../../components/Field";
import { ConfirmDialog, Sheet } from "../../components/Overlay";
import { Select } from "../../components/Select";
import { Card, EmptyState, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate, formatMoney, todayInWarsaw } from "../../lib/format";
import { useCanWrite, useWedding, useWeddingId } from "./data";
import { ifMatch, saveErrorMessage } from "./mutations";
import { useVendors } from "./vendors";

type After = components["schemas"]["AfterWedding"];
type Deliverable = After["deliverables"][number];

/** Uprzejme przypomnienie do skopiowania (usługodawca po terminie z umowy). */
export function reminderText(d: Pick<Deliverable, "title" | "due_on" | "vendor_name">, couple: string): string {
  const greeting = d.vendor_name ? `Dzień dobry, ${d.vendor_name}!` : "Dzień dobry!";
  const due = d.due_on ? ` Zgodnie z umową termin minął ${formatDate(d.due_on)}.` : "";
  return `${greeting} Piszemy w sprawie: ${d.title}.${due} Czy możemy prosić o informację, kiedy możemy się spodziewać? Dziękujemy i pozdrawiamy, ${couple}`;
}

export function AfterWeddingView() {
  const id = useWeddingId();
  const canWrite = useCanWrite(id);
  const wedding = useWedding(id);
  const queryKey = ["wedding", id, "after-wedding"];
  const data = useQuery({
    queryKey,
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/after-wedding", { params: { path: { wedding_id: id } }, signal })),
  });
  const [editing, setEditing] = useState<Deliverable | "new" | null>(null);
  const o = data.data;
  return (
    <main className="page enter-tab" aria-labelledby="after-h">
      <div>
        <h1 id="after-h">Po weselu</h1>
        <p className="text-secondary">Dopłaty, zdjęcia i film od usługodawców, zmiana nazwiska i podziękowania — wszystko, co zostaje po weselu.</p>
      </div>
      {data.isPending && <Skeleton lines={5} />}
      {data.isError && (
        <Notice tone="error" live>
          {userMessage(data.error)}
        </Notice>
      )}
      {o && (
        <>
          {!o.after_wedding && o.wedding_day && (
            <Notice tone="info">Ta strona przyda się po {formatDate(o.wedding_day)}. Już teraz możecie wpisać terminy oddania zdjęć i filmu z umów.</Notice>
          )}

          <section className="form-stack" aria-labelledby="settle-h">
            <h2 id="settle-h">Rozliczenie</h2>
            {o.open_payments.length === 0 ? (
              <Card>
                <p>Wszystkie zaplanowane płatności są rozliczone.</p>
              </Card>
            ) : (
              <Card>
                <ul className="row-list">
                  {o.open_payments.map((p) => (
                    <li key={p.id} className="row">
                      <span className="row__body">
                        <span className="row__title">{p.item_name}</span>
                        <span className="text-secondary">{p.due_date ? `termin ${formatDate(p.due_date)}` : "bez terminu"}</span>
                      </span>
                      <span className="num">{formatMoney(p.amount)}</span>
                      {p.overdue && <StatusChip tone="warning">Po terminie</StatusChip>}
                    </li>
                  ))}
                </ul>
                <Link to={`/w/${id}/budzet#platnosci`}>Przejdź do płatności</Link>
              </Card>
            )}
          </section>

          <section className="form-stack" aria-labelledby="deliv-h">
            <div className="section-head section-head--wrap">
              <h2 id="deliv-h">Od usługodawców</h2>
              {canWrite && (
                <Button variant="secondary" icon={<Plus aria-hidden size={18} />} onPress={() => setEditing("new")}>
                  Dodaj
                </Button>
              )}
            </div>
            {canWrite && <SuggestedDeliverables weddingId={id} existing={o.deliverables} queryKey={queryKey} />}
            {o.deliverables.length === 0 ? (
              <EmptyState title="Nic jeszcze nie czeka">Wpiszcie np. „Zdjęcia — galeria” z terminem z umowy fotografa. Przypomnimy, gdy minie.</EmptyState>
            ) : (
              o.deliverables.map((d) => (
                <DeliverableCard key={d.id} d={d} weddingId={id} couple={wedding.data?.name ?? ""} canWrite={canWrite} onEdit={() => setEditing(d)} />
              ))
            )}
          </section>

          <NameChangeSection items={o.name_change} weddingId={id} canWrite={canWrite} queryKey={queryKey} />

          <section className="form-stack" aria-labelledby="thanks-h">
            <h2 id="thanks-h">Podziękowania</h2>
            <Card>
              <p>
                {o.thanks.with_gift > 0
                  ? `Podziękowania za prezenty: ${o.thanks.thanked_with_gift} z ${o.thanks.with_gift}.`
                  : "Wpiszcie przy zaproszeniach, co podarowali goście — zobaczycie, komu jeszcze podziękować."}
              </p>
              <Link to={`/w/${id}/goscie`}>Lista gości</Link>
            </Card>
          </section>

          <ArchiveSection weddingId={id} />
        </>
      )}
      <DeliverableSheet weddingId={id} item={editing} queryKey={queryKey} onClose={() => setEditing(null)} />
    </main>
  );
}

function DeliverableCard({ d, weddingId, couple, canWrite, onEdit }: { d: Deliverable; weddingId: string; couple: string; canWrite: boolean; onEdit: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const received = useMutation({
    mutationFn: () =>
      unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/deliverables/{deliverable_id}", {
          params: { path: { wedding_id: weddingId, deliverable_id: d.id } },
          body: { received_on: todayInWarsaw() },
          headers: ifMatch(d.version),
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(["wedding", weddingId, "after-wedding"], data);
      toast("Zaznaczono jako odebrane");
    },
  });
  const tone = d.status === "received" ? "success" : d.status === "overdue" ? "warning" : "neutral";
  const label = d.status === "received" ? `Odebrane ${d.received_on ? formatDate(d.received_on) : ""}` : d.status === "overdue" ? `Spóźnienie: ${d.days_late} dni` : d.due_on ? `Do ${formatDate(d.due_on)}` : "Bez terminu";
  return (
    <Card className="form-stack">
      <div className="section-head section-head--wrap">
        <h3 className="logistics__title">{d.title}</h3>
        <StatusChip tone={tone}>{label}</StatusChip>
      </div>
      {(d.vendor_name || d.note) && <p className="text-secondary">{[d.vendor_name, d.note].filter(Boolean).join(" · ")}</p>}
      {received.isError && (
        <Notice tone="error" live>
          {userMessage(received.error)}
        </Notice>
      )}
      {canWrite && d.status !== "received" && (
        <div className="wp-sheet__actions">
          <Button variant="secondary" pending={received.isPending} onPress={() => received.mutate()}>
            Odebrane
          </Button>
          {d.status === "overdue" && (
            <Button
              variant="text"
              icon={<Copy aria-hidden size={18} />}
              onPress={async () => {
                try {
                  await navigator.clipboard.writeText(reminderText(d, couple));
                  toast("Skopiowano przypomnienie — wklejcie je do wiadomości");
                } catch {
                  toast("Nie udało się skopiować");
                }
              }}
            >
              Kopiuj przypomnienie
            </Button>
          )}
          <Button variant="text" onPress={onEdit}>
            Edytuj
          </Button>
        </div>
      )}
    </Card>
  );
}

function DeliverableSheet({ weddingId, item, queryKey, onClose }: { weddingId: string; item: Deliverable | "new" | null; queryKey: string[]; onClose: () => void }) {
  return (
    <Sheet title={item === "new" ? "Co oddaje usługodawca" : "Edycja"} isOpen={item !== null} onOpenChange={(open) => !open && onClose()}>
      {item && <DeliverableForm key={item === "new" ? "new" : `${item.id}-${item.version}`} weddingId={weddingId} item={item === "new" ? null : item} queryKey={queryKey} onClose={onClose} />}
    </Sheet>
  );
}

function DeliverableForm({ weddingId, item, queryKey, onClose }: { weddingId: string; item: Deliverable | null; queryKey: string[]; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const vendors = useVendors(weddingId);
  const [title, setTitle] = useState(item?.title ?? "");
  const [vendor, setVendor] = useState<string>(item?.vendor_id ?? "");
  const [due, setDue] = useState<CalendarDate | null>(item?.due_on ? parseDate(item.due_on) : null);
  const [note, setNote] = useState(item?.note ?? "");
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const key = useRef(newIdempotencyKey());
  const body = { title: title.trim(), vendor_id: vendor || null, due_on: due?.toString() ?? null, note: note.trim() || null };
  const done = (data: After | void, message: string) => {
    if (data) queryClient.setQueryData(queryKey, data);
    else void queryClient.invalidateQueries({ queryKey });
    onClose();
    toast(message);
  };
  const save = useMutation({
    mutationFn: () =>
      item
        ? unwrap(api.PATCH("/api/v1/weddings/{wedding_id}/deliverables/{deliverable_id}", { params: { path: { wedding_id: weddingId, deliverable_id: item.id } }, body, headers: ifMatch(item.version) }))
        : unwrap(api.POST("/api/v1/weddings/{wedding_id}/deliverables", { params: { path: { wedding_id: weddingId } }, body, headers: { "Idempotency-Key": key.current } })),
    onSuccess: (data) => done(data, "Zapisano"),
    onError: (e) => setError(saveErrorMessage(e, queryClient, [queryKey])),
  });
  const remove = useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/v1/weddings/{wedding_id}/deliverables/{deliverable_id}", { params: { path: { wedding_id: weddingId, deliverable_id: item!.id } } })),
    onSuccess: () => done(undefined, "Usunięto"),
  });
  return (
    <Form
      className="form-stack"
      onSubmit={(e) => {
        e.preventDefault();
        if (title.trim()) save.mutate();
      }}
    >
      <TextField label="Co" description="Np. „Zdjęcia — galeria online”, „Film”." value={title} onChange={setTitle} isRequired autoComplete="off" />
      <Select label="Usługodawca (opcjonalnie)" options={[{ id: "", label: "Bez usługodawcy" }, ...(vendors.data ?? []).map((v) => ({ id: v.id, label: v.name }))]} value={vendor} onChange={setVendor} />
      <DateField label="Termin z umowy" value={due} onChange={setDue} />
      <TextField label="Notatka (opcjonalnie)" value={note} onChange={setNote} autoComplete="off" />
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      <div className="wp-sheet__actions">
        <Button type="submit" pending={save.isPending} isDisabled={!title.trim()}>
          Zapisz
        </Button>
        {item && (
          <Button variant="text" onPress={() => setConfirm(true)}>
            Usuń
          </Button>
        )}
      </div>
      <ConfirmDialog title="Usunąć pozycję?" isOpen={confirm} onOpenChange={setConfirm}>
        <p>„{item?.title}” zniknie z listy.</p>
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

function NameChangeSection({ items, weddingId, canWrite, queryKey }: { items: After["name_change"]; weddingId: string; canWrite: boolean; queryKey: string[] }) {
  const queryClient = useQueryClient();
  const set = useMutation({
    mutationFn: ({ code, done }: { code: string; done: boolean }) =>
      unwrap(api.PUT("/api/v1/weddings/{wedding_id}/after-checks/{code}", { params: { path: { wedding_id: weddingId, code } }, body: { done } })),
    onSuccess: (data) => queryClient.setQueryData(queryKey, data),
  });
  const done = items.filter((i) => i.done_on).length;
  return (
    <section className="form-stack" aria-labelledby="name-h">
      <h2 id="name-h">Zmiana nazwiska</h2>
      <p className="text-secondary">
        Jeśli któreś z Was zmienia nazwisko: zrobione {done} z {items.length}. Terminy podajemy tylko tam, gdzie wskazuje je gov.pl.
      </p>
      {set.isError && (
        <Notice tone="error" live>
          {userMessage(set.error)}
        </Notice>
      )}
      <Card>
        <ul className="row-list">
          {items.map((i) => (
            <li key={i.code} className="row name-change-row">
              <span className="row__body">
                {canWrite ? (
                  <Checkbox isSelected={!!i.done_on} onChange={(v) => set.mutate({ code: i.code, done: v })}>
                    <span className="row__title">{i.title}</span>
                  </Checkbox>
                ) : (
                  <span className="row__title">{i.title}</span>
                )}
                <span className="text-secondary">
                  {i.hint}
                  {i.approx_deadline && !i.done_on ? ` Orientacyjnie do ${formatDate(i.approx_deadline)}.` : ""}
                </span>
                {i.source && (
                  <a href={i.source} target="_blank" rel="noreferrer noopener" className="cdocs__source">
                    Źródło: gov.pl <ExternalLink aria-hidden size={16} />
                  </a>
                )}
              </span>
              {i.done_on && <StatusChip tone="success">Zrobione</StatusChip>}
            </li>
          ))}
        </ul>
      </Card>
    </section>
  );
}

function ArchiveSection({ weddingId }: { weddingId: string }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <section className="form-stack" aria-labelledby="archive-h">
      <h2 id="archive-h">Archiwum wesela</h2>
      <Card className="form-stack">
        <p className="text-secondary">Wszystkie dane wesela w jednym pliku (JSON) — na pamiątkę albo przed usunięciem konta. Dane gości zostaną zanonimizowane 90 dni po weselu.</p>
        <Button
          variant="secondary"
          icon={<Download aria-hidden size={18} />}
          pending={busy}
          onPress={async () => {
            setBusy(true);
            setError(null);
            try {
              await downloadAuthorized(`/api/v1/weddings/${weddingId}/export`, "wesele-archiwum.json");
            } catch (e) {
              setError(userMessage(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          Pobierz archiwum
        </Button>
        {error && (
          <Notice tone="error" live>
            {error}
          </Notice>
        )}
      </Card>
    </section>
  );
}

/** Co zwykle oddają usługodawcy po weselu (wg rodzaju firmy). */
export const AFTER_ITEMS: Record<string, string> = {
  photographer: "Zdjęcia",
  videographer: "Film",
  photobooth: "Zdjęcia z fotobudki",
};

/** Podpowiedzi z zarezerwowanych usługodawców (fotograf, filmowiec), których jeszcze nie ma na liście. */
function SuggestedDeliverables({ weddingId, existing, queryKey }: { weddingId: string; existing: Deliverable[]; queryKey: string[] }) {
  const vendors = useVendors(weddingId);
  const queryClient = useQueryClient();
  const toast = useToast();
  const add = useMutation({
    mutationFn: (v: { id: string; name: string; category: string }) =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/deliverables", {
          params: { path: { wedding_id: weddingId } },
          body: { title: `${AFTER_ITEMS[v.category]} — ${v.name}`, vendor_id: v.id, due_on: null, note: null },
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKey, data);
      toast("Dodano — wpiszcie termin z umowy (Edytuj)");
    },
  });
  const have = new Set(existing.map((d) => d.vendor_id).filter(Boolean));
  const suggestions = (vendors.data ?? []).filter((v) => v.category in AFTER_ITEMS && v.status === "booked" && !have.has(v.id));
  if (suggestions.length === 0) return null;
  return (
    <Card className="form-stack">
      <p className="text-secondary">Zarezerwowani usługodawcy, od których zwykle coś się odbiera po weselu:</p>
      <div className="wp-sheet__actions">
        {suggestions.map((v) => (
          <Button key={v.id} variant="secondary" icon={<Plus aria-hidden size={18} />} pending={add.isPending && add.variables?.id === v.id} onPress={() => add.mutate(v)}>
            {AFTER_ITEMS[v.category]} — {v.name}
          </Button>
        ))}
      </div>
    </Card>
  );
}
