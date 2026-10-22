/** Program dnia dla usługodawcy: link bez logowania, odświeżany co minutę (przesunięcia na żywo). */
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { MapPin, Printer } from "lucide-react";
import { useParams } from "react-router";

import { api, unwrap } from "../../api/client";
import { ApiError, userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { BriefView } from "../../components/BriefView";
import { Button } from "../../components/Button";
import { OfflineDay } from "../../components/OfflineDay";
import { Card, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { publicCopyKey, readDayCopy, removeDayCopy, saveDayCopy } from "../../lib/dayCopy";
import { downloadIcs } from "../../lib/ics";
import { byMoment, songLabel } from "../../lib/music";
import { briefLabels } from "../../lib/vendorBrief";
import { eventWhen, formatDate, formatTime, plural, todayInWarsaw } from "../../lib/format";
import "../auth/auth.css";
import "./rsvp.css";

export function DayPage() {
  const { token = "" } = useParams();
  const day = useQuery({
    queryKey: ["public-day", token],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/day/{token}", { params: { path: { token } }, signal })),
    refetchInterval: 60_000,
    retry: false,
  });
  const d = day.data;
  const key = publicCopyKey(token);
  const gone = day.error instanceof ApiError && day.error.status === 404;
  // Kopia programu na tym urządzeniu (bez danych gości): na wypadek braku zasięgu na sali.
  useEffect(() => {
    if (d) {
      saveDayCopy(key, {
        name: d.wedding_name,
        wedding_date: d.wedding_date,
        items: d.items.map((i, n) => ({ ...i, id: String(n), vendor_name: i.mine ? d.vendor_name : null, plan_b: i.plan_b, preparations: i.preparations })),
      });
    }
    if (gone) removeDayCopy(key); // link wyłączony: kopia też znika
  }, [d, gone, key]);
  const copy = day.isError && !gone ? readDayCopy(key, todayInWarsaw()) : null;
  return (
    <main className="auth-page rsvp-page" aria-labelledby="day-h">
      <div className="auth-card rsvp-card">
        <p className="auth-brand" aria-hidden="true">
          <svg viewBox="0 0 24 24" className="auth-brand__icon">
            <circle cx="9" cy="12" r="5" />
            <circle cx="15" cy="12" r="5" />
          </svg>
          Nasz dzień
        </p>
        {day.isPending && (
          <>
            <h1 id="day-h">Program dnia</h1>
            <Skeleton lines={6} />
          </>
        )}
        {copy && <OfflineDay copy={copy} headingLevel={1} />}
        {day.isError && !copy && (
          <>
            <h1 id="day-h">Program dnia</h1>
            <Notice tone="error" live>
              {day.error instanceof ApiError && day.error.status === 404
                ? "Ten link nie działa — mógł zostać wyłączony. Poproście parę młodą o nowy."
                : userMessage(day.error)}
            </Notice>
          </>
        )}
        {d && (
          <>
            <div>
              <p className="overline">{d.vendor_name}</p>
              <h1 id="day-h">{d.wedding_name}</h1>
              {d.wedding_date && <p className="text-secondary">{formatDate(d.wedding_date)}</p>}
            </div>
            {d.events.map((e) => (
              <div key={`${e.name}-${e.starts_at}`} className="rsvp-event">
                <strong>{e.name}</strong>
                <span className="text-secondary">{eventWhen(e.starts_at)}</span>
                {e.address && (
                  <span className="rsvp-event__line">
                    <MapPin aria-hidden size={18} />
                    {e.address}
                  </span>
                )}
              </div>
            ))}
            <Card>
              <ol className="day-list">
                {d.items.map((i) => (
                  <li key={`${i.title}-${i.starts_at}`} className={`day-item${i.mine ? " day-item--mine" : ""}`}>
                    <span className="day-item__time num">{formatTime(i.starts_at)}</span>
                    <div className="day-item__body">
                      <p className="day-item__title">
                        {i.title} {i.mine && <StatusChip tone="info">Wasz punkt</StatusChip>}
                      </p>
                      {i.location && <p className="text-secondary">{i.location}</p>}
                      {i.preparations && <p>Przygotować: {i.preparations}</p>}
                      {i.notes && <p className="text-secondary">{i.notes}</p>}
                      {i.plan_b && <p>Plan B: {i.plan_b}</p>}
                    </div>
                  </li>
                ))}
              </ol>
            </Card>
            {d.items.length > 0 && (
              <span className="no-print">
                <Button
                  variant="secondary"
                  onPress={() => {
                    // Własne punkty usługodawcy, a gdy ich nie ma — cały program dnia.
                    const own = d.items.filter((i) => i.mine);
                    const list = own.length ? own : d.items;
                    downloadIcs(
                      list.map((i, n) => ({
                        uid: `${token.slice(0, 8)}-${n}`,
                        title: `${i.title} — ${d.wedding_name}`,
                        startsAt: i.starts_at,
                        endsAt: i.ends_at,
                        location: i.location,
                        description:
                          [i.preparations && `Przygotować: ${i.preparations}`, i.plan_b && `Plan B: ${i.plan_b}`]
                            .filter(Boolean)
                            .join(String.fromCharCode(10)) || null,
                      })),
                      "program-wesela.ics",
                    );
                  }}
                >
                  {d.items.some((i) => i.mine) ? "Dodaj swoje punkty do kalendarza" : "Dodaj program do kalendarza"}
                </Button>
              </span>
            )}
            {hasBrief(d.brief) && (
              <section className="form-stack" aria-labelledby="brief-h">
                <h2 id="brief-h">Informacje od pary</h2>
                <Card>
                  <BriefView brief={d.brief} labels={briefLabels(d.vendor_category)} />
                </Card>
              </section>
            )}
            {!!d.music?.length && (
              <section className="form-stack" aria-labelledby="music-h">
                <h2 id="music-h">Muzyka od pary</h2>
                <Card className="form-stack brief-view">
                  {byMoment(d.music).map((m) => (
                    <div key={m.id}>
                      <h3>{m.label}</h3>
                      <ul>
                        {m.items.map((s, i) => (
                          <li key={i}>
                            {songLabel(s)}
                            {s.note && <span className="text-secondary"> · {s.note}</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </Card>
              </section>
            )}
            {!!d.prep?.length && (
              <section className="form-stack" aria-labelledby="prep-h">
                <h2 id="prep-h">{d.vendor_category === "makeup" ? "Makijaże" : "Fryzury"}</h2>
                <Card className="brief-view">
                  <ul>
                    {d.prep.map((s, i) => (
                      <li key={i} className="num">
                        <strong>
                          {s.start}–{s.end}
                        </strong>{" "}
                        {s.name}
                        {d.prep!.some((x) => x.artist > 1) && <span className="text-secondary"> · stanowisko {s.artist}</span>}
                      </li>
                    ))}
                  </ul>
                </Card>
              </section>
            )}
            {!!d.photo_groups?.length && (
              <section className="form-stack" aria-labelledby="photos-h">
                <h2 id="photos-h">Zdjęcia grupowe</h2>
                <Card className="brief-view">
                  <ol>
                    {d.photo_groups.map((g, i) => (
                      <li key={i}>
                        <strong>{g.title}</strong>
                        {(g.people.length > 0 || g.extra) && `: ${[...g.people, ...(g.extra ? [g.extra] : [])].join(", ")}`}
                        <span className="text-secondary num"> · {g.minutes} min</span>
                      </li>
                    ))}
                  </ol>
                </Card>
              </section>
            )}
            <AckBox token={token} day={d} onChanged={() => void day.refetch()} />
            {d.catering && <CateringSection c={d.catering} />}
            <p className="text-secondary rsvp-privacy">
              Strona odświeża się sama co minutę — gdy program się przesunie, zobaczycie nowe godziny.
              {d.updated_at && ` Ostatnia zmiana: ${formatTime(d.updated_at)}.`}
            </p>
          </>
        )}
      </div>
    </main>
  );
}

type PublicDay = components["schemas"]["PublicDay"];

const hasBrief = (b: PublicDay["brief"]) => !!(b.must?.length || b.avoid?.length || b.people?.length || b.notes || b.contact);

/** Potwierdzenie przeczytania wersji: para widzi, kto zna aktualny program. */
function AckBox({ token, day, onChanged }: { token: string; day: PublicDay; onChanged: () => void }) {
  const [message, setMessage] = useState<string | null>(null);
  const ack = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/day/{token}/ack", { params: { path: { token } }, body: { version: day.version } })),
    onSuccess: () => {
      setMessage(null);
      onChanged();
    },
    onError: (e) => {
      if (e instanceof ApiError && e.code === "day_link.version_changed") {
        setMessage("Program właśnie się zmienił. Przeczytajcie zmiany i potwierdźcie nową wersję.");
        onChanged();
      } else setMessage(userMessage(e));
    },
  });
  if (day.up_to_date) {
    return (
      <Notice tone="success" live>
        Potwierdziliście wersję {day.version} programu. Para widzi, że ją znacie.
      </Notice>
    );
  }
  return (
    <section className="form-stack no-print" aria-labelledby="ack-h">
      <h2 id="ack-h">Wersja {day.version} programu</h2>
      {day.acknowledged_version && (
        <Notice tone="warning">Od Waszego potwierdzenia (wersja {day.acknowledged_version}) program lub informacje się zmieniły.</Notice>
      )}
      {message && (
        <Notice tone="error" live>
          {message}
        </Notice>
      )}
      <p className="text-secondary">Po przeczytaniu potwierdźcie — para zobaczy, że znacie aktualny program.</p>
      <Button pending={ack.isPending} onPress={() => ack.mutate()}>
        Potwierdzam, że znam wersję {day.version}
      </Button>
    </section>
  );
}

type Catering = components["schemas"]["Catering"];
type Ages = Catering["attending"];

const DIET: Record<string, string> = {
  standard: "bez wymagań",
  vegetarian: "wegetariańska",
  vegan: "wegańska",
  gluten_free: "bezglutenowa",
  other: "inna",
};

const AGE: Record<string, string> = { adult: "dorosły", teen: "nastolatek", child: "dziecko", infant: "maluch" };

function agesText(a: Ages): string {
  const parts = [
    plural(a.adults, { one: "# dorosły", few: "# dorosłych", many: "# dorosłych", other: "# dorosłego" }),
    a.teens ? plural(a.teens, { one: "# nastolatek", few: "# nastolatków", many: "# nastolatków", other: "# nastolatka" }) : "",
    a.children ? plural(a.children, { one: "# dziecko", few: "# dzieci", many: "# dzieci", other: "# dziecka" }) : "",
    a.infants ? plural(a.infants, { one: "# maluch (0–3)", few: "# maluchy (0–3)", many: "# maluchów (0–3)", other: "# malucha (0–3)" }) : "",
  ];
  return parts.filter(Boolean).join(", ");
}

const dietsText = (diets: Catering["diets"]) => diets.map((x) => `${DIET[x.diet] ?? x.diet}: ${x.count}`).join(", ");

/** Dla sali i cateringu: liczby dla kuchni i obsługi; imiona i uwagi tylko za zgodą pary. */
function CateringSection({ c }: { c: Catering }) {
  return (
    <section className="form-stack day-catering" aria-labelledby="catering-h">
      <div className="rsvp-guest-head">
        <h2 id="catering-h">Dla kuchni i obsługi sali</h2>
        <span className="no-print">
          <Button variant="secondary" icon={<Printer aria-hidden size={18} />} onPress={() => window.print()}>
            Drukuj
          </Button>
        </span>
      </div>
      <Card className="form-stack">
        <dl className="rsvp-info">
          <div>
            <dt>Potwierdzeni na przyjęcie</dt>
            <dd className="num">{agesText(c.attending)}</dd>
          </div>
          <div>
            <dt>Jeszcze bez odpowiedzi</dt>
            <dd className="num">{c.pending}</dd>
          </div>
          <div>
            <dt>Diety (potwierdzeni)</dt>
            <dd>{c.diets.length ? dietsText(c.diets) : "wszyscy bez wymagań"}</dd>
          </div>
          <div>
            <dt>Posiłki dla obsługi (zespół, fotograf…)</dt>
            <dd className="num">{c.crew_meals}</dd>
          </div>
        </dl>
      </Card>
      {c.tables.length > 0 && (
        <Card className="form-stack">
          <h3>Stoły</h3>
          <ul className="day-tables">
            {c.tables.map((t) => (
              <li key={t.name} className="form-stack day-table">
                <p>
                  <strong>{t.name}</strong> — {agesText(t.count)}
                  {t.diets.length > 0 && <span className="text-secondary"> · {dietsText(t.diets)}</span>}
                </p>
                {t.guests && (
                  <ul className="day-table__guests">
                    {t.guests.map((g, i) => (
                      <li key={`${g.name}-${i}`}>
                        {g.name}
                        {g.age_group !== "adult" && <span className="text-secondary"> ({AGE[g.age_group] ?? g.age_group})</span>}
                        {g.diet !== "standard" && <span> — {DIET[g.diet] ?? g.diet}</span>}
                        {g.diet_note && <span className="text-secondary"> · {g.diet_note}</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}
      <p className="text-secondary">
        {c.details_shared
          ? "Para udostępniła imiona i uwagi dietetyczne wyłącznie do przygotowania posiłków. Nie przekazujcie ich dalej."
          : "Bez imion gości — para udostępnia tylko liczby."}{" "}
        Liczby zmieniają się po każdej odpowiedzi gości.
      </p>
    </section>
  );
}
