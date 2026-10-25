import { parseDate, type CalendarDate } from "@internationalized/date";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useRef, useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";
import { useNavigate } from "react-router";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { DateField } from "../../components/DateField";
import { AmountField, Checkbox, TextField } from "../../components/Field";
import { Sheet } from "../../components/Overlay";
import { Segmented } from "../../components/Segmented";
import { Select } from "../../components/Select";
import { Card, Notice } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { ifMatch, saveErrorMessage } from "./mutations";
import { COMPONENT_KINDS, vendorKeys, type ComponentKind, type Offer } from "./vendors";

type ComponentIn = components["schemas"]["ComponentIn"];
type TermIn = components["schemas"]["TermIn"];
type OfferPatch = components["schemas"]["OfferUpdate"];

interface Row {
  key: string;
  label: string;
  kind: ComponentKind;
  amount: string | null;
  quantity: string;
  included: boolean;
  optional: boolean;
  /** Pola z analizy AI zostają bez zmian (cytat, pewność), dopóki ktoś nie zmieni kwoty. */
  source?: ComponentIn;
  /** Pozycja poprawin: liczona od liczby gości poprawin. */
  eventKind?: ComponentIn["event_kind"];
  /** Podpowiedź z szablonu: bez kwoty jest pomijana przy zapisie. */
  template?: boolean;
}

const newRow = (over: Partial<Row> = {}): Row => ({
  key: newIdempotencyKey(),
  label: "",
  kind: "per_guest",
  amount: null,
  quantity: "",
  included: false,
  optional: false,
  ...over,
});

/**
 * Szablony typowych ofert: para zaczyna od listy pozycji, które zwykle są w ofercie danej
 * kategorii, i tylko wpisuje kwoty (albo usuwa zbędne). Kwot nie podpowiadamy.
 */
const TEMPLATES: Record<string, Partial<Row>[]> = {
  venue: [
    { label: "Menu weselne", kind: "per_guest" },
    { label: "Menu dla dzieci", kind: "per_child" },
    { label: "Napoje i alkohol", kind: "per_guest" },
    { label: "Tort", kind: "fixed" },
    { label: "Poprawiny", kind: "per_guest", eventKind: "after_party" },
    { label: "Posiłek dla obsługi (muzycy, fotograf)", kind: "per_crew" },
  ],
  catering: [
    { label: "Menu weselne", kind: "per_guest" },
    { label: "Menu dla dzieci", kind: "per_child" },
    { label: "Obsługa kelnerska", kind: "fixed" },
    { label: "Posiłek dla obsługi", kind: "per_crew" },
  ],
  photographer: [
    { label: "Reportaż z dnia ślubu", kind: "fixed" },
    { label: "Plener", kind: "fixed", optional: true },
    { label: "Album", kind: "fixed", optional: true },
    { label: "Dojazd", kind: "fixed" },
  ],
  videographer: [
    { label: "Film z dnia ślubu", kind: "fixed" },
    { label: "Nagrania z drona", kind: "fixed", optional: true },
    { label: "Dojazd", kind: "fixed" },
  ],
  dj: [
    { label: "Oprawa muzyczna (pakiet godzin)", kind: "fixed" },
    { label: "Nadgodzina", kind: "per_hour", optional: true },
    { label: "Dojazd", kind: "fixed" },
  ],
  band: [
    { label: "Oprawa muzyczna (pakiet godzin)", kind: "fixed" },
    { label: "Nadgodzina", kind: "per_hour", optional: true },
    { label: "Dojazd", kind: "fixed" },
  ],
  florist: [
    { label: "Dekoracja sali", kind: "fixed" },
    { label: "Dekoracja kościoła lub USC", kind: "fixed" },
    { label: "Bukiet i butonierki", kind: "fixed" },
  ],
  decorations: [
    { label: "Dekoracja sali", kind: "fixed" },
    { label: "Dekoracja kościoła lub USC", kind: "fixed" },
    { label: "Montaż i demontaż", kind: "fixed" },
  ],
  transport: [
    { label: "Auto do ślubu", kind: "fixed" },
    { label: "Bus dla gości", kind: "fixed" },
  ],
};

function rowsOf(offer: Offer | null, vendorCategory?: string): Row[] {
  if (!offer) {
    const template = vendorCategory ? TEMPLATES[vendorCategory] : undefined;
    return template ? template.map((t) => newRow({ ...t, template: true })) : [newRow({ label: "", kind: "fixed" })];
  }
  return offer.components.map((c) =>
    newRow({
      label: c.label,
      kind: c.kind,
      amount: c.amount != null ? String(c.amount) : null,
      quantity: c.quantity != null ? String(c.quantity) : "",
      included: c.included,
      optional: c.optional,
      source: c,
    }),
  );
}

/** Pozycje do zapisu: podpowiedzi z szablonu bez kwoty pomijamy (para ich nie uzupełniła). */
export function filled(rows: Row[]): Row[] {
  return rows.filter((r) => !(r.template && !r.amount && !r.included));
}

/** Wiersz formularza → pozycja dla API. Zmieniona ręcznie pozycja traci etykietę „niepewne”. */
export function toComponent(r: Row): ComponentIn {
  const amount = r.included ? null : r.amount;
  const quantity = r.kind === "per_hour" || r.kind === "per_unit" ? r.quantity.replace(",", ".") || null : null;
  const unchanged =
    r.source &&
    r.source.label === r.label.trim() &&
    r.source.kind === r.kind &&
    String(r.source.amount ?? "") === String(amount ?? "") &&
    !!r.source.included === r.included &&
    !!r.source.optional === r.optional;
  return {
    label: r.label.trim(),
    kind: r.kind,
    amount: amount,
    quantity: quantity,
    included: r.included,
    optional: r.optional,
    event_kind: r.eventKind ?? r.source?.event_kind ?? null,
    citation: unchanged ? (r.source?.citation ?? null) : null,
    confidence: unchanged ? (r.source?.confidence ?? "high") : "high",
  };
}

function stripTerm(t: components["schemas"]["TermOut"]): TermIn {
  const rest: Partial<components["schemas"]["TermOut"]> = { ...t };
  delete rest.id;
  return rest as TermIn;
}

export function OfferEditorSheet({
  weddingId,
  vendorId,
  offer,
  isOpen,
  onClose,
  vendorCategory,
}: {
  weddingId: string;
  vendorId: string;
  offer: Offer | null;
  isOpen: boolean;
  onClose: () => void;
  /** Kategoria usługodawcy: nowa oferta startuje z typowych pozycji. */
  vendorCategory?: string;
}) {
  return (
    <Sheet title={offer ? "Edycja oferty" : "Nowa oferta"} isOpen={isOpen} onOpenChange={(o) => !o && onClose()}>
      {isOpen && (
        <OfferForm
          key={offer ? `${offer.id}-${offer.version}` : "new"}
          weddingId={weddingId}
          vendorId={vendorId}
          offer={offer}
          onClose={onClose}
          vendorCategory={vendorCategory}
        />
      )}
    </Sheet>
  );
}

function OfferForm({
  weddingId,
  vendorId,
  offer,
  onClose,
  vendorCategory,
}: {
  weddingId: string;
  vendorId: string;
  offer: Offer | null;
  onClose: () => void;
  vendorCategory?: string;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const deposit = offer?.terms.find((t) => t.term_type === "deposit");
  const [title, setTitle] = useState(offer?.title ?? "");
  const [validUntil, setValidUntil] = useState<CalendarDate | null>(offer?.valid_until ? parseDate(offer.valid_until) : null);
  const [minGuests, setMinGuests] = useState(offer?.min_guests != null ? String(offer.min_guests) : "");
  const [rows, setRows] = useState<Row[]>(() => rowsOf(offer, vendorCategory));
  const [depositAmount, setDepositAmount] = useState<string | null>(deposit?.amount?.amount != null ? String(deposit.amount.amount) : null);
  const [depositKind, setDepositKind] = useState<"deposit_zadatek" | "advance_zaliczka">(deposit?.deposit_kind ?? "deposit_zadatek");
  const [notes, setNotes] = useState(offer?.notes ?? "");
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const [error, setError] = useState<string | null>(null);
  const key = useRef(newIdempotencyKey());

  const update = (k: string, patch: Partial<Row>) => setRows((all) => all.map((r) => (r.key === k ? { ...r, ...patch } : r)));

  const save = useMutation({
    mutationFn: () => {
      const otherTerms = (offer?.terms ?? []).filter((t) => t.term_type !== "deposit").map(stripTerm);
      const terms: TermIn[] = depositAmount
        ? [
            {
              ...(deposit ? stripTerm(deposit) : {}),
              term_type: "deposit",
              amount: { amount: depositAmount, currency: "PLN" },
              deposit_kind: depositKind,
              installments: [],
              confidence: deposit && deposit.amount?.amount != null && String(deposit.amount.amount) === depositAmount ? deposit.confidence : "high",
            },
            ...otherTerms,
          ]
        : otherTerms;
      const fields = {
        title: title.trim(),
        valid_until: validUntil ? validUntil.toString() : null,
        min_guests: minGuests.trim() ? Number(minGuests) : null,
        notes: notes.trim() || null,
        components: filled(rows).map(toComponent),
        terms,
      };
      if (!offer) {
        return unwrap(
          api.POST("/api/v1/weddings/{wedding_id}/offers", {
            params: { path: { wedding_id: weddingId } },
            body: { ...fields, vendor_id: vendorId, status: "draft" },
            headers: { "Idempotency-Key": key.current },
          }),
        );
      }
      return unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/offers/{offer_id}", {
          params: { path: { wedding_id: weddingId, offer_id: offer.id } },
          body: fields as OfferPatch,
          headers: ifMatch(offer.version),
        }),
      );
    },
    onSuccess: async (saved) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: vendorKeys.offers(weddingId) }),
        queryClient.invalidateQueries({ queryKey: vendorKeys.all(weddingId) }),
      ]);
      onClose();
      toast(offer ? "Zapisano ofertę" : "Dodano ofertę — sprawdźcie ją i zatwierdźcie");
      if (!offer) navigate(`/w/${weddingId}/oferty/${saved.id}`, { viewTransition: true });
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [vendorKeys.offers(weddingId)])),
  });

  return (
    <Form
      className="form-stack"
      validationBehavior="aria"
      onSubmit={(e) => {
        e.preventDefault();
        const next: typeof errors = {};
        if (!title.trim()) next.title = "Wpisz nazwę, np. Pakiet Złoty.";
        if (minGuests.trim() && !/^\d{1,4}$/.test(minGuests.trim())) next.minGuests = "Wpisz liczbę gości.";
        filled(rows).forEach((r) => {
          if (!r.label.trim()) next[`label-${r.key}`] = "Wpisz, za co jest ta kwota.";
          if (!r.included && !r.amount) next[`amount-${r.key}`] = "Wpisz kwotę albo zaznacz „W cenie”.";
          if (r.kind === "percent" && r.amount && Number(r.amount) > 100) next[`amount-${r.key}`] = "Najwyżej 100%.";
        });
        if (filled(rows).length === 0) next.rows = "Dodaj przynajmniej jedną pozycję cenową.";
        setErrors(next);
        if (Object.values(next).some(Boolean)) return;
        save.mutate();
      }}
    >
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      {offer && offer.status === "approved" && (
        <Notice tone="info">Zmiana cen cofnie ofertę do sprawdzenia — trzeba ją będzie zatwierdzić ponownie.</Notice>
      )}
      <TextField label="Nazwa oferty" value={title} onChange={setTitle} error={errors.title} isRequired />
      <div className="stat-grid">
        <DateField label="Ważna do (opcjonalnie)" value={validUntil} onChange={setValidUntil} />
        <TextField label="Min. liczba gości" inputMode="numeric" value={minGuests} onChange={setMinGuests} error={errors.minGuests} />
      </div>

      <h3>Pozycje cenowe</h3>
      {!offer && vendorCategory && TEMPLATES[vendorCategory] && (
        <p className="text-secondary">
          Zaczynamy od pozycji, które zwykle są w takiej ofercie. Wpiszcie kwoty — pozycje bez kwoty pominiemy przy zapisie.
        </p>
      )}
      {errors.rows && (
        <Notice tone="error" live>
          {errors.rows}
        </Notice>
      )}
      {rows.map((r, i) => (
        <Card key={r.key} className="form-stack offer-row" aria-label={`Pozycja ${i + 1}`}>
          <div className="section-head">
            <strong>Pozycja {i + 1}</strong>
            <AriaButton
              className="wp-icon-button"
              aria-label={`Usuń pozycję ${i + 1}${r.label ? `: ${r.label}` : ""}`}
              onPress={() => setRows((all) => all.filter((x) => x.key !== r.key))}
            >
              <X aria-hidden size={20} />
            </AriaButton>
          </div>
          <TextField label="Za co?" value={r.label} onChange={(v) => update(r.key, { label: v })} error={errors[`label-${r.key}`]} />
          <Select
            label="Sposób liczenia"
            options={COMPONENT_KINDS.map((k) => ({ id: k.id, label: k.label }))}
            value={r.kind}
            onChange={(v) => update(r.key, { kind: v as ComponentKind })}
          />
          {!r.included &&
            (r.kind === "percent" ? (
              <TextField
                label="Procent"
                inputMode="decimal"
                value={r.amount ?? ""}
                onChange={(v) => update(r.key, { amount: v.replace(",", ".") || null })}
                error={errors[`amount-${r.key}`]}
              />
            ) : (
              <AmountField
                label={`Kwota ${COMPONENT_KINDS.find((k) => k.id === r.kind)?.unit ?? ""}`.trim()}
                value={r.amount}
                onChange={(v) => update(r.key, { amount: v })}
                error={errors[`amount-${r.key}`]}
              />
            ))}
          {(r.kind === "per_hour" || r.kind === "per_unit") && (
            <TextField
              label={r.kind === "per_hour" ? "Ile godzin (opcjonalnie)" : "Ile sztuk (opcjonalnie)"}
              inputMode="decimal"
              value={r.quantity}
              onChange={(v) => update(r.key, { quantity: v })}
            />
          )}
          {r.kind === "per_crew" && <p className="text-secondary">Liczba osób obsługi to suma z kart usługodawców (pole „Posiłki dla obsługi”).</p>}
          {(r.eventKind ?? r.source?.event_kind) === "after_party" && <p className="text-secondary">Liczone od liczby gości poprawin.</p>}
          <Checkbox isSelected={r.included} onChange={(v) => update(r.key, { included: v })}>
            W cenie (bez dopłaty)
          </Checkbox>
          <Checkbox isSelected={r.optional} onChange={(v) => update(r.key, { optional: v })}>
            Opcjonalne (np. fontanna czekoladowa)
          </Checkbox>
        </Card>
      ))}
      <Button variant="secondary" icon={<Plus aria-hidden size={20} />} onPress={() => setRows((all) => [...all, newRow({ kind: "fixed" })])}>
        Dodaj pozycję
      </Button>

      <h3>Zadatek lub zaliczka</h3>
      <Segmented
        label="Rodzaj wpłaty"
        value={depositKind}
        options={[
          { value: "deposit_zadatek", label: "Zadatek" },
          { value: "advance_zaliczka", label: "Zaliczka" },
        ]}
        onChange={setDepositKind}
      />
      <p className="text-secondary">
        Zadatek zwykle przepada, jeśli to Wy zrezygnujecie; zaliczka co do zasady podlega zwrotowi. Sprawdźcie zapis w umowie.
      </p>
      <AmountField label="Kwota (opcjonalnie)" value={depositAmount} onChange={setDepositAmount} />
      <TextField label="Notatki (opcjonalnie)" value={notes} onChange={setNotes} />
      <Button type="submit" block pending={save.isPending}>
        {offer ? "Zapisz ofertę" : "Dodaj ofertę"}
      </Button>
    </Form>
  );
}
