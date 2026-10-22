import { parseDate, type CalendarDate } from "@internationalized/date";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Form } from "react-aria-components";
import { Link } from "react-router";

import { api, unwrap } from "../../api/client";
import { downloadAuthorized } from "../../api/download";
import { userMessage } from "../../api/errors";
import { DateField } from "../../components/DateField";
import { AmountField, TextField } from "../../components/Field";
import { Button } from "../../components/Button";
import { ConfirmDialog } from "../../components/Overlay";
import { Segmented } from "../../components/Segmented";
import { Select } from "../../components/Select";
import { Card, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate, plural } from "../../lib/format";
import { keys, useWedding, useWeddingId, type Wedding } from "./data";
import { DateCompare } from "./DateCompare";
import { EventsSection } from "./EventsSection";
import { MembersSection } from "./MembersSection";
import { ifMatch, saveErrorMessage } from "./mutations";

export const CEREMONIES = [
  { id: "undecided", label: "Jeszcze nie wiemy" },
  { id: "concordat", label: "Ślub konkordatowy (kościelny)" },
  { id: "civil", label: "Ślub cywilny" },
  { id: "religious_other", label: "Inny ślub wyznaniowy" },
  { id: "humanist", label: "Ślub humanistyczny" },
];

export function SettingsView() {
  const id = useWeddingId();
  const wedding = useWedding(id);
  if (wedding.isPending) {
    return (
      <main className="page">
        <Skeleton lines={6} />
      </main>
    );
  }
  if (!wedding.data) return null;
  const w = wedding.data;
  const canWrite = w.my_role === "owner" || w.my_role === "coorganizer";
  return (
    <main className="page enter-detail" aria-labelledby="settings-h">
      <div>
        <Link to={`/w/${id}/wiecej`} viewTransition className="wp-button wp-button--text back-link">
          ← Więcej
        </Link>
        <h1 id="settings-h">Ustawienia wesela</h1>
        {!canWrite && <p className="text-secondary">Masz dostęp tylko do podglądu ustawień.</p>}
      </div>
      <BasicsSection key={`basics-${w.version}`} wedding={w} canWrite={canWrite} />
      <DateSection key={`date-${w.version}`} wedding={w} canWrite={canWrite} />
      <DateCompare wedding={w} />
      <EventsSection wedding={w} canWrite={canWrite} />
      <MembersSection wedding={w} />
      <WeddingDataSection wedding={w} />
    </main>
  );
}

/** Nazwa, typ ceremonii, miasto, planowana liczba gości, budżet. Wysyłane tylko zmienione pola. */
function BasicsSection({ wedding: w, canWrite }: { wedding: Wedding; canWrite: boolean }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const initial = useMemo(
    () => ({
      name: w.name,
      ceremony: w.ceremony_type,
      city: w.city ?? "",
      guests: w.guest_count_planned?.toString() ?? "",
      budget: w.total_budget?.amount ?? null,
    }),
    [w],
  );
  // Po odświeżeniu danych (konflikt, zmiana partnera) sekcja montuje się na nowo (key = wersja).
  const [form, setForm] = useState(initial);
  const [errors, setErrors] = useState<{ name?: string; guests?: string }>({});
  const [saveError, setSaveError] = useState<string | null>(null);

  const changed: Record<string, unknown> = {};
  if (form.name.trim() !== w.name) changed.name = form.name.trim();
  if (form.ceremony !== w.ceremony_type) changed.ceremony_type = form.ceremony;
  if ((form.city.trim() || null) !== (w.city ?? null)) changed.city = form.city.trim() || null;
  const guests = form.guests.trim() === "" ? null : Number(form.guests);
  if (guests !== (w.guest_count_planned ?? null)) changed.guest_count_planned = guests;
  if (form.budget !== (w.total_budget?.amount ?? null))
    changed.total_budget = form.budget ? { amount: form.budget, currency: "PLN" } : null;
  const dirty = Object.keys(changed).length > 0;

  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}", {
          params: { path: { wedding_id: w.id } },
          body: changed,
          headers: ifMatch(w.version),
        }),
      ),
    onSuccess: async (updated) => {
      setSaveError(null);
      queryClient.setQueryData(keys.wedding(w.id), updated);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.summary(w.id) }),
        queryClient.invalidateQueries({ queryKey: keys.budget(w.id) }),
        queryClient.invalidateQueries({ queryKey: ["weddings"] }),
      ]);
      toast("Zapisano ustawienia wesela");
    },
    onError: (e) => setSaveError(saveErrorMessage(e, queryClient, [keys.wedding(w.id)])),
  });

  return (
    <section aria-labelledby="basics-h" className="form-stack">
      <h2 id="basics-h">Podstawowe</h2>
      <Card>
        <Form
          className="form-stack"
          validationBehavior="aria"
          onSubmit={(e) => {
            e.preventDefault();
            const next: typeof errors = {};
            if (!form.name.trim()) next.name = "Wpisz nazwę wesela.";
            if (form.guests.trim() && !/^\d{1,4}$/.test(form.guests.trim())) next.guests = "Wpisz liczbę, np. 100.";
            setErrors(next);
            if (next.name || next.guests) return;
            save.mutate();
          }}
        >
          {saveError && (
            <Notice tone="error" live>
              {saveError}
            </Notice>
          )}
          <TextField
            label="Nazwa wesela"
            value={form.name}
            onChange={(v) => setForm({ ...form, name: v })}
            error={errors.name}
            isReadOnly={!canWrite}
            isRequired
          />
          <Select
            label="Typ ceremonii"
            description="Od typu zależą zadania z planu (np. nauki przedmałżeńskie)."
            options={CEREMONIES}
            value={form.ceremony}
            onChange={(v) => setForm({ ...form, ceremony: v as typeof form.ceremony })}
          />
          <TextField label="Miejscowość" value={form.city} onChange={(v) => setForm({ ...form, city: v })} isReadOnly={!canWrite} />
          <TextField
            label="Planowana liczba gości"
            inputMode="numeric"
            value={form.guests}
            onChange={(v) => setForm({ ...form, guests: v })}
            error={errors.guests}
            isReadOnly={!canWrite}
          />
          <AmountField
            label="Budżet (limit)"
            description="Na tej kwocie opiera się pasek wykorzystania budżetu."
            value={form.budget}
            onChange={(v) => setForm({ ...form, budget: v })}
          />
          {canWrite && (
            <Button type="submit" pending={save.isPending} isDisabled={!dirty}>
              Zapisz zmiany
            </Button>
          )}
        </Form>
      </Card>
    </section>
  );
}

const MONTHS = ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień"];

type Reschedule = {
  dry_run: boolean;
  changes: { task_id: string; title: string; old_due_date: string | null; new_due_date: string; becomes_overdue: boolean }[];
  kept_manual: number;
  kept_finished: number;
};

/** Data ślubu albo planowany miesiąc. Zapis przez podgląd przesunięć terminów zadań. */
function DateSection({ wedding: w, canWrite }: { wedding: Wedding; canWrite: boolean }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const thisYear = new Date().getFullYear();
  const [mode, setMode] = useState<"date" | "month">(w.wedding_date || !w.planned_month ? "date" : "month");
  const [date, setDate] = useState<CalendarDate | null>(w.wedding_date ? parseDate(w.wedding_date) : null);
  const [month, setMonth] = useState<string | null>(w.planned_month?.slice(5) ?? null);
  const [year, setYear] = useState<string | null>(w.planned_month?.slice(0, 4) ?? null);
  const [preview, setPreview] = useState<Reschedule | null>(null);
  const [error, setError] = useState<string | null>(null);

  const body = () =>
    mode === "date"
      ? { wedding_date: date!.toString(), planned_month: null }
      : { wedding_date: null, planned_month: `${year}-${month}` };

  const run = useMutation({
    mutationFn: (dryRun: boolean) =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/reschedule", {
          params: { path: { wedding_id: w.id } },
          body: { ...body(), dry_run: dryRun },
          headers: ifMatch(w.version),
        }),
      ) as Promise<Reschedule>,
    onSuccess: async (r) => {
      setError(null);
      if (r.dry_run) {
        setPreview(r);
        return;
      }
      setPreview(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.wedding(w.id) }),
        queryClient.invalidateQueries({ queryKey: keys.tasks(w.id) }),
        queryClient.invalidateQueries({ queryKey: keys.summary(w.id) }),
        queryClient.invalidateQueries({ queryKey: ["weddings"] }),
      ]);
      toast(
        `Zapisano nową datę. ${plural(r.changes.length, { one: "Przesunięto # termin zadania", few: "Przesunięto # terminy zadań", many: "Przesunięto # terminów zadań", other: "Przesunięto # terminu zadań" })}.`,
      );
    },
    onError: (e) => {
      setPreview(null);
      setError(saveErrorMessage(e, queryClient, [keys.wedding(w.id)]));
    },
  });

  const current = w.wedding_date
    ? formatDate(w.wedding_date)
    : w.planned_month
      ? `${MONTHS[Number(w.planned_month.slice(5)) - 1]} ${w.planned_month.slice(0, 4)}`
      : "nieustalona";
  const ready = mode === "date" ? !!date : !!(month && year);
  const overdue = preview?.changes.filter((c) => c.becomes_overdue).length ?? 0;

  return (
    <section aria-labelledby="date-h" className="form-stack">
      <h2 id="date-h">Data ślubu</h2>
      <Card className="form-stack">
        <p>
          Teraz: <strong className="num">{current}</strong>
        </p>
        {canWrite && (
          <>
            <Segmented
              label="Co wiecie?"
              value={mode}
              options={[
                { value: "date", label: "Dokładna data" },
                { value: "month", label: "Tylko miesiąc" },
              ]}
              onChange={setMode}
            />
            {mode === "date" ? (
              <DateField label="Data ślubu" value={date} onChange={setDate} />
            ) : (
              <div className="stat-grid">
                <Select
                  label="Miesiąc"
                  options={MONTHS.map((m, i) => ({ id: String(i + 1).padStart(2, "0"), label: m }))}
                  value={month}
                  onChange={setMonth}
                />
                <Select
                  label="Rok"
                  options={Array.from({ length: 6 }, (_, i) => String(thisYear + i)).map((y) => ({ id: y, label: y }))}
                  value={year}
                  onChange={setYear}
                />
              </div>
            )}
            {error && (
              <Notice tone="error" live>
                {error}
              </Notice>
            )}
            <p className="text-secondary">
              Terminy zadań liczone od daty ślubu przesuną się razem z nią. Najpierw pokażemy, co się zmieni.
            </p>
            <Button variant="secondary" isDisabled={!ready} pending={run.isPending && !preview} onPress={() => run.mutate(true)}>
              Pokaż, co się zmieni
            </Button>
          </>
        )}
      </Card>

      <ConfirmDialog title="Zmienić datę ślubu?" isOpen={!!preview} onOpenChange={(o) => !o && setPreview(null)}>
        {preview && (
          <>
            <p>
              {preview.changes.length === 0
                ? "Terminy zadań się nie zmienią."
                : plural(preview.changes.length, {
                    one: "Przesuniemy # termin zadania:",
                    few: "Przesuniemy # terminy zadań:",
                    many: "Przesuniemy # terminów zadań:",
                    other: "Przesuniemy # terminu zadań:",
                  })}
            </p>
            {preview.changes.length > 0 && (
              <ul className="row-list reschedule-list">
                {preview.changes.slice(0, 8).map((c) => (
                  <li key={c.task_id} className="row">
                    <span className="row__body">
                      <span className="row__title">{c.title}</span>
                      <span className="text-secondary num">
                        {c.old_due_date ? formatDate(c.old_due_date) : "bez terminu"} → {formatDate(c.new_due_date)}
                      </span>
                    </span>
                    {c.becomes_overdue && <StatusChip tone="warning">Po terminie</StatusChip>}
                  </li>
                ))}
              </ul>
            )}
            {preview.changes.length > 8 && <p className="text-secondary">…i {preview.changes.length - 8} kolejnych.</p>}
            {overdue > 0 && (
              <Notice tone="warning">
                {plural(overdue, { one: "# zadanie będzie od razu po terminie.", few: "# zadania będą od razu po terminie.", many: "# zadań będzie od razu po terminie.", other: "# zadania będą od razu po terminie." })}
              </Notice>
            )}
            {(preview.kept_manual > 0 || preview.kept_finished > 0) && (
              <p className="text-secondary">
                Bez zmian: zadania z ręcznie ustawionym terminem ({preview.kept_manual}) i zakończone ({preview.kept_finished}).
              </p>
            )}
            <div className="wp-sheet__actions">
              <Button variant="secondary" onPress={() => setPreview(null)}>
                Anuluj
              </Button>
              <Button pending={run.isPending} onPress={() => run.mutate(false)}>
                Zapisz nową datę
              </Button>
            </div>
          </>
        )}
      </ConfirmDialog>
    </section>
  );
}

/** Eksport wszystkich danych wesela (RODO: dostęp i przenoszenie) — dla właściciela. */
function WeddingDataSection({ wedding: w }: { wedding: Wedding }) {
  const exportData = useMutation({
    mutationFn: () => downloadAuthorized(`/api/v1/weddings/${w.id}/export`, `wesele-${new Date().toISOString().slice(0, 10)}.json`),
  });
  if (w.my_role !== "owner") return null;
  return (
    <section aria-labelledby="wdata-h" className="form-stack">
      <h2 id="wdata-h">Dane wesela</h2>
      <Card className="form-stack">
        <p className="text-secondary">
          Kopia wszystkiego, co zapisaliście: plan, budżet, goście, usługodawcy, oferty, harmonogram (plik JSON). Zawiera dane
          osobowe gości — przechowujcie ją bezpiecznie.
        </p>
        {exportData.isError && (
          <Notice tone="error" live>
            {userMessage(exportData.error)}
          </Notice>
        )}
        <Button variant="secondary" pending={exportData.isPending} onPress={() => exportData.mutate()}>
          Pobierz dane wesela
        </Button>
      </Card>
    </section>
  );
}
