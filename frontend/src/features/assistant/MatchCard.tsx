import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";

import { Card, StatusChip } from "../../components/Surface";
import { FRESHNESS, formatDay, type CatalogPackage, type Match } from "./assistant";

function PackageLine({ pkg }: { pkg: CatalogPackage }) {
  return (
    <li className="match__pkg">
      <span className="match__pkg-name">{pkg.name}</span>
      <strong>{pkg.price_label}</strong>
      <span className="text-secondary">
        {pkg.season_known ? `sezon ${pkg.season}` : "sezon nie podany"} · odczytano {formatDay(pkg.observed_at)}
        {pkg.source_url && (
          <>
            {" · "}
            <a href={pkg.source_url} target="_blank" rel="noopener noreferrer">
              źródło <ExternalLink aria-hidden size={14} />
              <span className="visually-hidden"> (otwiera się w nowej karcie)</span>
            </a>
          </>
        )}
      </span>
      {pkg.conflict && <StatusChip tone="warning">Źródła podają różne ceny</StatusChip>}
    </li>
  );
}

/**
 * Karta firmy z katalogu: dlaczego pasuje, cena i jej źródło, czego brakuje.
 * Nie ma tu etykiety „sprawdzony” ani oceny punktowej — tylko dowody i braki.
 */
export function MatchCard({ match, actions }: { match: Match; actions?: ReactNode }) {
  const v = match.vendor;
  const fresh = FRESHNESS[v.freshness] ?? FRESHNESS.unknown!;
  const reasons = match.reasons.filter((r) => r.kind !== "category");
  return (
    <Card as="article" className="match" aria-label={v.name}>
      <header className="match__head">
        <div>
          <h3>{v.name}</h3>
          <p className="text-secondary">{[v.city, v.service_area].filter(Boolean).join(" · ") || "Lokalizacja nie podana"}</p>
        </div>
        <StatusChip tone={fresh.tone}>{fresh.label}</StatusChip>
      </header>

      {reasons.length > 0 && (
        <section aria-label="Dlaczego pasuje">
          <h4>Dlaczego pasuje</h4>
          <ul className="match__list">
            {reasons.map((r, i) => (
              <li key={i}>
                {r.text}
                {r.evidence && <q className="match__quote">{r.evidence}</q>}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-label="Cennik publiczny">
        <h4>Cennik publiczny</h4>
        {v.packages.length === 0 ? (
          <p className="text-secondary">Brak ceny w katalogu — zapytaj o wycenę.</p>
        ) : (
          <ul className="match__pkgs">
            {v.packages.slice(0, 3).map((p) => (
              <PackageLine key={p.id} pkg={p} />
            ))}
          </ul>
        )}
        {v.surcharges.length > 0 && (
          <p className="text-secondary">
            Dopłaty: {v.surcharges.map((s) => `${s.name} — ${s.price_label}`).join("; ")}
          </p>
        )}
        <p className="text-secondary">Cena publiczna nie jest wyceną na Wasz termin.</p>
      </section>

      {match.flags.length > 0 && (
        <ul className="match__flags" aria-label="Uwagi">
          {match.flags.map((f) => (
            <li key={f}>
              <StatusChip tone="warning">{f}</StatusChip>
            </li>
          ))}
        </ul>
      )}

      <section aria-label="Czego brakuje">
        <h4>Czego brakuje</h4>
        <ul className="match__list match__list--missing">
          {match.missing.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      </section>

      {actions && <footer className="match__actions">{actions}</footer>}
    </Card>
  );
}
