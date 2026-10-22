import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarHeart, MapPin } from "lucide-react";
import { useState } from "react";
import { Form } from "react-aria-components";
import { useParams } from "react-router";

import { api, unwrap } from "../../api/client";
import { ApiError, userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { Checkbox, TextAreaField, TextField } from "../../components/Field";
import { Segmented } from "../../components/Segmented";
import { Select } from "../../components/Select";
import { Card, Notice, Skeleton } from "../../components/Surface";
import { downloadIcs } from "../../lib/ics";
import "../auth/auth.css";
import "./rsvp.css";
import { courseLabel, dishTags } from "../../lib/menu";
import { dateIn, LangContext, pickLang, saveLang, savedLang, saveReadable, savedReadable, STRINGS, timeIn, useLang, useT, whenIn, type Lang } from "./i18n";
import { accentStyle } from "./themes";

type View = components["schemas"]["RsvpView"];
type RsvpGuest = components["schemas"]["RsvpGuest"];
type Answer = "attending" | "declined" | "maybe";
type Diet = RsvpGuest["dietary_preference"];
type AgeGroup = RsvpGuest["age_group"];

const ANSWER_KEYS: Answer[] = ["attending", "declined", "maybe"];
const DIET_KEYS: Diet[] = ["standard", "vegetarian", "vegan", "gluten_free", "other"];
const AGE_KEYS: AgeGroup[] = ["adult", "teen", "child", "infant"];

interface Draft {
  answers: Record<string, Answer | undefined>;
  diet: Diet;
  note: string;
  stay: boolean;
  transport: boolean;
  runs: string[];
}

function draftOf(g: RsvpGuest): Draft {
  const answers: Draft["answers"] = {};
  for (const [eventId, status] of Object.entries(g.attendance)) {
    if (status !== "pending") answers[eventId] = status;
  }
  return {
    answers,
    diet: g.dietary_preference,
    note: "",
    stay: g.needs_accommodation,
    transport: g.needs_transport,
    runs: g.transport_run_ids ?? [],
  };
}


/**
 * Odpowiedź gości z linku w zaproszeniu (bez konta i logowania). Token jest tylko w adresie;
 * strona nie wysyła go nigdzie poza naszym API (Referrer-Policy: no-referrer w Caddy).
 */
export function RsvpPage() {
  const { token = "" } = useParams();
  const [chosen, setChosen] = useState<Lang | null>(savedLang);
  const [readable, setReadable] = useState(savedReadable);
  const view = useQuery({
    queryKey: ["rsvp", token],
    queryFn: () =>
      unwrap(api.GET("/api/v1/rsvp/{token}", { params: { path: { token } } })),
    retry: false,
    refetchOnWindowFocus: false,
  });
  const lang = pickLang(chosen, view.data?.language);
  const t = STRINGS[lang];

  return (
    <LangContext.Provider value={lang}>
    <main
      lang={lang}
      className="auth-page rsvp-page guest-themed"
      aria-labelledby="rsvp-h"
      data-guest-theme={view.data?.theme.style ?? "classic"}
      data-readable={readable ? "true" : undefined}
      style={accentStyle(view.data?.theme.accent)}
    >
      <div className="auth-card rsvp-card">
        <p className="auth-brand" aria-hidden="true">
          <svg viewBox="0 0 24 24" className="auth-brand__icon">
            <circle cx="9" cy="12" r="5" />
            <circle cx="15" cy="12" r="5" />
          </svg>
          {t.brand}
        </p>
        <div className="rsvp-lang">
          <Segmented
            label={t.language}
            value={lang}
            options={[
              { value: "pl", label: "Polski" },
              { value: "en", label: "English" },
            ]}
            onChange={(v) => {
              setChosen(v);
              saveLang(v);
            }}
          />
          <Segmented
            label={t.textSize}
            value={readable ? "large" : "normal"}
            options={[
              { value: "normal", label: t.textNormal },
              { value: "large", label: t.textLarge },
            ]}
            onChange={(v) => {
              setReadable(v === "large");
              saveReadable(v === "large");
            }}
          />
        </div>
        {view.isPending && (
          <>
            <h1 id="rsvp-h">{t.invitation}</h1>
            <Skeleton lines={6} />
          </>
        )}
        {view.isError && (
          <>
            <h1 id="rsvp-h">{view.error instanceof ApiError && view.error.status === 404 ? t.linkBroken : t.invitation}</h1>
            <Notice tone="error" live>
              {view.error instanceof ApiError && view.error.status === 404
                ? t.linkExpired
                : view.error instanceof ApiError && view.error.status === 429
                  ? t.tooMany
                  : userMessage(view.error)}
            </Notice>
          </>
        )}
        {view.data && <RsvpForm token={token} view={view.data} />}
      </div>
    </main>
    </LangContext.Provider>
  );
}

/** `preview`: podgląd pary (fikcyjna rodzina) — wszystko widać, nic się nie wysyła. */
export function RsvpForm({ token, view, preview = false }: { token: string; view: View; preview?: boolean }) {
  const queryClient = useQueryClient();
  const t = useT();
  const lang = useLang();
  const [drafts, setDrafts] = useState<Record<string, Draft>>(() =>
    Object.fromEntries(view.guests.map((g) => [g.id, draftOf(g)])),
  );
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const notes = Object.values(drafts).some((d) => d.note.trim());

  // Osoba dopisana w trakcie (osoba towarzysząca) nie ma jeszcze szkicu — powstaje z danych API.
  const draft = (g: RsvpGuest) => drafts[g.id] ?? draftOf(g);
  const update = (g: RsvpGuest, patch: Partial<Draft>) =>
    setDrafts((all) => ({ ...all, [g.id]: { ...(all[g.id] ?? draftOf(g)), ...patch } }));

  const submit = useMutation({
    mutationFn: () =>
      unwrap(
        api.PUT("/api/v1/rsvp/{token}", {
          params: { path: { token } },
          body: {
            responses: view.guests.flatMap((g) =>
              Object.entries(draft(g).answers)
                .filter((e): e is [string, Answer] => !!e[1])
                .map(([event_id, status]) => ({
                  guest_id: g.id,
                  event_id,
                  status,
                })),
            ),
            guests: view.guests.map((g) => {
              const d = draft(g);
              return {
                guest_id: g.id,
                dietary_preference: d.diet,
                // Pustej notatki nie wysyłamy: wcześniej zapisana zostaje bez zmian.
                dietary_note: d.note.trim() || null,
                needs_accommodation: d.stay,
                needs_transport: d.transport || d.runs.length > 0,
                // Kursy wysyłamy tylko, gdy para pokazała je gościom.
                ...(view.transport_runs?.length ? { transport_run_ids: d.runs } : {}),
              };
            }),
            health_data_consent: consent,
          },
        }),
      ),
    onSuccess: (fresh) => {
      setError(null);
      setSent(true);
      queryClient.setQueryData(["rsvp", token], fresh);
      window.scrollTo({ top: 0 });
    },
    onError: (e) => setError(userMessage(e)),
  });

  const answered = view.guests.reduce(
    (n, g) => n + Object.values(draft(g).answers).filter(Boolean).length,
    0,
  );

  if (sent) {
    const coming = view.guests.filter((g) =>
      Object.values(g.attendance).includes("attending"),
    );
    return (
      <>
        <h1 id="rsvp-h">{t.thanks}</h1>
        <Notice tone="success" live>
          {t.delivered} {coming.length > 0 ? t.seeYou(coming.map((g) => g.first_name).join(", ")) : t.sorry}
        </Notice>
        {view.is_open && (
          <Button variant="secondary" onPress={() => setSent(false)}>
            {t.changeAnswer}
          </Button>
        )}
      </>
    );
  }

  return (
    <>
      <div>
        <p className="overline">{view.wedding_name}</p>
        <h1 id="rsvp-h">{view.household_name}</h1>
        <p className="text-secondary">
          {view.rsvp_deadline ? t.deadline(dateIn(lang, view.rsvp_deadline)) : t.noDeadline}
        </p>
      </div>

      {view.events.length === 0 && (
        <Notice tone="info">{t.noEvents}</Notice>
      )}

      {!view.is_open && (
        <Notice tone="warning">{t.closed}</Notice>
      )}

      {view.announcement && (
        <Notice tone="info" title={t.announcement}>
          <span className="prewrap">{view.announcement.text}</span>
        </Notice>
      )}

      {!!view.tables?.length && (
        <Card className="form-stack" aria-labelledby="rsvp-tables-h">
          <h2 id="rsvp-tables-h">{t.tablesTitle}</h2>
          <ul className="rsvp-menu">
            {view.tables.map((s, i) => (
              <li key={i}>
                <strong>{s.first_name}</strong>: {s.table}
                {s.seat_number != null && `, ${t.seat(s.seat_number)}`}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {view.info && <GuestInfo info={view.info} />}
      {!!view.menu?.length && <GuestMenu menu={view.menu} />}

      {view.events.length > 0 && (
        <Card className="form-stack" aria-label={t.events}>
          {view.events.map((e) => (
            <div key={e.id} className="rsvp-event">
              <strong>{e.name}</strong>
              {whenIn(lang, e.starts_at) && (
                <span className="text-secondary rsvp-event__line">
                  <CalendarHeart aria-hidden size={18} /> {whenIn(lang, e.starts_at)}
                </span>
              )}
              {e.address && (
                <span className="text-secondary rsvp-event__line">
                  <MapPin aria-hidden size={18} /> {e.address}
                </span>
              )}
              {e.address && (
                <a
                  className="rsvp-map-link"
                  href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(e.address)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {t.showMap}
                </a>
              )}
              {e.starts_at && (
                <Button
                  variant="text"
                  onPress={() =>
                    downloadIcs(
                      [{ uid: e.id, title: `${e.name} — ${view.wedding_name}`, startsAt: e.starts_at!, endsAt: e.ends_at, location: e.address }],
                      "wesele.ics",
                    )
                  }
                >
                  {t.addToCalendar}
                </Button>
              )}
            </div>
          ))}
        </Card>
      )}

      {view.schedule.length > 0 && (
        <Card className="form-stack" aria-labelledby="rsvp-plan-h">
          <h2 id="rsvp-plan-h">{t.plan}</h2>
          <ul className="rsvp-plan">
            {view.schedule.map((s) => (
              <li key={`${s.title}-${s.starts_at}`}>
                <span className="num">{timeIn(lang, s.starts_at)}</span> {s.title}
                {s.location && <span className="text-secondary"> · {s.location}</span>}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {(view.transport_runs?.length ?? 0) > 0 && (
        <Card className="form-stack" aria-labelledby="rsvp-rides-h">
          <h2 id="rsvp-rides-h">{t.rides}</h2>
          <ul className="rsvp-plan">
            {view.transport_runs!.map((r) => (
              <li key={r.id}>
                {r.departs_at && <span className="num">{timeIn(lang, r.departs_at)} </span>}
                {r.name}
                {(r.from_place || r.to_place) && <span className="text-secondary"> · {[r.from_place, r.to_place].filter(Boolean).join(" → ")}</span>}
              </li>
            ))}
          </ul>
          <p className="text-secondary">{t.ridesHint}</p>
        </Card>
      )}

      {view.events.length > 0 && view.is_open && !preview && <AddCompanion token={token} />}

      {view.events.length > 0 && (
        <Form
          className="form-stack"
          validationBehavior="aria"
          onSubmit={(ev) => {
            ev.preventDefault();
            if (answered === 0) {
              setError(t.pickOne);
              return;
            }
            if (preview) {
              setError(t.previewOnly);
              return;
            }
            if (notes && !consent) {
              setError(t.needConsent);
              return;
            }
            submit.mutate();
          }}
        >
          {view.guests.map((g) => {
            const d = draft(g);
            const coming = Object.values(d.answers).includes("attending");
            return (
              <Card key={g.id} className="form-stack" aria-label={g.first_name}>
                <div className="rsvp-guest-head">
                  <h2 className="rsvp-guest">{g.first_name}</h2>
                  {g.added_via_rsvp && view.is_open && <RemoveCompanion token={token} guest={g} />}
                </div>
                {view.events.map((e) => (
                  <Segmented
                    key={e.id}
                    label={view.events.length > 1 ? e.name : t.willYouCome}
                    value={(d.answers[e.id] ?? "") as Answer}
                    options={ANSWER_KEYS.map((a) => ({ value: a, label: t.answers[a] }))}
                    onChange={(v) =>
                      view.is_open &&
                      update(g, { answers: { ...d.answers, [e.id]: v } })
                    }
                  />
                ))}
                {coming && (
                  <>
                    <Select
                      label={t.diet}
                      options={DIET_KEYS.map((k) => ({ id: k, label: t.diets[k] }))}
                      value={d.diet}
                      onChange={(v) => update(g, { diet: v as Diet })}
                    />
                    {(d.diet !== "standard" || d.note) && (
                      <TextField
                        label={t.kitchenNotes}
                        description={g.has_dietary_note ? t.notesKnown : t.notesHint}
                        value={d.note}
                        onChange={(v) => update(g, { note: v })}
                        maxLength={300}
                        autoComplete="off"
                      />
                    )}
                    <Checkbox
                      isSelected={d.stay}
                      onChange={(v) => update(g, { stay: v })}
                    >
                      {t.needStay}
                    </Checkbox>
                    <Checkbox
                      isSelected={d.transport}
                      onChange={(v) => update(g, { transport: v })}
                    >
                      {t.needTransport}
                    </Checkbox>
                    {(view.transport_runs?.length ?? 0) > 0 && (d.transport || d.runs.length > 0) && (
                      <fieldset className="plain-fieldset form-stack rsvp-runs">
                        <legend className="wp-field__label">{t.runs}</legend>
                        <p className="text-secondary">{t.runsHint}</p>
                        {view.transport_runs!.map((r) => {
                          const on = d.runs.includes(r.id);
                          const when = r.departs_at ? `${dateIn(lang, r.departs_at.slice(0, 10))}, ${timeIn(lang, r.departs_at)}` : null;
                          return (
                            <Checkbox
                              key={r.id}
                              isSelected={on}
                              isDisabled={!on && r.free === 0}
                              onChange={(v) => update(g, { runs: v ? [...d.runs, r.id] : d.runs.filter((x) => x !== r.id) })}
                            >
                              {[r.name, when, [r.from_place, r.to_place].filter(Boolean).join(" → ")].filter(Boolean).join(" · ")}{" "}
                              <span className="text-secondary">({t.seatsLeft(r.free)})</span>
                            </Checkbox>
                          );
                        })}
                      </fieldset>
                    )}
                  </>
                )}
              </Card>
            );
          })}

          {notes && (
            <Checkbox isSelected={consent} onChange={setConsent}>
              {t.consent}
            </Checkbox>
          )}
          {error && (
            <Notice tone="error" live>
              {error}
            </Notice>
          )}
          {view.is_open && (
            <Button type="submit" block pending={submit.isPending}>
              {t.send(answered)}
            </Button>
          )}
        </Form>
      )}
      {view.songs?.enabled && view.is_open && <SongSuggest token={token} songs={view.songs} preview={preview} />}
      {!!view.gifts?.length && <Gifts token={token} gifts={view.gifts} preview={preview} />}
      {view.wishes && <Wishes token={token} wishes={view.wishes} preview={preview} />}
      <p className="text-secondary rsvp-privacy">{t.privacy || view.privacy_note}</p>
    </>
  );
}

/** Lista prezentów: gość rezerwuje pomysł pary (inni widzą tylko „zarezerwowany”). */
function Gifts({ token, gifts, preview }: { token: string; gifts: NonNullable<View["gifts"]>; preview: boolean }) {
  const queryClient = useQueryClient();
  const t = useT();
  const toggle = useMutation({
    mutationFn: ({ id, reserved }: { id: string; reserved: boolean }) =>
      unwrap(api.PUT("/api/v1/rsvp/{token}/gifts/{gift_id}", { params: { path: { token, gift_id: id } }, body: { reserved } })),
    onSuccess: (fresh) => queryClient.setQueryData(["rsvp", token], fresh),
    onError: () => queryClient.invalidateQueries({ queryKey: ["rsvp", token] }),
  });
  return (
    <Card className="form-stack" aria-labelledby="rsvp-gifts-h">
      <h2 id="rsvp-gifts-h">{t.giftsTitle}</h2>
      <p className="text-secondary">{t.giftsHint}</p>
      {toggle.isError && (
        <Notice tone="error" live>
          {userMessage(toggle.error)}
        </Notice>
      )}
      <ul className="row-list">
        {gifts.map((g) => (
          <li key={g.id} className="row rsvp-gift">
            <span className="row__body">
              <span className={g.reserved && !g.mine ? "done-title" : "row__title"}>{g.title}</span>
              {g.kind === "fund" && <span className="text-secondary">{t.giftFund}</span>}
              {g.link && (
                <a href={g.link} target="_blank" rel="noopener noreferrer" className="text-secondary">
                  {t.giftShop}
                </a>
              )}
            </span>
            {g.kind === "item" &&
              (g.mine ? (
                <Button variant="text" isDisabled={preview} pending={toggle.isPending && toggle.variables?.id === g.id} onPress={() => toggle.mutate({ id: g.id, reserved: false })}>
                  {t.giftRelease}
                </Button>
              ) : g.reserved ? (
                <span className="text-secondary">{t.giftReserved}</span>
              ) : (
                <Button variant="secondary" isDisabled={preview} pending={toggle.isPending && toggle.variables?.id === g.id} onPress={() => toggle.mutate({ id: g.id, reserved: true })}>
                  {t.giftReserve}
                </Button>
              ))}
            {g.mine && <span className="visually-hidden">{t.giftMine}</span>}
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** Księga życzeń: gość zostawia kilka słów dla pary (do limitu wpisów na zaproszenie). */
function Wishes({ token, wishes, preview }: { token: string; wishes: NonNullable<View["wishes"]>; preview: boolean }) {
  const queryClient = useQueryClient();
  const t = useT();
  const [author, setAuthor] = useState("");
  const [text, setText] = useState("");
  const [sent, setSent] = useState(false);
  const add = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/rsvp/{token}/wishes", { params: { path: { token } }, body: { author: author.trim(), text: text.trim() } })),
    onSuccess: (fresh) => {
      queryClient.setQueryData(["rsvp", token], fresh);
      setText("");
      setSent(true);
    },
  });
  const full = wishes.mine.length >= wishes.limit;
  return (
    <Card className="form-stack" aria-labelledby="rsvp-wishes-h">
      <h2 id="rsvp-wishes-h">{t.wishesTitle}</h2>
      <p className="text-secondary">{t.wishesHint}</p>
      {wishes.mine.length > 0 && (
        <div>
          <h3 className="card-title">{t.wishesMine}</h3>
          <ul className="rsvp-menu">
            {wishes.mine.map((w, i) => (
              <li key={i}>
                <span className="prewrap">{w.text}</span> <span className="text-secondary">— {w.author}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {sent && (
        <Notice tone="success" live>
          {t.wishThanks}
        </Notice>
      )}
      {full ? (
        <p className="text-secondary">{t.wishesFull}</p>
      ) : (
        <Form
          className="form-stack"
          validationBehavior="aria"
          onSubmit={(ev) => {
            ev.preventDefault();
            if (author.trim() && text.trim() && !preview) add.mutate();
          }}
        >
          <TextAreaField label={t.wishText} isRequired value={text} onChange={setText} maxLength={1000} rows={4} />
          <TextField label={t.wishAuthor} isRequired value={author} onChange={setAuthor} maxLength={120} autoComplete="off" />
          {add.isError && (
            <Notice tone="error" live>
              {userMessage(add.error)}
            </Notice>
          )}
          <Button type="submit" variant="secondary" pending={add.isPending} isDisabled={preview || !author.trim() || !text.trim()}>
            {t.wishSend}
          </Button>
        </Form>
      )}
    </Card>
  );
}

/** Gość proponuje utwór dla DJ-a (para zatwierdza); widzi tylko swoje propozycje. */
function SongSuggest({ token, songs, preview }: { token: string; songs: NonNullable<View["songs"]>; preview: boolean }) {
  const queryClient = useQueryClient();
  const t = useT();
  const [title, setTitle] = useState("");
  const [artist, setArtist] = useState("");
  const [sent, setSent] = useState(false);
  const add = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/v1/rsvp/{token}/songs", { params: { path: { token } }, body: { title: title.trim(), artist: artist.trim() || null } })),
    onSuccess: (fresh) => {
      queryClient.setQueryData(["rsvp", token], fresh);
      setTitle("");
      setArtist("");
      setSent(true);
    },
  });
  const full = songs.mine.length >= songs.limit;
  return (
    <Card className="form-stack" aria-labelledby="rsvp-songs-h">
      <h2 id="rsvp-songs-h">{t.songsTitle}</h2>
      <p className="text-secondary">{t.songsHint(songs.limit)}</p>
      {songs.mine.length > 0 && (
        <div>
          <h3 className="card-title">{t.songsMine}</h3>
          <ul>
            {songs.mine.map((s, i) => (
              <li key={i}>{s.artist ? `${s.title} — ${s.artist}` : s.title}</li>
            ))}
          </ul>
        </div>
      )}
      {sent && (
        <Notice tone="success" live>
          {t.songThanks}
        </Notice>
      )}
      {full ? (
        <p className="text-secondary">{t.songsFull}</p>
      ) : (
        <Form
          className="form-stack"
          validationBehavior="aria"
          onSubmit={(ev) => {
            ev.preventDefault();
            if (title.trim() && !preview) add.mutate();
          }}
        >
          <TextField label={t.songTitle} isRequired value={title} onChange={setTitle} maxLength={200} autoComplete="off" />
          <TextField label={t.songArtist} value={artist} onChange={setArtist} maxLength={120} autoComplete="off" />
          {add.isError && (
            <Notice tone="error" live>
              {userMessage(add.error)}
            </Notice>
          )}
          <Button type="submit" variant="secondary" pending={add.isPending} isDisabled={preview || !title.trim()}>
            {t.songSend}
          </Button>
        </Form>
      )}
    </Card>
  );
}

/** Menu na stronie gościa: dania z oznaczeniem diet i alergenów. */
function GuestMenu({ menu }: { menu: NonNullable<View["menu"]> }) {
  const t = useT();
  const lang = useLang();
  const courses = [...new Set(menu.map((d) => d.course))];
  return (
    <Card className="form-stack" aria-labelledby="rsvp-menu-h">
      <h2 id="rsvp-menu-h">{t.menuTitle}</h2>
      {courses.map((c) => (
        <div key={c}>
          <h3 className="card-title">{courseLabel(c, lang)}</h3>
          <ul className="rsvp-menu">
            {menu
              .filter((d) => d.course === c)
              .map((d, i) => (
                <li key={i}>
                  <strong>{d.name}</strong>
                  {d.description && <span className="text-secondary"> — {d.description}</span>}
                  {dishTags(d, lang).length > 0 && <span className="text-secondary"> ({dishTags(d, lang).join(" · ")})</span>}
                </li>
              ))}
          </ul>
        </div>
      ))}
      <p className="text-secondary">{t.menuNote}</p>
    </Card>
  );
}

const INFO_KEYS = ["directions", "accommodation", "transport", "dress_code", "gifts", "contact"] as const;

/** Informacje od pary (strona dla gości). */
function GuestInfo({ info }: { info: NonNullable<View["info"]> }) {
  const t = useT();
  return (
    <Card className="form-stack" aria-label={t.info}>
      {info.welcome && <p className="prewrap">{info.welcome}</p>}
      <dl className="rsvp-info">
        {INFO_KEYS.filter((key) => info[key]).map((key) => (
          <div key={key}>
            <dt>{t.infoLabels[key]}</dt>
            <dd className="prewrap">{info[key]}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

/** Gość dopisuje osobę towarzyszącą; potem odpowiada za nią w tym samym formularzu. */
function AddCompanion({ token }: { token: string }) {
  const queryClient = useQueryClient();
  const t = useT();
  const [open, setOpen] = useState(false);
  const [first, setFirst] = useState("");
  const [last, setLast] = useState("");
  const [age, setAge] = useState<AgeGroup>("adult");
  const add = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/rsvp/{token}/companions", {
          params: { path: { token } },
          body: { first_name: first.trim(), last_name: last.trim() || null, age_group: age },
        }),
      ),
    onSuccess: (fresh) => {
      queryClient.setQueryData(["rsvp", token], fresh);
      setFirst("");
      setLast("");
      setAge("adult");
      setOpen(false);
    },
  });

  if (!open) {
    return (
      <Button variant="secondary" onPress={() => setOpen(true)}>
        {t.addCompanion}
      </Button>
    );
  }
  return (
    <Card className="form-stack" aria-labelledby="rsvp-companion-h">
      <h2 id="rsvp-companion-h">{t.companion}</h2>
      <Form
        className="form-stack"
        validationBehavior="aria"
        onSubmit={(ev) => {
          ev.preventDefault();
          if (first.trim()) add.mutate();
        }}
      >
        <TextField label={t.firstName} isRequired value={first} onChange={setFirst} maxLength={80} autoComplete="off" />
        <TextField label={t.lastName} value={last} onChange={setLast} maxLength={80} autoComplete="off" />
        <Select label={t.age} options={AGE_KEYS.map((k) => ({ id: k, label: t.ages[k] }))} value={age} onChange={(v) => setAge(v as AgeGroup)} />
        <p className="text-secondary">{t.companionHint}</p>
        {add.isError && (
          <Notice tone="error" live>
            {userMessage(add.error)}
          </Notice>
        )}
        <div className="rsvp-actions">
          <Button type="submit" pending={add.isPending}>
            {t.add}
          </Button>
          <Button variant="text" onPress={() => setOpen(false)}>
            {t.cancel}
          </Button>
        </div>
      </Form>
    </Card>
  );
}

function RemoveCompanion({ token, guest }: { token: string; guest: RsvpGuest }) {
  const queryClient = useQueryClient();
  const t = useT();
  const remove = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE("/api/v1/rsvp/{token}/companions/{guest_id}", {
          params: { path: { token, guest_id: guest.id } },
        }),
      ),
    onSuccess: (fresh) => queryClient.setQueryData(["rsvp", token], fresh),
  });
  return (
    <Button variant="text" pending={remove.isPending} onPress={() => remove.mutate()} aria-label={t.removeLabel(guest.first_name)}>
      {t.remove}
    </Button>
  );
}
