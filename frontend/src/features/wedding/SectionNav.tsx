import { Printer } from "lucide-react";
import { Link, NavLink } from "react-router";

import { useWedding, useWeddingId } from "./data";

interface Section {
  to: string;
  label: string;
}

/** Podzakładki działu (np. Budżet: wydatki i usługodawcy). Każda ma własny adres. */
export function SectionNav({ label, sections }: { label: string; sections: Section[] }) {
  const id = useWeddingId();
  return (
    <nav className="subnav" aria-label={label}>
      {sections.map((s) => (
        <NavLink key={s.to} to={`/w/${id}/${s.to}`} end viewTransition className="subnav__link">
          {s.label}
        </NavLink>
      ))}
    </nav>
  );
}

export const PLAN_SECTIONS: Section[] = [
  { to: "plan", label: "Zadania" },
  { to: "kalendarz", label: "Kalendarz" },
  { to: "formalnosci", label: "Dokumenty do ślubu" },
  { to: "pomocnicy", label: "Pomocnicy" },
];

export const MONEY_SECTIONS: Section[] = [
  { to: "budzet", label: "Wydatki" },
  { to: "uslugodawcy", label: "Usługodawcy" },
  { to: "sponsorzy", label: "Kto płaci" },
];

export const GUEST_SECTIONS: Section[] = [
  { to: "goscie", label: "Lista gości" },
  { to: "stoly", label: "Plan stołów" },
  { to: "zaproszenia", label: "Zaproszenia" },
  { to: "frekwencja", label: "Frekwencja" },
  { to: "logistyka", label: "Transport i noclegi" },
  { to: "menu", label: "Menu" },
  { to: "strona-goscia", label: "Strona gościa" },
];

export const DAY_SECTIONS: Section[] = [
  { to: "dzien", label: "Harmonogram" },
  { to: "fryzura-i-makijaz", label: "Fryzura i makijaż" },
  { to: "zdjecia", label: "Zdjęcia grupowe" },
  { to: "muzyka", label: "Muzyka" },
];

/** Podzakładki dnia ślubu; koordynator dnia nie widzi muzyki (to część planowania pary). */
export function DaySectionNav() {
  const role = useWedding(useWeddingId()).data?.my_role;
  return <SectionNav label="Dzień ślubu" sections={role === "coordinator" ? DAY_SECTIONS.filter((s) => s.to !== "muzyka") : DAY_SECTIONS} />;
}

/** Link do strony wydruku (/druk/:rodzaj) z ikoną drukarki. */
export function PrintLink({ kind, children }: { kind: string; children: React.ReactNode }) {
  const id = useWeddingId();
  return (
    <Link to={`/w/${id}/druk/${kind}`} className="wp-button wp-button--text print-link">
      <Printer aria-hidden size={18} />
      {children}
    </Link>
  );
}
