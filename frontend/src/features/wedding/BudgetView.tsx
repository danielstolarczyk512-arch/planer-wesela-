import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { downloadAuthorized } from "../../api/download";
import { userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { AmountField, TextField } from "../../components/Field";
import { ConfirmDialog, Sheet } from "../../components/Overlay";
import { Segmented } from "../../components/Segmented";
import { Select } from "../../components/Select";
import { Card, EmptyState, Notice, Skeleton, StatusChip, type Tone } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate, formatMoney } from "../../lib/format";
import { BudgetCategories } from "./BudgetCategories";
import { DrinksCalculator } from "./DrinksCalculator";
import { MONEY_SECTIONS, PrintLink, SectionNav } from "./SectionNav";
import { EditItemSheet } from "./EditItemSheet";
import { CashflowCard, GuestCostCard } from "./BudgetInsights";
import { IndexationCard } from "./IndexationCard";
import {
  keys,
  useBudgetCategories,
  useBudgetItems,
  useBudgetOverview,
  useCanWrite,
  useWeddingId,
  type BudgetItem,
  type Payment,
} from "./data";

const KIND: Record<string, string> = {
  deposit_zadatek: "Zadatek",
  advance_zaliczka: "Zaliczka",
  installment: "Rata",
  final: "Dopłata",
  other: "Płatność",
};

const ITEM_STATUS: Record<string, { label: string; tone: Tone }> = {
  planned: { label: "Szacunek", tone: "neutral" },
  confirmed: { label: "Umowa", tone: "info" },
  paid: { label: "Zapłacone", tone: "success" },
  cancelled: { label: "Anulowane", tone: "neutral" },
};

/** Procent wykorzystania limitu z napisów kwot (bez arytmetyki zmiennoprzecinkowej na kwotach w UI). */
export function usagePercent(estimated: string, limit: string): number {
  const e = Number(estimated);
  const l = Number(limit);
  return l > 0 ? Math.round((e / l) * 100) : 0;
}

export function BudgetView() {
  const id = useWeddingId();
  const overview = useBudgetOverview(id);
  const items = useBudgetItems(id);
  const categories = useBudgetCategories(id);
  const canWrite = useCanWrite(id);
  const [exporting, setExporting] = useState(false);
  const [adding, setAdding] = useState(false);
  const [paying, setPaying] = useState<Payment | null>(null);
  const [editing, setEditing] = useState<BudgetItem | null>(null);

  const categoryName = useMemo(
    () => new Map((categories.data ?? []).map((c) => [c.id, c.name])),
    [categories.data],
  );

  if (overview.isPending) {
    return (
      <main className="page">
        <Skeleton lines={6} />
      </main>
    );
  }
  if (overview.isError) {
    return (
      <main className="page">
        <Notice tone="error" title="Nie udało się wczytać budżetu." live>
          {userMessage(overview.error)}
        </Notice>
      </main>
    );
  }
  const o = overview.data;
  const limit = o.total_budget;
  const percent = limit ? usagePercent(o.estimated_total.amount, limit.amount) : null;
  const payments = [...o.overdue_payments, ...o.upcoming_payments_30d];

  return (
    <main className="page enter-tab" aria-labelledby="budget-h">
      <SectionNav label="Budżet" sections={MONEY_SECTIONS} />
      <div className="view-head">
        <div>
          <h1 id="budget-h">Budżet</h1>
          <p className="text-secondary">Każda kwota na swoim miejscu.</p>
          <div className="seating-actions">
            <PrintLink kind="budzet">Drukuj budżet</PrintLink>
            {canWrite && (
              <Button variant="text" onPress={() => setExporting(true)}>
                Pobierz do Excela (CSV)
              </Button>
            )}
          </div>
        </div>
      </div>
      <BudgetCsvDialog weddingId={id} isOpen={exporting} onClose={() => setExporting(false)} />

      <Card className="form-stack" aria-label="Podsumowanie budżetu">
        <span className="text-secondary">Przewidywany koszt</span>
        <span className="amount-lg">{formatMoney(o.estimated_total)}</span>
        {limit && percent !== null ? (
          <div className="meter">
            <div
              className="meter__track"
              role="meter"
              aria-label="Wykorzystanie limitu budżetu"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.min(percent, 100)}
              aria-valuetext={`${percent}% limitu`}
            >
              <div className={`meter__fill${o.over_budget ? " meter__fill--over" : ""}`} style={{ width: `${Math.min(percent, 100)}%` }} />
            </div>
            <div className="section-head text-secondary num">
              <span>Limit: {formatMoney(limit)}</span>
              <span>Wykorzystano {percent}%</span>
            </div>
            {o.over_budget && (
              <Notice tone="error" title="Przekroczony budżet">
                Przewidywany koszt jest wyższy niż limit.
              </Notice>
            )}
          </div>
        ) : (
          <p className="text-secondary">Bez ustalonego limitu budżetu.</p>
        )}
      </Card>

      <div className="stat-grid">
        <Card className="stat">
          <span className="text-secondary">Wpłacono</span>
          <span className="stat__value">{formatMoney(o.paid_total)}</span>
        </Card>
        <Card className="stat">
          <span className="text-secondary">Do zapłaty</span>
          <span className="stat__value">{formatMoney(o.remaining_to_pay)}</span>
        </Card>
      </div>

      <IndexationCard weddingId={id} />
      <CashflowCard weddingId={id} />
      <GuestCostCard weddingId={id} />

      <section id="platnosci" aria-labelledby="pay-h" className="form-stack">
        <div className="section-head">
          <h2 id="pay-h">Płatności w najbliższych 30 dniach</h2>
        </div>
        <Card>
          {payments.length === 0 ? (
            <p className="text-secondary">Brak płatności do zrobienia w najbliższym miesiącu.</p>
          ) : (
            <ul className="row-list">
              {payments.map((p) => (
                <li key={p.id} className="row">
                  <div className="row__body">
                    <span className="row__title">{p.item_name}</span>
                    <span className="text-secondary num">
                      {KIND[p.kind] ?? "Płatność"}
                      {p.due_date && ` · do ${formatDate(p.due_date)}`}
                    </span>
                  </div>
                  <div className="row__end">
                    <strong className="num">{formatMoney(p.amount)}</strong>
                    {p.is_overdue && <StatusChip tone="error">Po terminie</StatusChip>}
                  </div>
                  {canWrite && (
                    <Button variant="text" onPress={() => setPaying(p)} aria-label={`Oznacz zapłatę: ${p.item_name}, ${formatMoney(p.amount)}`}>
                      Oznacz zapłatę
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>

      <BudgetCategories weddingId={id} categories={o.categories} hasLimit={!!limit} canWrite={canWrite} />
      <DrinksCalculator weddingId={id} canWrite={canWrite} />

      <section aria-labelledby="items-h" className="form-stack">
        <div className="section-head">
          <h2 id="items-h">Wydatki</h2>
          {canWrite && (
            <Button variant="secondary" icon={<Plus aria-hidden size={20} />} onPress={() => setAdding(true)}>
              Dodaj wydatek
            </Button>
          )}
        </div>
        {items.isPending ? (
          <Skeleton lines={4} />
        ) : (items.data ?? []).length === 0 ? (
          <Card>
            <EmptyState title="Nie ma jeszcze wydatków">Dodajcie pierwszy koszt, np. salę albo fotografa.</EmptyState>
          </Card>
        ) : (
          <Card>
            <ul className="row-list">
              {(items.data ?? []).map((i: BudgetItem) => {
                const st = ITEM_STATUS[i.status] ?? { label: i.status, tone: "neutral" as Tone };
                const body = (
                  <>
                    <span className="row__title">{i.name}</span>
                    <span className="text-secondary">
                      {categoryName.get(i.category_id) ?? "Bez kategorii"}
                      {Number(i.paid.amount) > 0 && ` · wpłacono ${formatMoney(i.paid)}`}
                    </span>
                  </>
                );
                return (
                  <li key={i.id} className="row">
                    {canWrite ? (
                      // Dotknięcie wydatku otwiera edycję (nazwa przycisku = widoczna nazwa).
                      <AriaButton className="row-edit" onPress={() => setEditing(i)}>
                        {body}
                      </AriaButton>
                    ) : (
                      <div className="row__body">{body}</div>
                    )}
                    <div className="row__end">
                      <strong className="num">{formatMoney(i.estimated)}</strong>
                      <StatusChip tone={st.tone}>{st.label}</StatusChip>
                    </div>
                  </li>
                );
              })}
            </ul>
          </Card>
        )}
      </section>

      <NewItemSheet weddingId={id} isOpen={adding} onOpenChange={setAdding} />
      <MarkPaidDialog weddingId={id} payment={paying} onClose={() => setPaying(null)} />
      <EditItemSheet weddingId={id} item={editing} onClose={() => setEditing(null)} />
    </main>
  );
}

function MarkPaidDialog({ weddingId, payment, onClose }: { weddingId: string; payment: Payment | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const mark = useMutation({
    mutationFn: (p: Payment) =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/payments/{payment_id}/mark-paid", {
          params: { path: { wedding_id: weddingId, payment_id: p.id } },
          body: {},
        }),
      ),
    onSuccess: async (p) => {
      onClose();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.budget(weddingId) }),
        queryClient.invalidateQueries({ queryKey: keys.items(weddingId) }),
        queryClient.invalidateQueries({ queryKey: keys.payments(weddingId) }),
        queryClient.invalidateQueries({ queryKey: keys.summary(weddingId) }),
      ]);
      toast(`Zapisano wpłatę: ${p.item_name}, ${formatMoney(p.amount)}`);
    },
  });
  return (
    <ConfirmDialog title="Oznaczyć jako zapłacone?" isOpen={!!payment} onOpenChange={(o) => !o && onClose()}>
      {payment && (
        <>
          <p>
            {KIND[payment.kind] ?? "Płatność"} <strong>{formatMoney(payment.amount)}</strong> za „{payment.item_name}”.
          </p>
          <p className="text-secondary">Zapisujemy tylko informację, że zapłaciliście. Aplikacja nie wykonuje przelewów.</p>
          {mark.isError && (
            <Notice tone="error" live>
              {userMessage(mark.error)}
            </Notice>
          )}
          <div className="wp-sheet__actions">
            <Button variant="secondary" onPress={onClose}>
              Anuluj
            </Button>
            <Button pending={mark.isPending} onPress={() => mark.mutate(payment)}>
              Tak, zapłacone
            </Button>
          </div>
        </>
      )}
    </ConfirmDialog>
  );
}

function NewItemSheet({ weddingId, isOpen, onOpenChange }: { weddingId: string; isOpen: boolean; onOpenChange: (o: boolean) => void }) {
  const categories = useBudgetCategories(weddingId);
  const [name, setName] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [amount, setAmount] = useState<string | null>(null);
  const [errors, setErrors] = useState<{ name?: string; category?: string; amount?: string }>({});
  const key = useRef(newIdempotencyKey());
  const queryClient = useQueryClient();
  const toast = useToast();
  const create = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/budget/items", {
          params: { path: { wedding_id: weddingId } },
          body: {
            category_id: category!,
            name: name.trim(),
            cost_mode: "fixed",
            planned: { amount: amount!, currency: "PLN" },
            status: "planned",
            indexation: "none",
          },
          headers: { "Idempotency-Key": key.current },
        }),
      ),
    onSuccess: async (i) => {
      key.current = newIdempotencyKey();
      setName("");
      setAmount(null);
      setCategory(null);
      onOpenChange(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.items(weddingId) }),
        queryClient.invalidateQueries({ queryKey: keys.budget(weddingId) }),
        queryClient.invalidateQueries({ queryKey: keys.summary(weddingId) }),
      ]);
      toast(`Dodano wydatek „${i.name}”`);
    },
  });
  const dirty = name.trim() !== "" || amount !== null || category !== null;
  return (
    <Sheet title="Nowy wydatek" isOpen={isOpen} onOpenChange={onOpenChange} isDirty={dirty && !create.isPending}>
      <Form
        className="form-stack"
        validationBehavior="aria"
        onSubmit={(e) => {
          e.preventDefault();
          const next: typeof errors = {};
          if (!name.trim()) next.name = "Wpisz nazwę, np. Fotograf.";
          if (!category) next.category = "Wybierz kategorię.";
          // Wydatek bez kwoty liczyłby się w sumach jak 0 zł: wymagamy szacunku.
          if (!amount) next.amount = "Wpisz szacunkową kwotę, np. 5000.";
          setErrors(next);
          if (next.name || next.category || next.amount) return;
          create.mutate();
        }}
      >
        {create.isError && (
          <Notice tone="error" title="Nie zapisano." live>
            {userMessage(create.error)}
          </Notice>
        )}
        <TextField label="Nazwa" value={name} onChange={setName} error={errors.name} isRequired autoFocus />
        <Select
          label="Kategoria"
          options={(categories.data ?? []).map((c) => ({ id: c.id, label: c.name }))}
          value={category}
          onChange={setCategory}
          error={errors.category}
          isRequired
        />
        <AmountField
          label="Kwota (szacunek)"
          description="Szacunek wystarczy — zmienicie go po otrzymaniu oferty."
          value={amount}
          onChange={setAmount}
          error={errors.amount}
          isRequired
        />
        <Button type="submit" block pending={create.isPending}>
          Dodaj wydatek
        </Button>
      </Form>
    </Sheet>
  );
}

type BudgetPart = "items" | "payments";

/** Budżet do Excela: pozycje kosztowe albo harmonogram płatności (osobne pliki — prostsze filtry). */
function BudgetCsvDialog({ weddingId, isOpen, onClose }: { weddingId: string; isOpen: boolean; onClose: () => void }) {
  const [part, setPart] = useState<BudgetPart>("items");
  const toast = useToast();
  const download = useMutation({
    mutationFn: () =>
      downloadAuthorized(`/api/v1/weddings/${weddingId}/budget/export.csv?part=${part}`, part === "payments" ? "budzet-platnosci.csv" : "budzet.csv"),
    onSuccess: () => {
      onClose();
      toast(part === "payments" ? "Pobrano harmonogram płatności (CSV)" : "Pobrano budżet (CSV)");
    },
  });
  return (
    <ConfirmDialog title="Budżet do Excela" isOpen={isOpen} onOpenChange={(o) => !o && onClose()}>
      <p>Plik CSV otworzycie w Excelu lub Arkuszach Google. Kwoty mają przecinek dziesiętny, więc arkusz policzy sumy.</p>
      <Segmented<BudgetPart>
        label="Co pobrać"
        value={part}
        onChange={setPart}
        options={[
          { value: "items", label: "Pozycje kosztowe" },
          { value: "payments", label: "Płatności" },
        ]}
      />
      <p className="text-secondary">
        {part === "items"
          ? "Kategoria, pozycja, plan, umowa, szacunek, zapłacono i do zapłaty."
          : "Każdy zadatek, zaliczka i rata: kwota, termin, status i data zapłaty."}
      </p>
      {download.isError && (
        <Notice tone="error" live>
          {userMessage(download.error)}
        </Notice>
      )}
      <div className="wp-sheet__actions">
        <Button variant="secondary" onPress={onClose}>
          Anuluj
        </Button>
        <Button pending={download.isPending} onPress={() => download.mutate()}>
          Pobierz plik
        </Button>
      </div>
    </ConfirmDialog>
  );
}
