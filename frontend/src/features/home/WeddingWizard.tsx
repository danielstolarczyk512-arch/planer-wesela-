/**
 * Kreator pierwszego uruchomienia (plan dalszej pracy C3): nazwa i termin → ceremonia → budżet
 * i liczba gości → podsumowanie. W około dwie minuty para ma plan zadań dopasowany do ceremonii
 * i terminu (z nadrabianiem zaległości) oraz budżet rozdzielony na kategorie.
 * Każdy krok poza nazwą można pominąć — wszystko da się uzupełnić później w ustawieniach.
 */
import type { CalendarDate } from "@internationalized/date";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Form } from "react-aria-components";
import { useNavigate } from "react-router";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { DateField } from "../../components/DateField";
import { Checkbox, TextField } from "../../components/Field";
import { Sheet } from "../../components/Overlay";
import { Segmented } from "../../components/Segmented";
import { Select } from "../../components/Select";
import { Notice } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate, parseAmountInput, plural } from "../../lib/format";

type Ceremony = components["schemas"]["WeddingCreate"]["ceremony_type"];

export const WIZARD_CEREMONIES: { value: Ceremony; label: string; hint: string }[] = [
  { value: "concordat", label: "Kościelny (konkordatowy)", hint: "Dokumenty z parafii i USC — dodamy obie listy." },
  { value: "civil", label: "Cywilny", hint: "Formalności w urzędzie stanu cywilnego." },
  { value: "religious_other", label: "Inny wyznaniowy", hint: "Formalności wg Waszego wyznania i USC." },
  { value: "humanist", label: "Humanistyczny", hint: "Ceremonia symboliczna; formalnie potrzebny jest też ślub cywilny." },
  { value: "undecided", label: "Jeszcze nie wiemy", hint: "Plan uzupełnicie, gdy zdecydujecie." },
];

const MONTH_LABEL = new Intl.DateTimeFormat("pl-PL", { month: "long", year: "numeric", timeZone: "UTC" });

/** Najbliższe 36 miesięcy jako opcje „RRRR-MM” (gdy nie znacie jeszcze dnia). */
export function monthOptions(now = new Date()): { id: string; label: string }[] {
  return Array.from({ length: 36 }, (_, i) => {
    const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1 + i, 1));
    const id = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
    return { id, label: MONTH_LABEL.format(d) };
  });
}

/** Liczba gości: puste = nie wiemy (null), inaczej 1–2000. */
export function parseGuests(raw: string): number | null | "invalid" {
  const v = raw.trim();
  if (!v) return null;
  if (!/^\d{1,4}$/.test(v)) return "invalid";
  const n = Number(v);
  return n >= 1 && n <= 2000 ? n : "invalid";
}

const STEPS = ["Nazwa i termin", "Ceremonia", "Budżet i goście", "Podsumowanie"] as const;
const NO_MONTH = "__none__";

export function WeddingWizard({ isOpen, onOpenChange }: { isOpen: boolean; onOpenChange: (o: boolean) => void }) {
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [date, setDate] = useState<CalendarDate | null>(null);
  const [month, setMonth] = useState(NO_MONTH);
  const [ceremony, setCeremony] = useState<Ceremony>("undecided");
  const [budget, setBudget] = useState("");
  const [guests, setGuests] = useState("");
  // Rodzice dokładający się do wesela → od razu sponsorzy w „Kto płaci” (bez kwot).
  const [parents, setParents] = useState<{ bride: boolean; groom: boolean }>({ bride: false, groom: false });
  const [errors, setErrors] = useState<{ name?: string; budget?: string; guests?: string }>({});
  // Ten sam klucz przy ponowieniu (np. po błędzie sieci): bez duplikatu wesela.
  const idempotencyKey = useRef(newIdempotencyKey());
  const queryClient = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const months = monthOptions();

  const amount = budget.trim() ? parseAmountInput(budget) : null;
  const guestCount = parseGuests(guests);

  const reset = () => {
    setStep(0);
    setName("");
    setDate(null);
    setMonth(NO_MONTH);
    setCeremony("undecided");
    setBudget("");
    setGuests("");
    setParents({ bride: false, groom: false });
    setErrors({});
  };

  const create = useMutation({
    mutationFn: async () => {
      const w = await unwrap(
        api.POST("/api/v1/weddings", {
          body: {
            name: name.trim(),
            wedding_date: date ? date.toString() : null,
            planned_month: !date && month !== NO_MONTH ? month : null,
            ceremony_type: ceremony,
            guest_count_planned: typeof guestCount === "number" ? guestCount : null,
            total_budget: amount ? { amount, currency: "PLN" } : null,
          },
          headers: { "Idempotency-Key": idempotencyKey.current },
        }),
      );
      let split = 0;
      // Częściowe błędy nie blokują startu, ale para musi o nich wiedzieć (audyt 2026-10-23).
      const failed: string[] = [];
      if (amount) {
        // Budżet od razu na kategorie (typowe proporcje) — para widzi, gdzie przekracza plan.
        // Błąd podziału nie blokuje startu: wesele już jest, podział można zrobić w Budżecie.
        const result = await unwrap(
          api.POST("/api/v1/weddings/{wedding_id}/budget/apply-split", {
            params: { path: { wedding_id: w.id } },
            body: { dry_run: false },
          }),
        ).catch(() => {
          failed.push("podział budżetu (zrobisz go w Budżecie)");
          return null;
        });
        split = result?.proposals.length ?? 0;
      }
      for (const side of ["bride", "groom"] as const) {
        if (!parents[side]) continue;
        // Jak podział budżetu: błąd nie blokuje startu, sponsora można dodać w Budżecie.
        await unwrap(
          api.POST("/api/v1/weddings/{wedding_id}/funders", {
            params: { path: { wedding_id: w.id } },
            body: { name: side === "bride" ? "Rodzice Panny Młodej" : "Rodzice Pana Młodego", side, pledged_amount: null, notes: null },
          }),
        ).catch(() => {
          failed.push(`sponsor „${side === "bride" ? "Rodzice Panny Młodej" : "Rodzice Pana Młodego"}” (dodasz w Budżecie → Kto płaci)`);
        });
      }
      return { w, split, failed };
    },
    onSuccess: async ({ w, split, failed }) => {
      idempotencyKey.current = newIdempotencyKey();
      reset();
      onOpenChange(false);
      await queryClient.invalidateQueries({ queryKey: ["weddings"] });
      const done = split
        ? `Gotowe: plan zadań i budżet podzielony na ${plural(split, { one: "# kategorię", few: "# kategorie", many: "# kategorii", other: "# kategorii" })}`
        : `Utworzono wesele „${w.name}” z planem zadań`;
      toast(failed.length ? `${done}. Nie udało się zapisać: ${failed.join(", ")}.` : done);
      navigate(`/w/${w.id}`);
    },
  });

  const next = () => {
    if (step === 0 && !name.trim()) {
      setErrors({ name: "Wpisz nazwę, np. Anna i Michał." });
      document.getElementById("wizard-name")?.focus();
      return;
    }
    if (step === 2) {
      const e: typeof errors = {};
      if (budget.trim() && !amount) e.budget = "Wpisz kwotę, np. 60 000.";
      if (guestCount === "invalid") e.guests = "Wpisz liczbę od 1 do 2000.";
      setErrors(e);
      if (e.budget || e.guests) return;
    }
    setErrors({});
    if (step < STEPS.length - 1) setStep(step + 1);
    else create.mutate();
  };

  const dirty = name.trim() !== "" || date !== null || budget !== "" || guests !== "";
  const when = date ? formatDate(date.toString()) : month !== NO_MONTH ? months.find((m) => m.id === month)?.label : "bez terminu";

  return (
    <Sheet
      title="Nowe wesele"
      isOpen={isOpen}
      onOpenChange={(o) => {
        if (!o) reset();
        onOpenChange(o);
      }}
      isDirty={dirty && !create.isPending}
    >
      <Form
        className="home-form"
        validationBehavior="aria"
        onSubmit={(e) => {
          e.preventDefault();
          next();
        }}
      >
        <p className="text-secondary wizard-step" aria-live="polite">
          Krok {step + 1} z {STEPS.length}: <strong>{STEPS[step]}</strong>
        </p>
        <ol className="wizard-dots" aria-hidden="true">
          {STEPS.map((s, i) => (
            <li key={s} className={i <= step ? "is-done" : undefined} />
          ))}
        </ol>

        {step === 0 && (
          <>
            <TextField
              id="wizard-name"
              label="Nazwa wesela"
              description="Np. imiona pary. Widzicie ją tylko Wy i osoby, które zaprosicie."
              value={name}
              onChange={setName}
              error={errors.name}
              isRequired
              autoFocus
            />
            <DateField
              label="Data ślubu (opcjonalnie)"
              description="Na jej podstawie ustalimy terminy zadań."
              value={date}
              onChange={setDate}
            />
            {!date && (
              <Select
                label="Albo planowany miesiąc"
                options={[{ id: NO_MONTH, label: "Jeszcze nie wiemy" }, ...months]}
                value={month}
                onChange={setMonth}
              />
            )}
          </>
        )}

        {step === 1 && (
          <>
            <Segmented
              label="Jaki ślub planujecie?"
              variant="chips"
              value={ceremony}
              options={WIZARD_CEREMONIES.map((c) => ({ value: c.value, label: c.label }))}
              onChange={setCeremony}
            />
            <p className="text-secondary">{WIZARD_CEREMONIES.find((c) => c.value === ceremony)?.hint}</p>
          </>
        )}

        {step === 2 && (
          <>
            <TextField
              label="Budżet na całe wesele (opcjonalnie)"
              description="Podzielimy go na kategorie wg typowych proporcji — zmienicie to w każdej chwili."
              inputMode="decimal"
              value={budget}
              onChange={setBudget}
              error={errors.budget}
            />
            <TextField
              label="Planowana liczba gości (opcjonalnie)"
              description="Przyda się do porównywania ofert sal i cateringu."
              inputMode="numeric"
              value={guests}
              onChange={setGuests}
              error={errors.guests}
            />
            <fieldset className="plain-fieldset form-stack">
              <legend className="wp-field__label">Czy ktoś dokłada się do wesela? (opcjonalnie)</legend>
              <Checkbox isSelected={parents.bride} onChange={(v) => setParents((p) => ({ ...p, bride: v }))}>
                Rodzice Panny Młodej
              </Checkbox>
              <Checkbox isSelected={parents.groom} onChange={(v) => setParents((p) => ({ ...p, groom: v }))}>
                Rodzice Pana Młodego
              </Checkbox>
              <p className="text-secondary">Dodamy ich w Budżet → „Kto płaci”. Kwoty wpiszecie, kiedy będziecie gotowi.</p>
            </fieldset>
          </>
        )}

        {step === 3 && (
          <>
            <dl className="wizard-summary">
              <div>
                <dt>Wesele</dt>
                <dd>{name.trim()}</dd>
              </div>
              <div>
                <dt>Termin</dt>
                <dd>{when}</dd>
              </div>
              <div>
                <dt>Ceremonia</dt>
                <dd>{WIZARD_CEREMONIES.find((c) => c.value === ceremony)?.label}</dd>
              </div>
              <div>
                <dt>Budżet</dt>
                <dd className="num">{amount ? `${Number(amount).toLocaleString("pl-PL")} zł` : "później"}</dd>
              </div>
              <div>
                <dt>Goście</dt>
                <dd className="num">{typeof guestCount === "number" ? guestCount : "później"}</dd>
              </div>
              {(parents.bride || parents.groom) && (
                <div>
                  <dt>Dokładają się</dt>
                  <dd>{[parents.bride && "rodzice Panny Młodej", parents.groom && "rodzice Pana Młodego"].filter(Boolean).join(", ")}</dd>
                </div>
              )}
            </dl>
            <p className="text-secondary">
              Utworzymy plan zadań dopasowany do ceremonii{date || month !== NO_MONTH ? " i terminu (zaległe rozłożymy na najbliższe tygodnie)" : ""}
              {amount ? " oraz podział budżetu na kategorie" : ""}.
            </p>
          </>
        )}

        {create.isError && (
          <Notice tone="error" title="Nie zapisano." live>
            {userMessage(create.error)}
          </Notice>
        )}
        <div className="wp-sheet__actions">
          {step > 0 && (
            <Button variant="secondary" onPress={() => setStep(step - 1)}>
              Wstecz
            </Button>
          )}
          <Button type="submit" pending={create.isPending}>
            {step === STEPS.length - 1 ? "Utwórz wesele" : "Dalej"}
          </Button>
        </div>
      </Form>
    </Sheet>
  );
}
