import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { AmountField, TextField } from "../../components/Field";
import { ConfirmDialog, Sheet } from "../../components/Overlay";
import { Card, Notice, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatMoney } from "../../lib/format";
import { keys, useBudgetCategories } from "./data";
import { ifMatch, saveErrorMessage } from "./mutations";

type Summary = components["schemas"]["CategorySummary"];
type Split = components["schemas"]["SplitOut"];

/** Procent planu kategorii zużyty przez szacunek (0, gdy brak planu). */
export function categoryUsage(c: Pick<Summary, "planned" | "estimated">): number {
  const plan = Number(c.planned.amount);
  return plan > 0 ? Math.round((Number(c.estimated.amount) / plan) * 100) : 0;
}

export function BudgetCategories({
  weddingId,
  categories,
  hasLimit,
  canWrite,
}: {
  weddingId: string;
  categories: Summary[];
  hasLimit: boolean;
  canWrite: boolean;
}) {
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [split, setSplit] = useState<Split | null>(null);
  const queryClient = useQueryClient();
  const toast = useToast();
  const refresh = () =>
    Promise.all(
      [keys.budget(weddingId), keys.categories(weddingId), keys.summary(weddingId)].map((queryKey) =>
        queryClient.invalidateQueries({ queryKey }),
      ),
    );

  const runSplit = useMutation({
    mutationFn: (dryRun: boolean) =>
      unwrap(api.POST("/api/v1/weddings/{wedding_id}/budget/apply-split", { params: { path: { wedding_id: weddingId } }, body: { dry_run: dryRun } })),
    onSuccess: async (r) => {
      if (r.dry_run) {
        setSplit(r);
        return;
      }
      setSplit(null);
      await refresh();
      toast("Podzielono budżet na kategorie");
    },
  });

  return (
    <section aria-labelledby="cat-h" className="form-stack">
      <div className="section-head">
        <h2 id="cat-h">Kategorie</h2>
        {canWrite && (
          <Button variant="text" icon={<Plus aria-hidden size={18} />} onPress={() => setEditing("new")}>
            Dodaj
          </Button>
        )}
      </div>
      {canWrite && hasLimit && categories.every((c) => Number(c.planned.amount) === 0) && (
        <Notice tone="info" title="Rozdzielcie budżet na kategorie">
          <p>Bez planu na kategorie nie widać, gdzie przekraczacie budżet. Zaproponujemy podział według typowych proporcji — zobaczycie go przed zapisem.</p>
          <Button variant="secondary" pending={runSplit.isPending && !split} onPress={() => runSplit.mutate(true)}>
            Pokaż propozycję podziału
          </Button>
        </Notice>
      )}
      <Card className="form-stack">
        <ul className="row-list">
          {categories.map((c) => {
            const plan = Number(c.planned.amount);
            const usage = categoryUsage(c);
            const body = (
              <>
                <span className="row__title">{c.name}</span>
                <span className="text-secondary num">
                  {formatMoney(c.estimated)} {plan > 0 ? `z ${formatMoney(c.planned)}` : "· bez planu"}
                </span>
                {plan > 0 && (
                  <span className="meter__track meter__track--thin" aria-hidden="true">
                    <span className={`meter__fill${c.over_plan ? " meter__fill--over" : ""}`} style={{ width: `${Math.min(usage, 100)}%` }} />
                  </span>
                )}
              </>
            );
            return (
              <li key={c.id} className="row">
                {canWrite ? (
                  <AriaButton className="row-edit" onPress={() => setEditing(c.id)}>
                    {body}
                  </AriaButton>
                ) : (
                  <div className="row__body">{body}</div>
                )}
                {c.over_plan && <StatusChip tone="error">Ponad plan</StatusChip>}
              </li>
            );
          })}
        </ul>
        {canWrite && hasLimit && (
          <>
            {runSplit.isError && (
              <Notice tone="error" live>
                {userMessage(runSplit.error)}
              </Notice>
            )}
            <Button variant="secondary" pending={runSplit.isPending && !split} onPress={() => runSplit.mutate(true)}>
              Podziel budżet na kategorie
            </Button>
          </>
        )}
      </Card>

      <CategorySheet weddingId={weddingId} categoryId={editing} onClose={() => setEditing(null)} onSaved={refresh} />
      <ConfirmDialog title="Podzielić budżet?" isOpen={!!split} onOpenChange={(o) => !o && setSplit(null)}>
        {split && (
          <>
            <p className="text-secondary">{split.note}</p>
            <ul className="row-list reschedule-list">
              {split.proposals.map((s) => (
                <li key={s.category_id} className="row">
                  <span className="row__body">
                    <span className="row__title">{s.name}</span>
                    <span className="text-secondary num">
                      {formatMoney(s.old_planned)} → {formatMoney(s.new_planned)} ({String(s.share_percent).replace(".", ",")}%)
                    </span>
                  </span>
                </li>
              ))}
            </ul>
            <div className="wp-sheet__actions">
              <Button variant="secondary" onPress={() => setSplit(null)}>
                Anuluj
              </Button>
              <Button pending={runSplit.isPending} onPress={() => runSplit.mutate(false)}>
                Zastosuj podział
              </Button>
            </div>
          </>
        )}
      </ConfirmDialog>
    </section>
  );
}

function CategorySheet({
  weddingId,
  categoryId,
  onClose,
  onSaved,
}: {
  weddingId: string;
  categoryId: string | "new" | null;
  onClose: () => void;
  onSaved: () => Promise<unknown>;
}) {
  const categories = useBudgetCategories(weddingId);
  const category = categoryId && categoryId !== "new" ? (categories.data?.find((c) => c.id === categoryId) ?? null) : null;
  const open = categoryId === "new" || !!category;
  return (
    <Sheet title={category ? "Kategoria" : "Nowa kategoria"} isOpen={open} onOpenChange={(o) => !o && onClose()}>
      {open && (
        <CategoryForm
          key={category ? `${category.id}-${category.version}` : "new"}
          weddingId={weddingId}
          category={category}
          onClose={onClose}
          onSaved={onSaved}
        />
      )}
    </Sheet>
  );
}

function CategoryForm({
  weddingId,
  category,
  onClose,
  onSaved,
}: {
  weddingId: string;
  category: components["schemas"]["CategoryOut"] | null;
  onClose: () => void;
  onSaved: () => Promise<unknown>;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState(category?.name ?? "");
  const [planned, setPlanned] = useState<string | null>(category && Number(category.planned.amount) > 0 ? String(category.planned.amount) : null);
  const [nameError, setNameError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [key] = useState(newIdempotencyKey);

  const save = useMutation({
    mutationFn: () => {
      const body = { name: name.trim(), planned: { amount: planned ?? "0", currency: "PLN" as const } };
      if (!category) {
        return unwrap(
          api.POST("/api/v1/weddings/{wedding_id}/budget/categories", {
            params: { path: { wedding_id: weddingId } },
            body: { ...body, sort_order: 100, is_reserve: false },
            headers: { "Idempotency-Key": key },
          }),
        );
      }
      return unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/budget/categories/{category_id}", {
          params: { path: { wedding_id: weddingId, category_id: category.id } },
          body,
          headers: ifMatch(category.version),
        }),
      );
    },
    onSuccess: async () => {
      await onSaved();
      onClose();
      toast(category ? "Zapisano kategorię" : "Dodano kategorię");
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [keys.categories(weddingId)])),
  });

  const remove = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE("/api/v1/weddings/{wedding_id}/budget/categories/{category_id}", {
          params: { path: { wedding_id: weddingId, category_id: category!.id } },
        }),
      ),
    onSuccess: async () => {
      setConfirmDelete(false);
      await onSaved();
      onClose();
      toast(`Usunięto kategorię „${category!.name}”`);
    },
    onError: (e) => {
      setConfirmDelete(false);
      setError(userMessage(e));
    },
  });

  return (
    <>
      <Form
        className="form-stack"
        validationBehavior="aria"
        onSubmit={(e) => {
          e.preventDefault();
          if (!name.trim()) {
            setNameError("Wpisz nazwę, np. Fotografia.");
            return;
          }
          setNameError(null);
          save.mutate();
        }}
      >
        {error && (
          <Notice tone="error" live>
            {error}
          </Notice>
        )}
        <TextField label="Nazwa" value={name} onChange={setName} error={nameError} isRequired />
        <AmountField
          label="Plan na kategorię (opcjonalnie)"
          description="Ile chcecie przeznaczyć. Ostrzeżemy, gdy szacunek go przekroczy."
          value={planned}
          onChange={setPlanned}
        />
        <Button type="submit" block pending={save.isPending}>
          {category ? "Zapisz" : "Dodaj kategorię"}
        </Button>
        {category && (
          <Button variant="text" onPress={() => setConfirmDelete(true)}>
            Usuń kategorię
          </Button>
        )}
      </Form>
      {category && (
        <ConfirmDialog title="Usunąć kategorię?" isOpen={confirmDelete} onOpenChange={setConfirmDelete}>
          <p>Usunąć można tylko pustą kategorię. Wydatki z „{category.name}” najpierw przenieście do innej kategorii.</p>
          <div className="wp-sheet__actions">
            <Button variant="secondary" onPress={() => setConfirmDelete(false)}>
              Anuluj
            </Button>
            <Button variant="danger" pending={remove.isPending} onPress={() => remove.mutate()}>
              Usuń
            </Button>
          </div>
        </ConfirmDialog>
      )}
    </>
  );
}
