import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router";
import { ROLE_LABEL } from "../wedding/data";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { EmptyState, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { daysUntil, formatDate, plural } from "../../lib/format";
import { lastWedding } from "../wedding/lastWedding";
import "./home.css";
import { WeddingWizard } from "./WeddingWizard";

type Wedding = components["schemas"]["WeddingOut"];


const MONTHS = new Intl.DateTimeFormat("pl-PL", { month: "long", year: "numeric", timeZone: "UTC" });

/** Kiedy: data → „za 30 dni”; tylko miesiąc → „wrzesień 2027”; brak → zachęta (spec 2.4). */
export function whenLabel(w: Pick<Wedding, "wedding_date" | "planned_month">, now = new Date()): string {
  if (w.wedding_date) {
    const days = daysUntil(w.wedding_date, now);
    const date = formatDate(w.wedding_date);
    if (days === 0) return `${date} · dziś Wasz dzień`;
    if (days < 0) return `${date} · po ślubie`;
    return `${date} · ${plural(days, { one: "jutro", few: "za # dni", many: "za # dni", other: "za # dnia" })}`;
  }
  if (w.planned_month) {
    const [y, m] = w.planned_month.split("-").map(Number);
    const month = MONTHS.format(new Date(Date.UTC(y ?? 2000, (m ?? 1) - 1, 15)));
    // Intl zwraca „sierpień 2027”; na początku zdania wielka litera.
    return `${month.charAt(0).toLocaleUpperCase("pl-PL")}${month.slice(1)} · dokładna data do ustalenia`;
  }
  return "Data jeszcze nieustalona";
}

export function HomePage() {
  const [creating, setCreating] = useState(false);
  const weddings = useQuery({
    queryKey: ["weddings"],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings", { signal })),
  });
  const [params] = useSearchParams();

  // Wejście do aplikacji: od razu ostatnio otwarte wesele albo jedyne wesele.
  // „Wszystkie wesela” w zakładce Więcej (?wybierz=1) pokazuje listę.
  if (weddings.data && !params.has("wybierz")) {
    const items = weddings.data.items;
    const last = lastWedding();
    const target = items.find((w) => w.id === last) ?? (items.length === 1 ? items[0] : undefined);
    if (target) return <Navigate to={`/w/${target.id}`} replace />;
  }

  return (
    <main className="page enter-detail">
      <div className="home-head">
        <h1>Wasze wesela</h1>
        {weddings.data && weddings.data.items.length > 0 && (
          <Button variant="secondary" icon={<Plus aria-hidden size={20} />} onPress={() => setCreating(true)}>
            Nowe wesele
          </Button>
        )}
      </div>

      {weddings.isPending && <Skeleton lines={5} />}
      {weddings.isError && (
        <Notice tone="error" title="Nie udało się wczytać listy." live>
          <p>{userMessage(weddings.error)}</p>
          <Button variant="text" onPress={() => void weddings.refetch()}>
            Spróbuj ponownie
          </Button>
        </Notice>
      )}
      {weddings.data && weddings.data.items.length === 0 && (
        <EmptyState
          title="Zacznijmy od Waszego wesela"
          action={<Button onPress={() => setCreating(true)}>Utwórz wesele</Button>}
        >
          Kilka pytań (termin, ceremonia, budżet) — i macie gotowy plan zadań oraz podział budżetu. Wszystko poza nazwą można pominąć.
        </EmptyState>
      )}
      {weddings.data && weddings.data.items.length > 0 && (
        <ul className="home-list">
          {weddings.data.items.map((w) => (
            <li key={w.id}>
              <Link to={`/w/${w.id}`} className="wp-card home-card">
                <h2>{w.name}</h2>
                <p className="num">{whenLabel(w)}</p>
                <StatusChip tone={w.my_role === "viewer" ? "neutral" : "info"}>{ROLE_LABEL[w.my_role] ?? w.my_role}</StatusChip>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <WeddingWizard isOpen={creating} onOpenChange={setCreating} />
    </main>
  );
}
