import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Quote } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { Checkbox } from "../../components/Field";
import { ConfirmDialog } from "../../components/Overlay";
import { Card, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate, formatMoney } from "../../lib/format";
import { useCanWrite, useWeddingId } from "./data";
import { useDocuments } from "./Documents";
import { DocumentText } from "./DocumentText";
import { OfferEditorSheet } from "./OfferEditor";
import {
  COMPONENT_KINDS,
  CONFIDENCE,
  OFFER_STATUS,
  TERM_LABEL,
  useOffer,
  vendorKeys,
  type OfferComponent,
  type OfferTerm,
} from "./vendors";

/** „250 zł za osobę” / „W cenie” / „10%”. */
export function priceLabel(c: Pick<OfferComponent, "kind" | "amount" | "included" | "quantity">): string {
  if (c.included) return "W cenie";
  if (c.amount == null) return "Brak kwoty";
  if (c.kind === "percent") return `${String(c.amount).replace(".", ",").replace(/,00$/, "")}%`;
  const unit = COMPONENT_KINDS.find((k) => k.id === c.kind)?.unit ?? "";
  const qty = c.quantity != null && (c.kind === "per_hour" || c.kind === "per_unit") ? ` × ${String(c.quantity).replace(/\.00$/, "")}` : "";
  return `${formatMoney({ amount: String(c.amount), currency: "PLN" })}${unit ? ` ${unit}` : ""}${qty}`;
}

function Citation({ citation }: { citation: OfferComponent["citation"] }) {
  if (!citation) return null;
  return (
    <blockquote className="citation">
      <Quote aria-hidden size={14} />
      <span>
        „{citation.quote}”{citation.page ? <span className="text-secondary"> — str. {citation.page}</span> : null}
      </span>
    </blockquote>
  );
}

function ConfidenceChip({ value }: { value: OfferComponent["confidence"] }) {
  const c = CONFIDENCE[value];
  return c ? <StatusChip tone={c.tone}>{c.label}</StatusChip> : null;
}

export function OfferView() {
  const id = useWeddingId();
  const { offerId = "" } = useParams();
  const offer = useOffer(id, offerId);
  const docs = useDocuments(id);
  const sourceDoc = docs.data?.find((d) => d.versions.some((v) => v.id === offer.data?.source_document_version_id));
  const canWrite = useCanWrite(id);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [approving, setApproving] = useState(false);
  const [checked, setChecked] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: vendorKeys.offers(id) }),
      queryClient.invalidateQueries({ queryKey: vendorKeys.all(id) }),
    ]);

  const approve = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/offers/{offer_id}/approve", {
          params: { path: { wedding_id: id, offer_id: offerId } },
          body: { confirm_unverified: checked },
        }),
      ),
    onSuccess: async () => {
      setApproving(false);
      setError(null);
      await refresh();
      toast("Oferta sprawdzona — można ją porównać");
    },
    onError: (e) => {
      setApproving(false);
      setError(userMessage(e));
    },
  });

  const reject = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/offers/{offer_id}/reject", {
          params: { path: { wedding_id: id, offer_id: offerId } },
        }),
      ),
    onSuccess: async () => {
      await refresh();
      toast("Oferta odrzucona");
    },
    onError: (e) => setError(userMessage(e)),
  });

  const remove = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE("/api/v1/weddings/{wedding_id}/offers/{offer_id}", {
          params: { path: { wedding_id: id, offer_id: offerId } },
        }),
      ),
    onSuccess: async () => {
      setDeleting(false);
      const vendorId = offer.data?.vendor_id;
      await refresh();
      toast("Usunięto ofertę");
      navigate(vendorId ? `/w/${id}/uslugodawcy/${vendorId}` : `/w/${id}/uslugodawcy`, { replace: true });
    },
    onError: (e) => {
      setDeleting(false);
      setError(userMessage(e));
    },
  });

  if (offer.isPending) {
    return (
      <main className="page">
        <Skeleton lines={8} />
      </main>
    );
  }
  if (offer.isError) {
    return (
      <main className="page">
        <Notice tone="error" title="Nie udało się wczytać oferty." live>
          {userMessage(offer.error)}
        </Notice>
      </main>
    );
  }
  const o = offer.data;
  const st = OFFER_STATUS[o.status];
  const reviewable = o.status === "draft" || o.status === "needs_review";
  const fromAi = o.source !== "manual";

  return (
    <main className="page enter-detail" aria-labelledby="offer-h">
      <div className="view-head">
        <div>
          <Link to={`/w/${id}/uslugodawcy/${o.vendor_id}`} viewTransition className="wp-button wp-button--text back-link">
            ← {o.vendor_name}
          </Link>
          <h1 id="offer-h">{o.title}</h1>
          <p className="chips">
            <StatusChip tone={st.tone}>{st.label}</StatusChip>
            {o.valid_until && <span className="text-secondary">ważna do {formatDate(o.valid_until)}</span>}
            {o.min_guests != null && <span className="text-secondary">min. {o.min_guests} gości</span>}
          </p>
        </div>
        {canWrite && o.status !== "selected" && (
          <Button variant="secondary" onPress={() => setEditing(true)}>
            Edytuj
          </Button>
        )}
      </div>

      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      {reviewable && (
        <Notice tone={o.unverified_fields > 0 ? "warning" : "info"} title={fromAi ? "Odczytane z dokumentu — sprawdźcie" : "Szkic"}>
          {o.unverified_fields > 0
            ? `Pola do sprawdzenia: ${o.unverified_fields}. Porównajcie je z dokumentem (cytaty pod pozycjami), popraw, a potem zatwierdźcie.`
            : "Sprawdźcie kwoty i zatwierdźcie ofertę — dopiero wtedy trafi do porównania."}
        </Notice>
      )}
      {o.status === "selected" && o.selected_budget_item_id && (
        <Notice tone="success">
          Wybrana oferta — jest w budżecie.{" "}
          <Link to={`/w/${id}/budzet`} viewTransition>
            Przejdź do budżetu
          </Link>
        </Notice>
      )}

      <section aria-labelledby="components-h" className="form-stack">
        <h2 id="components-h">Pozycje cenowe</h2>
        <Card>
          {o.components.length === 0 ? (
            <p className="text-secondary">Brak pozycji.</p>
          ) : (
            <ul className="row-list">
              {o.components.map((c) => (
                <li key={c.id} className="row offer-line">
                  <span className="row__body">
                    <span className="row__title">
                      {c.label}
                      {c.optional && <span className="text-secondary"> (opcjonalnie)</span>}
                    </span>
                    <Citation citation={c.citation} />
                  </span>
                  <span className="offer-line__end">
                    <strong className="num">{priceLabel(c)}</strong>
                    <ConfidenceChip value={c.confidence} />
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>

      {o.terms.length > 0 && (
        <section aria-labelledby="terms-h" className="form-stack">
          <h2 id="terms-h">Warunki</h2>
          <Card>
            <ul className="row-list">
              {o.terms.map((t) => (
                <TermRow key={t.id} term={t} />
              ))}
            </ul>
          </Card>
        </section>
      )}
      {o.notes && <p className="text-secondary prewrap">{o.notes}</p>}
      {sourceDoc && o.source_document_version_id && (
        <DocumentText
          weddingId={id}
          documentId={sourceDoc.id}
          versionId={o.source_document_version_id}
          title={`Dokument źródłowy: ${sourceDoc.title}`}
        />
      )}

      {canWrite && (
        <div className="form-stack">
          {reviewable && (
            <Button
              block
              pending={approve.isPending}
              onPress={() => (o.unverified_fields > 0 ? setApproving(true) : approve.mutate())}
            >
              Zatwierdź ofertę
            </Button>
          )}
          {o.status === "approved" && (
            <Link to={`/w/${id}/oferty/porownanie?kategoria=${o.vendor_category}`} viewTransition className="wp-button wp-button--primary">
              Porównaj z innymi
            </Link>
          )}
          {o.status !== "rejected" && o.status !== "selected" && (
            <Button variant="secondary" pending={reject.isPending} onPress={() => reject.mutate()}>
              Odrzuć ofertę
            </Button>
          )}
          {o.status !== "selected" && (
            <Button variant="text" onPress={() => setDeleting(true)}>
              Usuń ofertę
            </Button>
          )}
        </div>
      )}

      <OfferEditorSheet weddingId={id} vendorId={o.vendor_id} offer={o} isOpen={editing} onClose={() => setEditing(false)} />
      <ConfirmDialog title="Zatwierdzić mimo niepewnych pól?" isOpen={approving} onOpenChange={setApproving}>
        <p>
          AI nie była pewna {o.unverified_fields} {o.unverified_fields === 1 ? "pola" : "pól"}. Porównanie ofert będzie tak dobre jak
          te kwoty.
        </p>
        <Checkbox isSelected={checked} onChange={setChecked}>
          Sprawdziłem/am kwoty z dokumentem
        </Checkbox>
        <div className="wp-sheet__actions">
          <Button variant="secondary" onPress={() => setApproving(false)}>
            Wróć do sprawdzania
          </Button>
          <Button isDisabled={!checked} pending={approve.isPending} onPress={() => approve.mutate()}>
            Zatwierdź
          </Button>
        </div>
      </ConfirmDialog>
      <ConfirmDialog title="Usunąć ofertę?" isOpen={deleting} onOpenChange={setDeleting}>
        <p>„{o.title}” zniknie razem z pozycjami i warunkami. Dokument źródłowy zostanie.</p>
        <div className="wp-sheet__actions">
          <Button variant="secondary" onPress={() => setDeleting(false)}>
            Anuluj
          </Button>
          <Button variant="danger" pending={remove.isPending} onPress={() => remove.mutate()}>
            Usuń
          </Button>
        </div>
      </ConfirmDialog>
    </main>
  );
}

function TermRow({ term: t }: { term: OfferTerm }) {
  const title = t.deposit_kind === "deposit_zadatek" ? "Zadatek" : t.deposit_kind === "advance_zaliczka" ? "Zaliczka" : TERM_LABEL[t.term_type];
  return (
    <li className="row offer-line">
      <span className="row__body">
        <span className="row__title">
          {title}
        </span>
        {t.text && <span className="text-secondary prewrap">{t.text}</span>}
        {(t.installments ?? []).length > 0 && (
          <span className="text-secondary num">
            {(t.installments ?? [])
              .map((i) => `${formatMoney(i.amount)}${i.due_date ? ` do ${formatDate(i.due_date)}` : i.days_before_wedding != null ? ` ${i.days_before_wedding} dni przed ślubem` : ""}`)
              .join(" · ")}
          </span>
        )}
        <Citation citation={t.citation} />
      </span>
      <span className="offer-line__end">
        {t.amount && <strong className="num">{formatMoney(t.amount)}</strong>}
        <ConfidenceChip value={t.confidence} />
      </span>
    </li>
  );
}
