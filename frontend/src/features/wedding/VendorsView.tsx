import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Plus } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { Form, Input, Label, SearchField } from "react-aria-components";
import { Link, useNavigate, useSearchParams } from "react-router";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { ApiError, userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { TextField } from "../../components/Field";
import { Sheet } from "../../components/Overlay";
import { Select } from "../../components/Select";
import { Card, EmptyState, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { normalize } from "./GuestsView";
import { MONEY_SECTIONS, SectionNav } from "./SectionNav";
import { ifMatch, saveErrorMessage } from "./mutations";
import { useCanWrite, useWeddingId } from "./data";
import { OFFER_STATUS, useOffers, useVendorCategories, useVendors, vendorKeys, VENDOR_STATUS, type Vendor } from "./vendors";

type VendorPatch = components["schemas"]["VendorUpdate"];

/** Firmy, których ludzie pracują na sali i zwykle jedzą posiłek (koszt w ofercie sali). */
const CREW_CATEGORIES = new Set(["dj", "band", "musician", "photographer", "videographer", "wedding_planner", "bartender", "photobooth", "attractions"]);

export function VendorsView() {
  const id = useWeddingId();
  const vendors = useVendors(id);
  const offers = useOffers(id);
  const canWrite = useCanWrite(id);
  const [adding, setAdding] = useState(false);
  const [query, setQuery] = useState("");
  // ?nowy=<kategoria>: skrót z zadania planu („Dodaj usługodawcę do tego zadania”).
  const [params, setParams] = useSearchParams();
  const preset = params.get("nowy");
  const closeNew = () => {
    setAdding(false);
    if (preset) setParams({}, { replace: true });
  };

  const groups = useMemo(() => {
    const q = normalize(query.trim());
    const map = new Map<string, Vendor[]>();
    for (const v of vendors.data ?? []) {
      if (q && !normalize(`${v.name} ${v.city ?? ""} ${v.category_label}`).includes(q)) continue;
      map.set(v.category_label, [...(map.get(v.category_label) ?? []), v]);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b, "pl"));
  }, [vendors.data, query]);

  const offerCount = (vendorId: string) => (offers.data ?? []).filter((o) => o.vendor_id === vendorId && o.status !== "rejected");
  const toReview = (offers.data ?? []).filter((o) => o.status === "needs_review").length;

  return (
    <main className="page enter-tab" aria-labelledby="vendors-h">
      <SectionNav label="Budżet" sections={MONEY_SECTIONS} />
      <div className="view-head">
        <div>
          <h1 id="vendors-h">Usługodawcy</h1>
          <p className="text-secondary">Sala, fotograf, muzyka — kontakty, oferty i porównania.</p>
        </div>
        {canWrite && (vendors.data?.length ?? 0) > 0 && (
          <Button variant="secondary" icon={<Plus aria-hidden size={20} />} onPress={() => setAdding(true)}>
            Dodaj usługodawcę
          </Button>
        )}
      </div>

      {toReview > 0 && (
        <Notice tone="warning">
          Oferty do sprawdzenia: {toReview}. Przed porównaniem potwierdźcie kwoty odczytane z dokumentów.
        </Notice>
      )}
      {(offers.data ?? []).filter((o) => o.status === "approved").length >= 2 && (
        <Link to={`/w/${id}/oferty/porownanie`} viewTransition className="wp-card link-card">
          <span className="row__body">
            <strong>Porównaj oferty</strong>
            <span className="text-secondary">Realny koszt przy tej samej liczbie gości</span>
          </span>
          <ChevronRight aria-hidden size={20} />
        </Link>
      )}

      {vendors.isPending && <Skeleton lines={6} />}
      {vendors.isError && (
        <Notice tone="error" title="Nie udało się wczytać usługodawców." live>
          {userMessage(vendors.error)}
        </Notice>
      )}
      {vendors.data?.length === 0 && (
        <EmptyState
          title="Nie ma jeszcze usługodawców"
          action={canWrite ? <Button onPress={() => setAdding(true)}>Dodaj pierwszego</Button> : undefined}
        >
          Zapiszcie salę, fotografa czy zespół, z którymi rozmawiacie. Potem dodacie ich oferty i porównacie realne koszty.
        </EmptyState>
      )}

      {(vendors.data?.length ?? 0) > 4 && (
        <SearchField className="wp-field" value={query} onChange={setQuery}>
          <Label className="wp-field__label">Szukaj usługodawcy</Label>
          <Input className="wp-field__input" placeholder="np. dworek, fotograf, Kraków" />
        </SearchField>
      )}

      {groups.map(([label, list]) => (
        <section key={label} className="form-stack" aria-label={label}>
          <h2>{label}</h2>
          <Card>
            <ul className="row-list">
              {list.map((v) => {
                const own = offerCount(v.id);
                const st = VENDOR_STATUS[v.status];
                return (
                  <li key={v.id}>
                    <Link to={`/w/${id}/uslugodawcy/${v.id}`} viewTransition className="row link-card">
                      <span className="row__body">
                        <span className="row__title">{v.name}</span>
                        <span className="text-secondary">
                          {[
                            v.city,
                            own.length > 0 &&
                              (own.some((o) => o.status === "selected")
                                ? "oferta wybrana"
                                : `ofert: ${own.length}${own.some((o) => o.status === "needs_review") ? ` (${OFFER_STATUS.needs_review.label.toLocaleLowerCase("pl-PL")})` : ""}`),
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                      </span>
                      <StatusChip tone={st.tone}>{st.label}</StatusChip>
                      <ChevronRight aria-hidden size={20} />
                    </Link>
                  </li>
                );
              })}
            </ul>
          </Card>
        </section>
      ))}

      <VendorSheet weddingId={id} vendor={null} isOpen={adding || (canWrite && !!preset)} onClose={closeNew} initialCategory={preset} />
    </main>
  );
}

/* ------------------------------------------------------------ usługodawca: formularz */

export function VendorSheet({
  weddingId,
  vendor,
  isOpen,
  onClose,
  initialCategory,
}: {
  weddingId: string;
  vendor: Vendor | null;
  isOpen: boolean;
  onClose: () => void;
  initialCategory?: string | null;
}) {
  return (
    <Sheet title={vendor ? "Usługodawca" : "Nowy usługodawca"} isOpen={isOpen} onOpenChange={(o) => !o && onClose()}>
      {isOpen && <VendorForm key={vendor ? `${vendor.id}-${vendor.version}` : "new"} weddingId={weddingId} vendor={vendor} onClose={onClose} initialCategory={initialCategory} />}
    </Sheet>
  );
}

function VendorForm({
  weddingId,
  vendor,
  onClose,
  initialCategory,
}: {
  weddingId: string;
  vendor: Vendor | null;
  onClose: () => void;
  initialCategory?: string | null;
}) {
  const categories = useVendorCategories();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const [name, setName] = useState(vendor?.name ?? "");
  const [category, setCategory] = useState<string | null>(vendor?.category ?? initialCategory ?? null);
  const [status, setStatus] = useState<string>(vendor?.status ?? "considering");
  const [city, setCity] = useState(vendor?.city ?? "");
  const [phone, setPhone] = useState(vendor?.phone ?? "");
  const [email, setEmail] = useState(vendor?.email ?? "");
  const [website, setWebsite] = useState(vendor?.website_url ?? "");
  const [notes, setNotes] = useState(vendor?.notes ?? "");
  const [crew, setCrew] = useState(vendor?.crew_meals != null ? String(vendor.crew_meals) : "");
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const [error, setError] = useState<string | null>(null);
  const key = useRef(newIdempotencyKey());

  const save = useMutation({
    mutationFn: () => {
      const fields = {
        name: name.trim(),
        category: category as VendorPatch["category"],
        status: status as Vendor["status"],
        city: city.trim() || null,
        phone: phone.trim() || null,
        email: email.trim() || null,
        // Bez schematu dopisujemy https:// („dworek.pl” → „https://dworek.pl”).
        website_url: website.trim() ? (/^https?:\/\//i.test(website.trim()) ? website.trim() : `https://${website.trim()}`) : null,
        notes: notes.trim() || null,
        crew_meals: CREW_CATEGORIES.has(category ?? "") && crew.trim() ? Number(crew) : null,
      };
      if (!vendor) {
        return unwrap(
          api.POST("/api/v1/weddings/{wedding_id}/vendors", {
            params: { path: { wedding_id: weddingId } },
            body: { ...fields, category: fields.category ?? "other" },
            headers: { "Idempotency-Key": key.current },
          }),
        );
      }
      return unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/vendors/{vendor_id}", {
          params: { path: { wedding_id: weddingId, vendor_id: vendor.id } },
          body: fields,
          headers: ifMatch(vendor.version),
        }),
      );
    },
    onSuccess: async (v) => {
      await queryClient.invalidateQueries({ queryKey: vendorKeys.all(weddingId) });
      onClose();
      const dup = v.possible_duplicates?.[0];
      toast(dup ? `Zapisano. Podobny usługodawca już jest: ${dup.name}` : vendor ? "Zapisano usługodawcę" : `Dodano „${v.name}”`);
      if (!vendor) navigate(`/w/${weddingId}/uslugodawcy/${v.id}`, { viewTransition: true });
    },
    onError: (e) => {
      if (e instanceof ApiError && e.fieldErrors.length > 0) {
        const map: Record<string, string> = {};
        for (const f of e.fieldErrors) {
          if (f.field === "email") map.email = "Sprawdź adres e-mail.";
          if (f.field === "phone") map.phone = "Wpisz numer telefonu, np. 600 100 200.";
          if (f.field === "website_url") map.website = "Sprawdź adres strony, np. dworek.pl.";
        }
        if (Object.keys(map).length) {
          setErrors(map);
          return;
        }
      }
      setError(saveErrorMessage(e, queryClient, [vendorKeys.all(weddingId)]));
    },
  });

  return (
    <Form
      className="form-stack"
      validationBehavior="aria"
      onSubmit={(e) => {
        e.preventDefault();
        const next: typeof errors = {};
        if (!name.trim()) next.name = "Wpisz nazwę, np. Dworek Pod Lipami.";
        if (!category) next.category = "Wybierz kategorię.";
        if (crew.trim() && (!/^\d{1,2}$/.test(crew.trim()) || Number(crew) > 50)) next.crew = "Wpisz liczbę osób (0–50).";
        setErrors(next);
        if (next.name || next.category || next.crew) return;
        save.mutate();
      }}
    >
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      <TextField label="Nazwa" value={name} onChange={setName} error={errors.name} isRequired autoFocus={!vendor} />
      <Select
        label="Kategoria"
        options={(categories.data ?? []).map((c) => ({ id: c.slug, label: c.label }))}
        value={category}
        onChange={setCategory}
        error={errors.category}
        placeholder="Wybierz"
        isRequired
      />
      <Select
        label="Etap"
        options={Object.entries(VENDOR_STATUS).map(([id, s]) => ({ id, label: s.label }))}
        value={status}
        onChange={setStatus}
      />
      <TextField label="Miejscowość (opcjonalnie)" value={city} onChange={setCity} />
      <TextField label="Telefon (opcjonalnie)" type="tel" inputMode="tel" value={phone} onChange={setPhone} error={errors.phone} />
      <TextField label="E-mail (opcjonalnie)" type="email" inputMode="email" value={email} onChange={setEmail} error={errors.email} />
      <TextField label="Strona www (opcjonalnie)" inputMode="url" value={website} onChange={setWebsite} error={errors.website} />
      {CREW_CATEGORIES.has(category ?? "") && (
        <TextField
          label="Posiłki dla obsługi (opcjonalnie)"
          description="Ile osób z tej firmy je posiłek na sali — sala zwykle liczy to osobno."
          inputMode="numeric"
          value={crew}
          onChange={setCrew}
          error={errors.crew}
        />
      )}
      <TextField label="Notatki (opcjonalnie)" value={notes} onChange={setNotes} />
      <Button type="submit" block pending={save.isPending}>
        {vendor ? "Zapisz" : "Dodaj usługodawcę"}
      </Button>
    </Form>
  );
}
