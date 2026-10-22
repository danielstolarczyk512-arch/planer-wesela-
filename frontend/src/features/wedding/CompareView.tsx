import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { useMemo, useState } from "react";
import { Button as AriaButton, Disclosure, DisclosurePanel, Heading } from "react-aria-components";
import { Link, useNavigate, useSearchParams } from "react-router";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { Checkbox } from "../../components/Field";
import { ConfirmDialog } from "../../components/Overlay";
import { PremiumBadge } from "../../components/Premium";
import { Segmented } from "../../components/Segmented";
import { Card, EmptyState, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatMoney, plural } from "../../lib/format";
import { keys, useCanWrite, useWeddingId } from "./data";
import { EMPTY_SCENARIO, SCENARIO_LABELS, ScenarioFields, ScenarioResults, type ScenarioDraft } from "./ScenarioCompare";
import { useChecklist, type ChecklistItem } from "./VendorChecklist";
import { useOffers, useVendorCategories, vendorKeys, type Offer } from "./vendors";

type Basis = components["schemas"]["CompareIn"]["guest_basis"];
type Compare = components["schemas"]["CompareOut"];
type Quote = components["schemas"]["OfferQuote"];

const BASES: { value: Basis; label: string }[] = [
  { value: "planned", label: "Planowani" },
  { value: "invited", label: "Zaproszeni" },
  { value: "confirmed", label: "Potwierdzeni" },
];

/**
 * Porównanie realnego kosztu ofert z jednej kategorii przy tej samej liczbie gości.
 * Wybór oferty pokazuje skutki (budżet, płatności, odrzucenie pozostałych) przed zapisem.
 */
export function CompareView() {
  const id = useWeddingId();
  const offers = useOffers(id);
  const categories = useVendorCategories();
  const canWrite = useCanWrite(id);
  const [params, setParams] = useSearchParams();
  const comparable = useMemo(() => (offers.data ?? []).filter((o) => o.status === "approved" || o.status === "selected"), [offers.data]);
  const presentCategories = [...new Set(comparable.map((o) => o.vendor_category))];
  const category = params.get("kategoria") ?? presentCategories[0] ?? "";
  const inCategory = comparable.filter((o) => o.vendor_category === category);
  const [basis, setBasis] = useState<Basis>("planned");
  const [optional, setOptional] = useState(false);
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [choosing, setChoosing] = useState<Quote | null>(null);
  // „Co jeśli”: własna liczba gości zamiast listy (np. +20 osób, poprawiny dla połowy).
  const [whatIf, setWhatIf] = useState<ScenarioDraft>(EMPTY_SCENARIO);
  // Dwa scenariusze obok siebie (Premium): A „Plan”, B „Co jeśli” — koszt, różnica i raty.
  const [twoScenarios, setTwoScenarios] = useState(false);
  const [planA, setPlanA] = useState<ScenarioDraft>(EMPTY_SCENARIO);
  const num = (v: string) => (/^\d{1,4}$/.test(v.trim()) ? Number(v.trim()) : null);
  const invalid = (d: ScenarioDraft) => (Object.values(d).some((v) => v.trim() && num(v) === null) ? "Wpisz liczbę osób." : null);
  const whatIfError = invalid(whatIf);
  const planAError = twoScenarios ? invalid(planA) : null;
  const checklist = useChecklist(id);
  const chosenIds = inCategory.filter((o) => !excluded.has(o.id)).map((o) => o.id);
  const label = (slug: string) => categories.data?.find((c) => c.slug === slug)?.label ?? slug;

  const compare = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/offers/compare", {
          params: { path: { wedding_id: id } },
          body: {
            offer_ids: chosenIds.slice(0, 10),
            guest_basis: basis,
            include_optional: optional,
            adults: num(whatIf.adults),
            children: num(whatIf.children),
            after_party_adults: num(whatIf.afterParty),
          },
        }),
      ),
  });

  const scenarioBody = (label: string, d: ScenarioDraft) => ({
    label,
    guest_basis: basis,
    include_optional: optional,
    adults: num(d.adults),
    children: num(d.children),
    after_party_adults: num(d.afterParty),
  });
  const scenarios = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/offers/scenarios", {
          params: { path: { wedding_id: id } },
          body: {
            offer_ids: chosenIds.slice(0, 10),
            scenarios: [scenarioBody(SCENARIO_LABELS[0], planA), scenarioBody(SCENARIO_LABELS[1], whatIf)],
          },
        }),
      ),
  });
  const running = twoScenarios ? scenarios : compare;

  return (
    <main className="page enter-detail" aria-labelledby="compare-h">
      <div>
        <Link to={`/w/${id}/uslugodawcy`} viewTransition className="wp-button wp-button--text back-link">
          ← Usługodawcy
        </Link>
        <h1 id="compare-h">Porównanie ofert</h1>
        <p className="text-secondary">Realny koszt przy tej samej liczbie gości — z dopłatami, serwisem i minimum gości.</p>
      </div>

      {offers.isPending && <Skeleton lines={6} />}
      {offers.data && comparable.length === 0 && (
        <EmptyState title="Brak sprawdzonych ofert">
          Do porównania trafiają oferty zatwierdzone. Otwórzcie ofertę, sprawdźcie kwoty i zatwierdźcie ją.
        </EmptyState>
      )}

      {presentCategories.length > 1 && (
        <Segmented
          label="Kategoria"
          variant="chips"
          value={category}
          options={presentCategories.map((c) => ({ value: c, label: label(c) }))}
          onChange={(v) => {
            compare.reset();
            scenarios.reset();
            setParams({ kategoria: v }, { replace: true });
          }}
        />
      )}

      {inCategory.length > 0 && (
        <Card className="form-stack">
          <fieldset className="plain-fieldset form-stack">
            <legend className="wp-field__label">Oferty</legend>
            {inCategory.map((o) => (
              <Checkbox
                key={o.id}
                isSelected={!excluded.has(o.id)}
                onChange={(v) =>
                  setExcluded((s) => {
                    const next = new Set(s);
                    if (v) next.delete(o.id);
                    else next.add(o.id);
                    return next;
                  })
                }
              >
                {o.vendor_name}: {o.title}
              </Checkbox>
            ))}
          </fieldset>
          <Segmented label="Liczba gości" value={basis} options={BASES} onChange={setBasis} />
          <Checkbox isSelected={optional} onChange={setOptional}>
            Doliczaj pozycje opcjonalne
          </Checkbox>
          <Disclosure className="quote__details">
            <Heading level={2} className="household__heading">
              <AriaButton slot="trigger" className="household__trigger">
                <span className="row__body">
                  <span>
                    Co jeśli… <PremiumBadge />
                  </span>
                  <span className="text-secondary">Własna liczba gości: np. +20 osób albo poprawiny dla połowy.</span>
                </span>
                <ChevronDown aria-hidden size={20} className="household__chevron" />
              </AriaButton>
            </Heading>
            <DisclosurePanel>
              <div className="form-stack">
                <Checkbox isSelected={twoScenarios} onChange={setTwoScenarios}>
                  Porównaj dwa scenariusze (koszt i raty obok siebie)
                </Checkbox>
                {twoScenarios && <ScenarioFields legend={`A: ${SCENARIO_LABELS[0]}`} value={planA} onChange={setPlanA} error={planAError} />}
                <ScenarioFields legend={twoScenarios ? `B: ${SCENARIO_LABELS[1]}` : "Liczba gości"} value={whatIf} onChange={setWhatIf} error={whatIfError} />
                <p className="text-secondary">Puste pola: liczba z listy gości („{BASES.find((b) => b.value === basis)?.label}”).</p>
              </div>
            </DisclosurePanel>
          </Disclosure>
          {running.isError && (
            <Notice tone="error" live>
              {userMessage(running.error)}
            </Notice>
          )}
          <Button
            block
            isDisabled={chosenIds.length === 0 || !!whatIfError || !!planAError}
            pending={running.isPending}
            onPress={() => (twoScenarios ? scenarios.mutate() : compare.mutate())}
          >
            Porównaj
          </Button>
        </Card>
      )}

      {twoScenarios && scenarios.data && <ScenarioResults data={scenarios.data} />}

      {!twoScenarios && compare.data && (
        <Results
          data={compare.data}
          offers={inCategory}
          checklist={checklist.data ?? []}
          canWrite={canWrite}
          onChoose={setChoosing}
        />
      )}

      <ChooseDialog
        weddingId={id}
        quote={choosing}
        offer={inCategory.find((o) => o.id === choosing?.offer_id) ?? null}
        all={offers.data ?? []}
        basis={basis}
        onClose={() => setChoosing(null)}
      />
    </main>
  );
}

function scenarioText(s: Compare["scenario"]): string {
  const adults = Number(s.adults ?? 0);
  const children = Number(s.children ?? 0);
  const crew = Number(s.crew ?? 0);
  const a = plural(adults, { one: "# dorosły", few: "# dorosłych", many: "# dorosłych", other: "# dorosłego" });
  const people = children > 0 ? `${a} i ${plural(children, { one: "# dziecko", few: "# dzieci", many: "# dzieci", other: "# dziecka" })}` : a;
  return crew > 0 ? `${people} (+ posiłki dla obsługi: ${crew})` : people;
}

function Results({
  data,
  offers,
  checklist,
  canWrite,
  onChoose,
}: {
  data: Compare;
  offers: Offer[];
  checklist: ChecklistItem[];
  canWrite: boolean;
  onChoose: (q: Quote) => void;
}) {
  return (
    <section aria-labelledby="results-h" className="form-stack" aria-live="polite">
      <h2 id="results-h">Wynik dla: {scenarioText(data.scenario)}</h2>
      {data.results.map((q) => {
        const cheapest = q.offer_id === data.cheapest_offer_id;
        const offer = offers.find((o) => o.id === q.offer_id);
        const notes = [...q.warnings, ...q.unknown.map((u) => `Brak ceny: ${u}`), ...q.missing_terms];
        return (
          <Card key={q.offer_id} className="form-stack quote" aria-label={`${q.vendor_name}: ${q.title}`}>
            <div className="section-head">
              <span className="row__body">
                <strong>{q.vendor_name}</strong>
                <span className="text-secondary">{q.title}</span>
              </span>
              {cheapest ? (
                <StatusChip tone="success">Najtańsza</StatusChip>
              ) : (
                <StatusChip tone="neutral">+{formatMoney(q.difference_to_cheapest)}</StatusChip>
              )}
            </div>
            <p className="quote__total">
              <span className="stat__value num">{formatMoney(q.total)}</span>
              {q.per_adult_effective && <span className="text-secondary num">realnie {formatMoney(q.per_adult_effective)} za dorosłego</span>}
            </p>
            {notes.length > 0 && (
              <Notice tone="warning">
                <ul className="conflict-list">
                  {notes.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              </Notice>
            )}
            <VendorAnswers items={checklist.filter((i) => i.vendor_id === offer?.vendor_id)} />
            {q.optional_excluded.length > 0 && (
              <p className="text-secondary">Bez opcjonalnych: {q.optional_excluded.join(", ")}.</p>
            )}
            <Disclosure className="quote__details">
              <Heading level={3} className="household__heading">
                <AriaButton slot="trigger" className="household__trigger">
                  <span className="row__body">Z czego to wynika</span>
                  <ChevronDown aria-hidden size={20} className="household__chevron" />
                </AriaButton>
              </Heading>
              <DisclosurePanel>
                <ul className="row-list">
                  {q.lines.map((l, i) => (
                    <li key={`${l.label}-${i}`} className="row offer-line">
                      <span className="row__body">
                        <span className="row__title">{l.label}</span>
                        {l.note && <span className="text-secondary">{l.note}</span>}
                      </span>
                      <span className="offer-line__end num">{formatMoney(l.subtotal)}</span>
                    </li>
                  ))}
                </ul>
              </DisclosurePanel>
            </Disclosure>
            {canWrite && offer?.status === "approved" && (
              <Button variant={cheapest ? "primary" : "secondary"} onPress={() => onChoose(q)}>
                Wybieram tę ofertę
              </Button>
            )}
            {offer?.status === "selected" && <StatusChip tone="success">Wybrana</StatusChip>}
          </Card>
        );
      })}
      <p className="text-secondary">{data.disclaimer}</p>
    </section>
  );
}

/** Odpowiedzi na pytania i braki w umowie — obok ceny, żeby porównywać nie tylko kwoty. */
function VendorAnswers({ items }: { items: ChecklistItem[] }) {
  const answered = items.filter((i) => i.kind === "question" && i.answer);
  const missing = items.filter((i) => i.kind === "contract" && i.status === "missing");
  if (answered.length === 0 && missing.length === 0) return null;
  return (
    <div className="form-stack">
      {answered.length > 0 && (
        <dl className="answers">
          {answered.map((i) => (
            <div key={i.id}>
              <dt className="text-secondary">{i.text}</dt>
              <dd>{i.answer}</dd>
            </div>
          ))}
        </dl>
      )}
      {missing.length > 0 && <p className="text-secondary">Brakuje w umowie: {missing.map((i) => i.text).join("; ")}.</p>}
    </div>
  );
}

function ChooseDialog({
  weddingId,
  quote,
  offer,
  all,
  basis,
  onClose,
}: {
  weddingId: string;
  quote: Quote | null;
  offer: Offer | null;
  all: Offer[];
  basis: Basis;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const [payments, setPayments] = useState(true);
  const [rejectOthers, setRejectOthers] = useState(true);
  const competing = offer
    ? all.filter(
        (o) => o.id !== offer.id && o.vendor_category === offer.vendor_category && ["draft", "needs_review", "approved"].includes(o.status),
      )
    : [];
  const paymentTerms = (offer?.terms ?? []).filter((t) => t.term_type === "deposit" || t.term_type === "payment_schedule");

  const select = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/offers/{offer_id}/select", {
          params: { path: { wedding_id: weddingId, offer_id: offer!.id } },
          body: { guest_basis: basis, create_payments: payments, reject_competing: rejectOthers },
        }),
      ),
    onSuccess: async (r) => {
      await Promise.all(
        [vendorKeys.offers(weddingId), vendorKeys.all(weddingId), keys.items(weddingId), keys.budget(weddingId), keys.summary(weddingId), keys.payments(weddingId)].map(
          (queryKey) => queryClient.invalidateQueries({ queryKey }),
        ),
      );
      onClose();
      toast(
        `Wybrano. W budżecie: ${formatMoney(r.planned_amount)}${r.payments_created ? `, płatności: ${r.payments_created}` : ""}${r.warnings.length ? ". Sprawdź uwagi w ofercie." : ""}`,
      );
      navigate(`/w/${weddingId}/oferty/${r.offer_id}`, { viewTransition: true });
    },
  });

  return (
    <ConfirmDialog title="Wybrać tę ofertę?" isOpen={!!quote} onOpenChange={(o) => !o && onClose()}>
      {quote && offer && (
        <>
          <p>
            <strong>
              {quote.vendor_name}: {quote.title}
            </strong>
          </p>
          <p>Co się stanie:</p>
          <ul className="consequences">
            <li>
              W budżecie pojawi się pozycja „{quote.vendor_name}: {quote.title}” na {formatMoney(quote.total)} jako umowa
              (liczone dla gości: {BASES.find((b) => b.value === basis)?.label.toLocaleLowerCase("pl-PL")}).
            </li>
            <li>„{quote.vendor_name}” dostanie status „Zarezerwowany”.</li>
            {payments && paymentTerms.length > 0 && <li>Dodamy płatności z warunków oferty (zadatek, raty) z terminami.</li>}
            {rejectOthers && competing.length > 0 && (
              <li>
                {plural(competing.length, {
                  one: "# inna oferta z tej kategorii zostanie odrzucona",
                  few: "# inne oferty z tej kategorii zostaną odrzucone",
                  many: "# innych ofert z tej kategorii zostanie odrzuconych",
                  other: "# innej oferty z tej kategorii zostanie odrzucone",
                })}
                : {competing.map((c) => c.vendor_name).join(", ")}.
              </li>
            )}
          </ul>
          {paymentTerms.length > 0 && (
            <Checkbox isSelected={payments} onChange={setPayments}>
              Dodaj płatności z warunków oferty
            </Checkbox>
          )}
          {competing.length > 0 && (
            <Checkbox isSelected={rejectOthers} onChange={setRejectOthers}>
              Odrzuć pozostałe oferty z tej kategorii
            </Checkbox>
          )}
          <p className="text-secondary">To nie jest podpisanie umowy — o tym decydujecie z usługodawcą.</p>
          {select.isError && (
            <Notice tone="error" live>
              {userMessage(select.error)}
            </Notice>
          )}
          <div className="wp-sheet__actions">
            <Button variant="secondary" onPress={onClose}>
              Anuluj
            </Button>
            <Button pending={select.isPending} onPress={() => select.mutate()}>
              Wybieram
            </Button>
          </div>
        </>
      )}
    </ConfirmDialog>
  );
}
