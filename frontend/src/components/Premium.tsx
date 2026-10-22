import { Sparkles } from "lucide-react";

import "./Premium.css";

/**
 * Oznaczenie funkcji planu Premium. Płatności jeszcze nie ma: funkcja działa dla wszystkich,
 * a znaczek tylko zapowiada, że w przyszłości będzie częścią planu płatnego
 * (docs/analysis/04-plan-rozwoju-i-uslugi-platne.md).
 */
export function PremiumBadge() {
  return (
    <span className="wp-premium" title="Funkcja planu Premium — na razie dostępna bezpłatnie">
      <Sparkles aria-hidden size={14} strokeWidth={2} />
      Premium
    </span>
  );
}

/** Krótka informacja pod nagłówkiem funkcji Premium. */
export function PremiumNote() {
  return <p className="text-secondary wp-premium-note">Funkcja Premium — w okresie testów bezpłatna dla wszystkich.</p>;
}
