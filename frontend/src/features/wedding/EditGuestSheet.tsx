import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Form } from "react-aria-components";
import { useNavigate } from "react-router";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { Checkbox, TextField } from "../../components/Field";
import { ConfirmDialog, Sheet } from "../../components/Overlay";
import { PremiumBadge } from "../../components/Premium";
import { Select } from "../../components/Select";
import { Notice } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { plural } from "../../lib/format";
import { keys, type Guest, type Household } from "./data";
import { ifMatch, saveErrorMessage } from "./mutations";
import { GuestLogistics } from "./GuestLogistics";

type GuestPatch = components["schemas"]["GuestUpdate"];
type HouseholdPatch = components["schemas"]["HouseholdUpdate"];

export const AGE_GROUPS = [
  { id: "adult", label: "Dorosły" },
  { id: "teen", label: "Nastolatek (13–17)" },
  { id: "child", label: "Dziecko (4–12)" },
  { id: "infant", label: "Maluch (0–3)" },
];

export const DIETS = [
  { id: "standard", label: "Bez wymagań" },
  { id: "vegetarian", label: "Wegetariańska" },
  { id: "vegan", label: "Wegańska" },
  { id: "gluten_free", label: "Bezglutenowa" },
  { id: "other", label: "Inna (opisz)" },
];

export const SIDES = [
  { id: "both", label: "Wspólni" },
  { id: "bride", label: "Strona Panny Młodej" },
  { id: "groom", label: "Strona Pana Młodego" },
  { id: "other", label: "Inni" },
];

export const DELIVERY = [
  { id: "none", label: "Jeszcze nie wiemy" },
  { id: "in_person", label: "Osobiście" },
  { id: "post", label: "Pocztą" },
  { id: "online", label: "E-mailem lub linkiem" },
  { id: "other", label: "Inaczej" },
];

const INVITATION = [
  { id: "not_sent", label: "Jeszcze nie wysłane" },
  { id: "sent", label: "Wysłane" },
  { id: "delivered", label: "Doręczone" },
];

export function fullName(g: Pick<Guest, "first_name" | "last_name">): string {
  return `${g.first_name} ${g.last_name ?? ""}`.trim();
}

function useRefreshGuests(weddingId: string) {
  const queryClient = useQueryClient();
  return () =>
    Promise.all(
      [keys.households(weddingId), keys.guestStats(weddingId), keys.summary(weddingId)].map((queryKey) =>
        queryClient.invalidateQueries({ queryKey }),
      ),
    );
}

/* ----------------------------------------------------------------------------- gość */

export function EditGuestSheet({
  weddingId,
  guest,
  household,
  onClose,
}: {
  weddingId: string;
  guest: Guest | null;
  household: Household | undefined;
  onClose: () => void;
}) {
  return (
    <Sheet title="Gość" isOpen={!!guest} onOpenChange={(o) => !o && onClose()}>
      {guest && (
        <EditGuestForm key={`${guest.id}-${guest.version}`} weddingId={weddingId} guest={guest} household={household} onClose={onClose} />
      )}
    </Sheet>
  );
}

function EditGuestForm({
  weddingId,
  guest,
  household,
  onClose,
}: {
  weddingId: string;
  guest: Guest;
  household: Household | undefined;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const refresh = useRefreshGuests(weddingId);
  const toast = useToast();
  const [first, setFirst] = useState(guest.first_name);
  const [last, setLast] = useState(guest.last_name ?? "");
  const [age, setAge] = useState<string>(guest.age_group);
  const [diet, setDiet] = useState<string>(guest.dietary_preference);
  const [dietNote, setDietNote] = useState(guest.dietary_note ?? "");
  const [stay, setStay] = useState(guest.needs_accommodation);
  const [transport, setTransport] = useState(guest.needs_transport);
  const [firstError, setFirstError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const others = (household?.guests.length ?? 1) - 1;
  const name = fullName(guest);

  const save = useMutation({
    mutationFn: (body: Partial<GuestPatch>) =>
      unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/guests/{guest_id}", {
          params: { path: { wedding_id: weddingId, guest_id: guest.id } },
          body,
          headers: ifMatch(guest.version),
        }),
      ),
    onSuccess: async () => {
      await refresh();
      onClose();
      toast("Zapisano gościa");
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [keys.households(weddingId)])),
  });

  const remove = useMutation({
    mutationFn: async (scope: "guest" | "household") => {
      if (scope === "household" && household) {
        await unwrap(
          api.DELETE("/api/v1/weddings/{wedding_id}/households/{household_id}", {
            params: { path: { wedding_id: weddingId, household_id: household.id } },
          }),
        );
      } else {
        await unwrap(
          api.DELETE("/api/v1/weddings/{wedding_id}/guests/{guest_id}", {
            params: { path: { wedding_id: weddingId, guest_id: guest.id } },
          }),
        );
      }
      return scope;
    },
    onSuccess: async (scope) => {
      setConfirmDelete(false);
      await refresh();
      onClose();
      toast(scope === "household" && household ? `Usunięto zaproszenie „${household.name}”` : `Usunięto: ${name}`);
    },
    onError: (e) => {
      setConfirmDelete(false);
      setError(`Nie usunięto. ${userMessage(e)}`);
    },
  });

  const changes = (): Partial<GuestPatch> => {
    const body: Partial<GuestPatch> = {};
    if (first.trim() !== guest.first_name) body.first_name = first.trim();
    if ((last.trim() || null) !== guest.last_name) body.last_name = last.trim() || null;
    if (age !== guest.age_group) body.age_group = age as GuestPatch["age_group"];
    if (diet !== guest.dietary_preference) body.dietary_preference = diet as GuestPatch["dietary_preference"];
    if ((dietNote.trim() || null) !== guest.dietary_note) body.dietary_note = dietNote.trim() || null;
    if (stay !== guest.needs_accommodation) body.needs_accommodation = stay;
    if (transport !== guest.needs_transport) body.needs_transport = transport;
    return body;
  };

  return (
    <>
      <Form
        className="form-stack"
        validationBehavior="aria"
        onSubmit={(e) => {
          e.preventDefault();
          if (!first.trim()) {
            setFirstError("Wpisz imię.");
            return;
          }
          setFirstError(null);
          const body = changes();
          if (Object.keys(body).length === 0) return onClose();
          save.mutate(body);
        }}
      >
        {error && (
          <Notice tone="error" live>
            {error}
          </Notice>
        )}
        <TextField label="Imię" value={first} onChange={setFirst} error={firstError} isRequired autoComplete="off" />
        <TextField label="Nazwisko (opcjonalnie)" value={last} onChange={setLast} autoComplete="off" />
        <Select label="Wiek" options={AGE_GROUPS} value={age} onChange={setAge} />
        <Select label="Dieta" options={DIETS} value={diet} onChange={setDiet} />
        {(diet !== "standard" || dietNote) && (
          <TextField
            label="Uwagi dla kuchni (opcjonalnie)"
            description="Mogą dotyczyć zdrowia (np. alergii). Wpiszcie tylko to, co potrzebne kuchni — dane są szyfrowane i usuwane po weselu."
            value={dietNote}
            onChange={setDietNote}
            autoComplete="off"
          />
        )}
        <Checkbox isSelected={stay} onChange={setStay}>
          Potrzebuje noclegu
        </Checkbox>
        <Checkbox isSelected={transport} onChange={setTransport}>
          Potrzebuje transportu
        </Checkbox>
        <GuestLogistics weddingId={weddingId} guestId={guest.id} />
        <Button type="submit" block pending={save.isPending}>
          Zapisz
        </Button>
        <Button variant="text" onPress={() => setConfirmDelete(true)}>
          Usuń osobę
        </Button>
      </Form>
      <ConfirmDialog title={others > 0 ? "Kogo usunąć?" : "Usunąć zaproszenie?"} isOpen={confirmDelete} onOpenChange={setConfirmDelete}>
        {others > 0 ? (
          <p>
            Usunąć tylko: {name}, czy całe zaproszenie „{household?.name}” (
            {plural(others + 1, { one: "# osoba", few: "# osoby", many: "# osób", other: "# osoby" })})? Odpowiedzi i miejsca przy stołach
            usuniętych osób też znikną.
          </p>
        ) : (
          <p>
            {name} to jedyna osoba w zaproszeniu „{household?.name}”. Usuniemy całe zaproszenie razem z odpowiedziami i miejscem przy stole.
          </p>
        )}
        <div className="wp-sheet__actions wp-sheet__actions--stack">
          <Button variant="secondary" onPress={() => setConfirmDelete(false)}>
            Anuluj
          </Button>
          {others > 0 && (
            <Button variant="danger" pending={remove.isPending && remove.variables === "guest"} onPress={() => remove.mutate("guest")}>
              Usuń tylko: {guest.first_name}
            </Button>
          )}
          <Button
            variant="danger"
            pending={remove.isPending && remove.variables === "household"}
            onPress={() => remove.mutate(household ? "household" : "guest")}
          >
            Usuń całe zaproszenie
          </Button>
        </div>
      </ConfirmDialog>
    </>
  );
}

/* ----------------------------------------------------------------------- zaproszenie */

export function EditHouseholdSheet({ weddingId, household, onClose }: { weddingId: string; household: Household | null; onClose: () => void }) {
  // Świeżo utworzony link trzymamy nad formularzem: utworzenie linku zmienia wersję zaproszenia,
  // a formularz jest wtedy montowany od nowa.
  const [link, setLink] = useState<{ householdId: string; url: string } | null>(null);
  const close = () => {
    setLink(null);
    onClose();
  };
  return (
    <Sheet title="Zaproszenie" isOpen={!!household} onOpenChange={(o) => !o && close()}>
      {household && (
        <EditHouseholdForm
          key={`${household.id}-${household.version}`}
          weddingId={weddingId}
          household={household}
          onClose={close}
          link={link?.householdId === household.id ? link.url : null}
          setLink={(url) => setLink(url ? { householdId: household.id, url } : null)}
        />
      )}
    </Sheet>
  );
}

function EditHouseholdForm({
  weddingId,
  household: h,
  onClose,
  link,
  setLink,
}: {
  weddingId: string;
  household: Household;
  onClose: () => void;
  link: string | null;
  setLink: (url: string | null) => void;
}) {
  const queryClient = useQueryClient();
  const refresh = useRefreshGuests(weddingId);
  const toast = useToast();
  const [name, setName] = useState(h.name);
  const [side, setSide] = useState<string>(h.side);
  const [invitation, setInvitation] = useState<string>(h.invitation_status);
  const [language, setLanguage] = useState<string>(h.language ?? "auto");
  const [email, setEmail] = useState(h.contact_email ?? "");
  const [phone, setPhone] = useState(h.contact_phone ?? "");
  const [gift, setGift] = useState(h.gift_note ?? "");
  const [thanked, setThanked] = useState(h.thanked);
  const [delivery, setDelivery] = useState<string>(h.delivery_method ?? "none");
  const [place, setPlace] = useState(h.delivery_place ?? "");
  const [deliveryBy, setDeliveryBy] = useState(h.delivery_by ?? "");
  const [person, setPerson] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const addKey = useRef(newIdempotencyKey());

  const save = useMutation({
    mutationFn: (body: Partial<HouseholdPatch>) =>
      unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/households/{household_id}", {
          params: { path: { wedding_id: weddingId, household_id: h.id } },
          body,
          headers: ifMatch(h.version),
        }),
      ),
    onSuccess: async () => {
      await refresh();
      onClose();
      toast("Zapisano zaproszenie");
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [keys.households(weddingId)])),
  });

  const add = useMutation({
    mutationFn: (full: string) => {
      const [first, ...rest] = full.split(/\s+/);
      return unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/households/{household_id}/guests", {
          params: { path: { wedding_id: weddingId, household_id: h.id } },
          body: {
            first_name: first ?? full,
            last_name: rest.join(" ") || null,
            age_group: "adult",
            is_plus_one: false,
            dietary_preference: "standard",
            needs_accommodation: false,
            needs_transport: false,
          },
          headers: { "Idempotency-Key": addKey.current },
        }),
      );
    },
    onSuccess: async (g) => {
      addKey.current = newIdempotencyKey();
      setPerson("");
      setError(null);
      await refresh();
      toast(`Dodano: ${fullName(g)}`);
    },
    onError: (e) => setError(`Nie dodano osoby. ${userMessage(e)}`),
  });

  const remove = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE("/api/v1/weddings/{wedding_id}/households/{household_id}", {
          params: { path: { wedding_id: weddingId, household_id: h.id } },
        }),
      ),
    onSuccess: async () => {
      setConfirmDelete(false);
      await refresh();
      onClose();
      toast(`Usunięto zaproszenie „${h.name}”`);
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
          if (!name.trim()) {
            setNameError("Wpisz nazwę zaproszenia.");
            return;
          }
          setNameError(null);
          const body: Partial<HouseholdPatch> = {};
          if (name.trim() !== h.name) body.name = name.trim();
          if (side !== h.side) body.side = side as HouseholdPatch["side"];
          if (invitation !== h.invitation_status) body.invitation_status = invitation as HouseholdPatch["invitation_status"];
          if (language !== (h.language ?? "auto")) body.language = language === "auto" ? null : (language as "pl" | "en");
          if ((email.trim() || null) !== h.contact_email) body.contact_email = email.trim() || null;
          if ((phone.trim() || null) !== h.contact_phone) body.contact_phone = phone.trim() || null;
          if ((gift.trim() || null) !== h.gift_note) body.gift_note = gift.trim() || null;
          if (thanked !== h.thanked) body.thanked = thanked;
          const method = delivery === "none" ? null : (delivery as NonNullable<HouseholdPatch["delivery_method"]>);
          if (method !== (h.delivery_method ?? null)) body.delivery_method = method;
          if ((place.trim() || null) !== (h.delivery_place ?? null)) body.delivery_place = place.trim() || null;
          if ((deliveryBy.trim() || null) !== (h.delivery_by ?? null)) body.delivery_by = deliveryBy.trim() || null;
          if (Object.keys(body).length === 0) return onClose();
          save.mutate(body);
        }}
      >
        {error && (
          <Notice tone="error" live>
            {error}
          </Notice>
        )}
        <TextField label="Nazwa zaproszenia" value={name} onChange={setName} error={nameError} isRequired />
        <Select label="Strona" options={SIDES} value={side} onChange={setSide} />
        <Select label="Zaproszenie papierowe" options={INVITATION} value={invitation} onChange={setInvitation} />
        <Select label="Jak wręczamy zaproszenie" options={DELIVERY} value={delivery} onChange={setDelivery} />
        {delivery === "in_person" && (
          <>
            <TextField
              label="Miejscowość (do planu objazdów)"
              description="Wystarczy miejscowość — bez adresu."
              value={place}
              onChange={setPlace}
              maxLength={120}
              autoComplete="off"
            />
            <TextField label="Kto wręcza (opcjonalnie)" value={deliveryBy} onChange={setDeliveryBy} maxLength={80} autoComplete="off" />
          </>
        )}
        <Select
          label="Język zaproszenia"
          description="W tym języku wyślemy e-mail z linkiem i otworzymy stronę dla gości (gość może go zmienić). Automatycznie: e-mail po polsku, strona wg przeglądarki."
          options={[
            { id: "auto", label: "Automatycznie (wg przeglądarki gościa)" },
            { id: "pl", label: "Polski" },
            { id: "en", label: "Angielski (English)" },
          ]}
          value={language}
          onChange={setLanguage}
        />
        <TextField
          label="E-mail do potwierdzeń (opcjonalnie)"
          description="Na ten adres możecie wysłać link do potwierdzenia obecności."
          type="email"
          inputMode="email"
          value={email}
          onChange={setEmail}
        />
        <TextField label="Telefon (opcjonalnie)" type="tel" inputMode="tel" value={phone} onChange={setPhone} />
        <fieldset className="plain-fieldset form-stack">
          <legend className="wp-field__label">Po weselu</legend>
          <TextField label="Prezent (opcjonalnie)" description="Np. koperta, ekspres do kawy — ułatwi podziękowania." value={gift} onChange={setGift} maxLength={300} />
          <Checkbox isSelected={thanked} onChange={setThanked}>
            Podziękowanie wysłane
          </Checkbox>
        </fieldset>
        <Button type="submit" block pending={save.isPending}>
          Zapisz
        </Button>
      </Form>

      <Form
        className="form-stack add-person"
        validationBehavior="aria"
        onSubmit={(e) => {
          e.preventDefault();
          if (person.trim()) add.mutate(person.trim());
        }}
      >
        <TextField
          label="Dodaj osobę do zaproszenia"
          description="Imię i nazwisko, np. Zosia Kowalska."
          value={person}
          onChange={setPerson}
          autoComplete="off"
        />
        <Button type="submit" variant="secondary" pending={add.isPending} isDisabled={!person.trim()}>
          Dodaj osobę
        </Button>
      </Form>

      <RsvpLinkSection weddingId={weddingId} household={h} url={link} setUrl={setLink} />

      <Button variant="text" onPress={() => setConfirmDelete(true)}>
        Usuń zaproszenie
      </Button>
      <ConfirmDialog title="Usunąć zaproszenie?" isOpen={confirmDelete} onOpenChange={setConfirmDelete}>
        <p>
          „{h.name}” zniknie z listy razem z{" "}
          {plural(h.guests.length, { one: "# osobą", few: "# osobami", many: "# osobami", other: "# osoby" })}, ich odpowiedziami i
          miejscami przy stołach.
        </p>
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

/* --------------------------------------------------------------- link do odpowiedzi */

/**
 * Link RSVP dla rodziny. Serwer trzyma tylko skrót tokenu, więc link widać raz — zaraz po
 * utworzeniu. Nowy link unieważnia poprzedni.
 */
function RsvpLinkSection({
  weddingId,
  household: h,
  url,
  setUrl,
}: {
  weddingId: string;
  household: Household;
  url: string | null;
  setUrl: (url: string | null) => void;
}) {
  const refresh = useRefreshGuests(weddingId);
  const toast = useToast();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  // Kod QR (adres z tokenem) — jak link: widoczny tylko zaraz po utworzeniu.
  const [qr, setQr] = useState<{ svg: string; url: string } | null>(null);

  const create = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/households/{household_id}/rsvp-link", {
          params: { path: { wedding_id: weddingId, household_id: h.id } },
        }),
      ),
    onSuccess: async (link) => {
      setError(null);
      // Adres budujemy z bieżącego originu aplikacji (ten sam host co GUI).
      setUrl(`${location.origin}/rsvp/${link.token}`);
      setQr({ svg: link.qr_svg, url: link.url });
      await refresh();
    },
    onError: (e) => setError(`Nie utworzono linku. ${userMessage(e)}`),
  });

  const revoke = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE("/api/v1/weddings/{wedding_id}/households/{household_id}/rsvp-link", {
          params: { path: { wedding_id: weddingId, household_id: h.id } },
        }),
      ),
    onSuccess: async () => {
      setUrl(null);
      setQr(null);
      await refresh();
      toast("Link wyłączony");
    },
    onError: (e) => setError(`Nie wyłączono linku. ${userMessage(e)}`),
  });

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url!);
      toast("Skopiowano link");
    } catch {
      setError("Nie udało się skopiować. Zaznacz link i skopiuj ręcznie.");
    }
  };

  return (
    <section className="form-stack rsvp-link" aria-labelledby={`rsvp-link-${h.id}`}>
      <h3 id={`rsvp-link-${h.id}`}>Link do odpowiedzi</h3>
      <p className="text-secondary">
        Goście odpowiadają bez zakładania konta. Wyślijcie link SMS-em lub komunikatorem tylko tej rodzinie.
      </p>
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      {url ? (
        <>
          <TextField label="Link (widoczny tylko teraz)" value={url} isReadOnly />
          <div className="wp-sheet__actions">
            <Button variant="secondary" onPress={() => void copy()}>
              Kopiuj link
            </Button>
            {typeof navigator.share === "function" && (
              <Button
                variant="secondary"
                onPress={() => void navigator.share({ title: "Zaproszenie na wesele", url }).catch(() => undefined)}
              >
                Udostępnij
              </Button>
            )}
          </div>
          {qr && (
            <div className="form-stack qr-block">
              <img className="qr-image" src={svgDataUri(qr.svg)} alt={`Kod QR z linkiem do odpowiedzi dla: ${h.name}`} width={160} height={160} />
              <p className="text-secondary">
                Kod QR do wydrukowania na zaproszeniu <PremiumBadge />
              </p>
              <div className="wp-sheet__actions">
                <Button variant="secondary" onPress={() => downloadSvg(qr.svg, `kod-qr-${slug(h.name)}.svg`)}>
                  Pobierz kod QR (SVG)
                </Button>
                <Button
                  variant="secondary"
                  onPress={() =>
                    navigate(`/w/${weddingId}/druk/qr`, {
                      state: { cards: [{ household_id: h.id, name: h.name, rsvp_deadline: h.rsvp_deadline, url: qr.url, qr_svg: qr.svg, has_active_link: true }] },
                    })
                  }
                >
                  Drukuj kartę z kodem
                </Button>
              </div>
            </div>
          )}
        </>
      ) : (
        <>
          {h.rsvp_link_active && (
            <p className="text-secondary">Link jest aktywny. Ze względów bezpieczeństwa nie pokazujemy go ponownie.</p>
          )}
          <Button variant="secondary" pending={create.isPending} onPress={() => create.mutate()}>
            {h.rsvp_link_active ? "Utwórz nowy link (stary przestanie działać)" : "Utwórz link"}
          </Button>
        </>
      )}
      {(h.rsvp_link_active || url) && (
        <Button variant="text" pending={revoke.isPending} onPress={() => revoke.mutate()}>
          Wyłącz link
        </Button>
      )}
    </section>
  );
}

/** SVG z serwera (segno) jako obraz — bez wstawiania znaczników do strony. */
export const svgDataUri = (svg: string) => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;

function downloadSvg(svg: string, filename: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

const slug = (name: string) =>
  name
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ł/gi, "l")
    .replace(/[^a-z0-9]+/gi, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase() || "zaproszenie";
