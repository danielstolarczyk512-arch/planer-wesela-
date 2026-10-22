import { parseDate, today, type CalendarDate } from "@internationalized/date";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { DateField } from "../../components/DateField";
import { AmountField, Checkbox } from "../../components/Field";
import { Select } from "../../components/Select";
import { Notice, StatusChip, type Tone } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate, formatMoney, TIME_ZONE } from "../../lib/format";
import { keys, type Payment } from "./data";
import { ifMatch, saveErrorMessage } from "./mutations";
import { useFunders } from "./FundersView";

type Kind = components["schemas"]["PaymentCreate"]["kind"];

export const PAYMENT_KINDS: { id: Kind; label: string }[] = [
  { id: "deposit_zadatek", label: "Zadatek" },
  { id: "advance_zaliczka", label: "Zaliczka" },
  { id: "installment", label: "Rata" },
  { id: "final", label: "Dopłata końcowa" },
  { id: "other", label: "Inna" },
];

export function paymentState(p: Pick<Payment, "status" | "is_overdue" | "paid_on">): { label: string; tone: Tone } {
  if (p.status === "paid") return { label: p.paid_on ? `Zapłacono ${formatDate(p.paid_on)}` : "Zapłacono", tone: "success" };
  if (p.status === "cancelled") return { label: "Anulowana", tone: "neutral" };
  if (p.status === "refunded") return { label: "Zwrócona", tone: "neutral" };
  if (p.is_overdue) return { label: "Po terminie", tone: "error" };
  return { label: "Do zapłaty", tone: "warning" };
}

/** Płatności jednego wydatku: zadatek, raty, dopłata — dodawanie, edycja, oznaczanie i usuwanie. */
export function ItemPayments({ weddingId, itemId }: { weddingId: string; itemId: string }) {
  const payments = useQuery({
    queryKey: [...keys.payments(weddingId), itemId],
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/weddings/{wedding_id}/budget/items/{item_id}/payments", {
          params: { path: { wedding_id: weddingId, item_id: itemId } },
          signal,
        }),
      ),
  });
  const [editing, setEditing] = useState<Payment | "new" | null>(null);
  const funders = useFunders(weddingId);
  const funderName = new Map((funders.data?.funders ?? []).map((f) => [f.id, f.name]));

  return (
    <section className="form-stack item-payments" aria-labelledby={`pay-${itemId}`}>
      <div className="section-head">
        <h3 id={`pay-${itemId}`}>Płatności</h3>
        {!editing && (
          <Button variant="text" icon={<Plus aria-hidden size={18} />} onPress={() => setEditing("new")}>
            Dodaj płatność
          </Button>
        )}
      </div>
      {editing ? (
        <PaymentForm
          key={editing === "new" ? "new" : `${editing.id}-${editing.version}`}
          weddingId={weddingId}
          itemId={itemId}
          payment={editing === "new" ? null : editing}
          onDone={() => setEditing(null)}
        />
      ) : (payments.data?.length ?? 0) === 0 ? (
        <p className="text-secondary">Brak zapisanych płatności. Dodajcie zadatek i raty z umowy — przypomnimy o terminach.</p>
      ) : (
        <ul className="row-list">
          {payments.data!.map((p) => {
            const st = paymentState(p);
            return (
              <li key={p.id} className="row">
                <AriaButton className="row-edit" onPress={() => setEditing(p)}>
                  <span className="row__title num">
                    {PAYMENT_KINDS.find((k) => k.id === p.kind)?.label ?? "Płatność"} · {formatMoney(p.amount)}
                  </span>
                  <span className="text-secondary">
                    {p.due_date ? `termin ${formatDate(p.due_date)}` : "bez terminu"}
                    {p.funder_id && funderName.get(p.funder_id) ? ` · płacą: ${funderName.get(p.funder_id)}` : ""}
                  </span>
                </AriaButton>
                <StatusChip tone={st.tone}>{st.label}</StatusChip>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function PaymentForm({
  weddingId,
  itemId,
  payment,
  onDone,
}: {
  weddingId: string;
  itemId: string;
  payment: Payment | null;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [kind, setKind] = useState<string>(payment?.kind ?? "deposit_zadatek");
  const [amount, setAmount] = useState<string | null>(payment ? String(payment.amount.amount) : null);
  const [due, setDue] = useState<CalendarDate | null>(payment?.due_date ? parseDate(payment.due_date) : null);
  const [paidAlready, setPaidAlready] = useState(false);
  const [funder, setFunder] = useState<string>(payment?.funder_id ?? "");
  const funders = useFunders(weddingId);
  const [amountError, setAmountError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [key] = useState(newIdempotencyKey);

  const refresh = () =>
    Promise.all(
      [keys.payments(weddingId), keys.items(weddingId), keys.budget(weddingId), keys.summary(weddingId), keys.funders(weddingId)].map((queryKey) =>
        queryClient.invalidateQueries({ queryKey }),
      ),
    );
  const done = async (message: string) => {
    await refresh();
    onDone();
    toast(message);
  };
  const fail = (e: unknown) => setError(saveErrorMessage(e, queryClient, [keys.payments(weddingId)]));

  const save = useMutation({
    mutationFn: () => {
      const money = { amount: amount!, currency: "PLN" as const };
      if (!payment) {
        return unwrap(
          api.POST("/api/v1/weddings/{wedding_id}/budget/items/{item_id}/payments", {
            params: { path: { wedding_id: weddingId, item_id: itemId } },
            body: {
              kind: kind as Kind,
              amount: money,
              due_date: due ? due.toString() : null,
              paid_on: paidAlready ? today(TIME_ZONE).toString() : null,
              funder_id: funder || null,
            },
            headers: { "Idempotency-Key": key },
          }),
        );
      }
      return unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/payments/{payment_id}", {
          params: { path: { wedding_id: weddingId, payment_id: payment.id } },
          body: { kind: kind as Kind, amount: money, due_date: due ? due.toString() : null, funder_id: funder || null },
          headers: ifMatch(payment.version),
        }),
      );
    },
    onSuccess: () => done(payment ? "Zapisano płatność" : "Dodano płatność"),
    onError: fail,
  });

  const markPaid = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/payments/{payment_id}/mark-paid", {
          params: { path: { wedding_id: weddingId, payment_id: payment!.id } },
          body: {},
        }),
      ),
    onSuccess: () => done("Oznaczono jako zapłacone"),
    onError: fail,
  });

  const cancel = useMutation({
    mutationFn: () =>
      unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/payments/{payment_id}", {
          params: { path: { wedding_id: weddingId, payment_id: payment!.id } },
          body: { status: "cancelled" },
          headers: ifMatch(payment!.version),
        }),
      ),
    onSuccess: () => done("Płatność anulowana"),
    onError: fail,
  });

  const remove = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE("/api/v1/weddings/{wedding_id}/payments/{payment_id}", {
          params: { path: { wedding_id: weddingId, payment_id: payment!.id } },
        }),
      ),
    onSuccess: () => done("Usunięto płatność"),
    onError: fail,
  });

  const kindHelp =
    kind === "deposit_zadatek"
      ? "Zadatek zwykle przepada, jeśli to Wy zrezygnujecie (art. 394 KC). O skutkach decyduje umowa."
      : kind === "advance_zaliczka"
        ? "Zaliczka co do zasady podlega zwrotowi. O skutkach decyduje umowa."
        : undefined;

  return (
    <Form
      className="form-stack payment-form"
      validationBehavior="aria"
      aria-label={payment ? "Edycja płatności" : "Nowa płatność"}
      onSubmit={(e) => {
        e.preventDefault();
        if (!amount || Number(amount) <= 0) {
          setAmountError("Wpisz kwotę większą od zera.");
          return;
        }
        setAmountError(null);
        save.mutate();
      }}
    >
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      <Select label="Rodzaj" description={kindHelp} options={PAYMENT_KINDS} value={kind} onChange={setKind} />
      <AmountField label="Kwota" value={amount} onChange={setAmount} error={amountError} isRequired />
      <DateField label="Termin (opcjonalnie)" value={due} onChange={setDue} />
      {(funders.data?.funders.length ?? 0) > 0 && (
        <Select
          label="Kto płaci"
          options={[{ id: "", label: "Para" }, ...(funders.data?.funders ?? []).map((f) => ({ id: f.id, label: f.name }))]}
          value={funder}
          onChange={setFunder}
        />
      )}
      {!payment && (
        <Checkbox isSelected={paidAlready} onChange={setPaidAlready}>
          Już zapłacone (dzisiaj)
        </Checkbox>
      )}
      <div className="wp-sheet__actions">
        <Button variant="secondary" onPress={onDone}>
          Wróć
        </Button>
        <Button type="submit" pending={save.isPending}>
          {payment ? "Zapisz płatność" : "Dodaj płatność"}
        </Button>
      </div>
      {payment?.status === "scheduled" && (
        <div className="wp-sheet__actions">
          <Button variant="secondary" pending={markPaid.isPending} onPress={() => markPaid.mutate()}>
            Oznacz jako zapłacone
          </Button>
          <Button variant="text" pending={cancel.isPending} onPress={() => cancel.mutate()}>
            Anuluj płatność
          </Button>
        </div>
      )}
      {payment && (
        <Button variant="text" pending={remove.isPending} onPress={() => remove.mutate()}>
          Usuń płatność
        </Button>
      )}
    </Form>
  );
}
