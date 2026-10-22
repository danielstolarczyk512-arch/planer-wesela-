import { parseDate, type CalendarDate } from "@internationalized/date";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Form } from "react-aria-components";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { DateField } from "../../components/DateField";
import { AmountField, TextField } from "../../components/Field";
import { ConfirmDialog, Sheet } from "../../components/Overlay";
import { Select } from "../../components/Select";
import { Notice } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatMoney } from "../../lib/format";
import { keys, useBudgetCategories, type BudgetItem } from "./data";
import { ItemPayments } from "./ItemPayments";
import { ifMatch, saveErrorMessage } from "./mutations";

type ItemPatch = components["schemas"]["app__modules__budget__schemas__ItemUpdate"];

export const INDEXATION = [
  { id: "none", label: "Cena stała (bez podwyżek)" },
  { id: "cpi", label: "Wg inflacji (wskaźnik GUS)" },
  { id: "price_list", label: "Wg cennika z roku wesela" },
  { id: "cap", label: "Podwyżka z limitem (np. max 5%)" },
];

const day = (iso: string | null | undefined) => (iso ? parseDate(iso) : null);

const STATUSES = [
  { id: "planned", label: "Szacunek" },
  { id: "confirmed", label: "Umowa podpisana" },
  { id: "cancelled", label: "Rezygnujemy" },
];

/** Edycja wydatku. Kwota trafia do „planu” (szacunek) albo „potwierdzonej” (umowa). */
export function EditItemSheet({ weddingId, item, onClose }: { weddingId: string; item: BudgetItem | null; onClose: () => void }) {
  return (
    <Sheet title="Wydatek" isOpen={!!item} onOpenChange={(o) => !o && onClose()}>
      {item && <EditItemForm key={`${item.id}-${item.version}`} weddingId={weddingId} item={item} onClose={onClose} />}
    </Sheet>
  );
}

function EditItemForm({ weddingId, item, onClose }: { weddingId: string; item: BudgetItem; onClose: () => void }) {
  const categories = useBudgetCategories(weddingId);
  const queryClient = useQueryClient();
  const toast = useToast();
  const startAmount = (item.status === "confirmed" ? item.confirmed?.amount : item.planned?.amount) ?? item.estimated.amount;
  const [name, setName] = useState(item.name);
  const [category, setCategory] = useState<string>(item.category_id);
  const [status, setStatus] = useState<string>(item.status === "paid" ? "confirmed" : item.status);
  const [amount, setAmount] = useState<string | null>(startAmount);
  const [errors, setErrors] = useState<{ name?: string; amount?: string }>({});
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [indexation, setIndexation] = useState<string>(item.indexation ?? "none");
  const [cap, setCap] = useState(item.indexation_cap_percent != null ? String(Number(item.indexation_cap_percent)) : "");
  const [fixedOn, setFixedOn] = useState<CalendarDate | null>(day(item.price_fixed_on));
  const [reviewOn, setReviewOn] = useState<CalendarDate | null>(day(item.price_review_on));
  const capNumber = Number(cap.replace(",", "."));
  const capError = indexation === "cap" && !(cap !== "" && capNumber >= 0 && capNumber <= 100) ? "Podajcie limit od 0 do 100%." : undefined;
  const perGuest = item.cost_mode === "per_guest";

  const refresh = () =>
    Promise.all(
      [keys.items(weddingId), keys.budget(weddingId), keys.summary(weddingId), keys.payments(weddingId)].map((queryKey) =>
        queryClient.invalidateQueries({ queryKey }),
      ),
    );

  const save = useMutation({
    mutationFn: (body: Partial<ItemPatch>) =>
      unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/budget/items/{item_id}", {
          params: { path: { wedding_id: weddingId, item_id: item.id } },
          body,
          headers: ifMatch(item.version),
        }),
      ),
    onSuccess: async () => {
      await refresh();
      onClose();
      toast("Zapisano wydatek");
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [keys.items(weddingId)])),
  });

  const remove = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE("/api/v1/weddings/{wedding_id}/budget/items/{item_id}", {
          params: { path: { wedding_id: weddingId, item_id: item.id } },
        }),
      ),
    onSuccess: async () => {
      setConfirmDelete(false);
      await refresh();
      onClose();
      toast(`Usunięto wydatek „${item.name}”`);
    },
    onError: (e) => {
      setConfirmDelete(false);
      setError(`Nie usunięto. ${userMessage(e)}`);
    },
  });

  return (
    <>
      <Form
        className="form-stack"
        validationBehavior="aria"
        onSubmit={(e) => {
          e.preventDefault();
          const next: typeof errors = {};
          if (!name.trim()) next.name = "Wpisz nazwę.";
          if (!perGuest && !amount) next.amount = "Wpisz kwotę (może być szacunkowa).";
          setErrors(next);
          if (next.name || next.amount || capError) return;
          const body: Partial<ItemPatch> = {};
          if (name.trim() !== item.name) body.name = name.trim();
          if (category !== item.category_id) body.category_id = category;
          if (status !== item.status && !(item.status === "paid" && status === "confirmed")) body.status = status as ItemPatch["status"];
          if (!perGuest) {
            const money = { amount: amount!, currency: "PLN" as const };
            // Przejście na „umowę” zapisuje kwotę z umowy, nawet jeśli liczba się nie zmieniła.
            if (status === "confirmed" && (amount !== startAmount || !item.confirmed)) body.confirmed = money;
            else if (status !== "confirmed" && amount !== startAmount) body.planned = money;
          }
          if (indexation !== (item.indexation ?? "none")) body.indexation = indexation as ItemPatch["indexation"];
          const capValue = indexation === "cap" ? String(capNumber) : null;
          if ((item.indexation_cap_percent != null ? String(Number(item.indexation_cap_percent)) : null) !== capValue) body.indexation_cap_percent = capValue;
          if ((fixedOn?.toString() ?? null) !== (item.price_fixed_on ?? null)) body.price_fixed_on = fixedOn?.toString() ?? null;
          if ((reviewOn?.toString() ?? null) !== (item.price_review_on ?? null)) body.price_review_on = reviewOn?.toString() ?? null;
          if (Object.keys(body).length === 0) return onClose();
          save.mutate(body);
        }}
      >
        {error && (
          <Notice tone="error" live>
            {error}
          </Notice>
        )}
        <TextField label="Nazwa" value={name} onChange={setName} error={errors.name} isRequired />
        <Select
          label="Kategoria"
          options={(categories.data ?? []).map((c) => ({ id: c.id, label: c.name }))}
          value={category}
          onChange={setCategory}
        />
        <Select label="Status" options={STATUSES} value={status} onChange={setStatus} />
        {perGuest ? (
          <p className="text-secondary">
            Koszt za osobę ({item.unit_price ? formatMoney(item.unit_price) : "brak ceny"}
            {item.child_unit_price ? `, dziecko 4–12 lat ${formatMoney(item.child_unit_price)}` : ""}) × liczba gości
            {item.guest_count_used != null ? ` (${item.guest_count_used}${item.children_used ? `, w tym dzieci: ${item.children_used}` : ""})` : ""}. Zmienisz go
            w ofercie.
          </p>
        ) : (
          <AmountField
            label={status === "confirmed" ? "Kwota z umowy" : "Kwota (szacunek)"}
            value={amount}
            onChange={setAmount}
            error={errors.amount}
            isRequired
          />
        )}
        <p className="text-secondary num">Wpłacono dotąd: {formatMoney(item.paid)}</p>
        <details className="form-stack indexation-fields" open={indexation !== "none"}>
          <summary>Podwyżka ceny w umowie (waloryzacja)</summary>
          <Select
            label="Czy umowa pozwala podnieść cenę?"
            description="Sprawdźcie zapis o waloryzacji lub cenniku w umowie."
            options={INDEXATION}
            value={indexation}
            onChange={setIndexation}
          />
          {indexation === "cap" && (
            <TextField label="Maksymalna podwyżka łącznie (%)" inputMode="decimal" value={cap} onChange={setCap} error={capError} />
          )}
          {indexation !== "none" && (
            <>
              <DateField label="Od kiedy obowiązuje cena (data umowy lub oferty)" value={fixedOn} onChange={setFixedOn} />
              <DateField label="Termin aneksu lub potwierdzenia ceny (opcjonalnie)" value={reviewOn} onChange={setReviewOn} />
            </>
          )}
        </details>
        <Button type="submit" block pending={save.isPending}>
          Zapisz
        </Button>
        <Button variant="text" onPress={() => setConfirmDelete(true)}>
          Usuń wydatek
        </Button>
      </Form>
      <ItemPayments weddingId={weddingId} itemId={item.id} />
      <ConfirmDialog title="Usunąć wydatek?" isOpen={confirmDelete} onOpenChange={setConfirmDelete}>
        <p>„{item.name}” zniknie z budżetu razem z zapisanymi płatnościami (zadatki, raty).</p>
        {Number(item.paid.amount) > 0 && (
          <Notice tone="warning">Zapisano już wpłaty: {formatMoney(item.paid)}. Jeśli rezygnujecie, lepiej ustawić status „Rezygnujemy”.</Notice>
        )}
        <div className="wp-sheet__actions">
          <Button variant="secondary" onPress={() => setConfirmDelete(false)}>
            Anuluj
          </Button>
          <Button variant="danger" pending={remove.isPending} onPress={() => remove.mutate()}>
            Usuń
          </Button>
        </div>
      </ConfirmDialog>
    </>
  );
}
