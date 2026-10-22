import { AlertTriangle, CheckCircle2, Info, XCircle, CircleDashed } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import "./Surface.css";

export function Card({ children, as: Tag = "section", ...rest }: { children: ReactNode; as?: "section" | "div" | "article" } & React.HTMLAttributes<HTMLElement>) {
  return (
    <Tag {...rest} className={`wp-card ${rest.className ?? ""}`}>
      {children}
    </Tag>
  );
}

export type Tone = "success" | "warning" | "error" | "info" | "neutral";

const ICONS: Record<Tone, typeof Info> = {
  success: CheckCircle2,
  warning: AlertTriangle,
  error: XCircle,
  info: Info,
  neutral: CircleDashed,
};

/** Status zawsze z nazwą (i ikoną), nigdy samym kolorem. */
export function StatusChip({ tone, children }: { tone: Tone; children: ReactNode }) {
  const Icon = ICONS[tone];
  return (
    <span className={`wp-chip wp-tone--${tone}`}>
      <Icon aria-hidden size={16} strokeWidth={1.75} />
      {children}
    </span>
  );
}

/**
 * Komunikat w treści. Błędy nie znikają same. `live`: odczytywany przez czytnik ekranu
 * w chwili pojawienia się (np. błąd logowania).
 */
export function Notice({
  tone,
  title,
  children,
  live,
  id,
}: {
  tone: Tone;
  title?: string;
  children?: ReactNode;
  live?: boolean;
  id?: string;
}) {
  const Icon = ICONS[tone];
  return (
    <div
      id={id}
      className={`wp-notice wp-tone--${tone}`}
      role={live ? (tone === "error" ? "alert" : "status") : undefined}
      tabIndex={-1}
    >
      <Icon aria-hidden size={20} strokeWidth={1.75} className="wp-notice__icon" />
      <div>
        {title && <p className="wp-notice__title">{title}</p>}
        {children && <div>{children}</div>}
      </div>
    </div>
  );
}

/** Stan pusty: jedno wyjaśnienie i jedno konkretne działanie (bez fikcyjnych kwot). */
export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="wp-empty">
      <h2>{title}</h2>
      {children && <p className="text-secondary">{children}</p>}
      {action}
    </div>
  );
}

/**
 * Szkielet ładowania: pokazywany dopiero po ~150 ms (szybkie odpowiedzi bez mignięcia),
 * stałe wymiary, bez ciągłego błyszczenia.
 */
export function Skeleton({ lines = 3, delay = 150, label = "Wczytywanie" }: { lines?: number; delay?: number; label?: string }) {
  const [visible, setVisible] = useState(delay === 0);
  useEffect(() => {
    const t = window.setTimeout(() => setVisible(true), delay);
    return () => window.clearTimeout(t);
  }, [delay]);
  return (
    <div className="wp-skeleton" role="status" aria-label={label} aria-busy="true">
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className="wp-skeleton__line" style={{ visibility: visible ? "visible" : "hidden" }} />
      ))}
    </div>
  );
}
