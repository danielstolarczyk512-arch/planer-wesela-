import { useEffect, useState } from "react";

import "./WeddingProgressBar.css";

export const FINALE_TEXT = "Wszystko dopięte na ostatni guzik! Teraz czas powiedzieć «TAK»! 💗";

/** Dokładny udział (0–100) do ustawienia końca wypełnienia. */
export function exactShare(completed: number, total: number): number {
  if (total <= 0) return 0;
  return Math.min(100, Math.max(0, (completed / total) * 100));
}

/** Etykieta: zaokrąglona, ale „100%” tylko gdy naprawdę wszystko gotowe (24,9/25 → 99%). */
export function percentLabel(completed: number, total: number, complete: boolean): number {
  const rounded = Math.round(exactShare(completed, total));
  return complete ? 100 : Math.min(99, rounded);
}

function prefersReducedMotion(): boolean {
  if (typeof document === "undefined") return false;
  if (document.documentElement.classList.contains("reduce-motion")) return true;
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// Kilkanaście konfetti i serduszek: kierunek (px) i opóźnienie, bez losowości (stabilny render).
const BITS = Array.from({ length: 14 }, (_, i) => {
  const angle = (-160 + (i * 140) / 13) * (Math.PI / 180);
  const dist = 46 + (i % 3) * 16;
  return {
    dx: Math.round(Math.cos(angle) * dist),
    dy: Math.round(Math.sin(angle) * dist),
    delay: (i % 5) * 40,
    kind: i % 4 === 0 ? "heart" : i % 2 === 0 ? "gold" : "pink",
  };
});

interface Props {
  completed: number;
  total: number;
  /**
   * Czy zapis zadań jest potwierdzony (żadna zmiana nie czeka na serwer). Finał pokazujemy dopiero
   * wtedy, żeby nieudany zapis nie dał fałszywego 100%.
   */
  settled?: boolean;
}

/** Pasek „Wasze postępy”: różowy tor, biała wykonana część, pierścionek (100% — para młoda). */
export function WeddingProgressBar({ completed, total, settled = true }: Props) {
  const trulyComplete = total > 0 && completed === total;
  const complete = trulyComplete && settled;
  const share = exactShare(completed, total);
  const label = percentLabel(completed, total, complete);

  // Świętowanie tylko przy przejściu <100% → 100% (bez powtórki przy pierwszym renderze i refetchu).
  const [wasComplete, setWasComplete] = useState(complete);
  const [burst, setBurst] = useState(0);
  const [celebrating, setCelebrating] = useState(false);
  if (complete !== wasComplete) {
    setWasComplete(complete);
    if (complete && !prefersReducedMotion()) {
      setBurst((n) => n + 1);
      setCelebrating(true);
    } else if (!complete) {
      setCelebrating(false);
    }
  }
  useEffect(() => {
    if (!celebrating) return;
    const timer = window.setTimeout(() => setCelebrating(false), 2600);
    return () => window.clearTimeout(timer);
  }, [celebrating, burst]);

  return (
    <div className={`wpb${complete ? " wpb--complete" : ""}`}>
      <div
        className="wpb__rail"
        role="progressbar"
        aria-label="Postęp przygotowań"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={label}
        aria-valuetext={`${completed} z ${total} zadań`}
      >
        <div className="wpb__track">
          <div className="wpb__fill" style={{ width: `${share}%` }} />
        </div>
        <div className="wpb__marker" style={{ left: `${share}%` }} aria-hidden>
          {!complete && (
            <span className="wpb__icon">
              <img src="/media/postep/pierscionek.png" alt="" height={48} draggable={false} />
            </span>
          )}
          <span className="wpb__percent num">{label}%</span>
        </div>
        {/* Meta: para młoda stoi przy prawym końcu toru; przy 100% zajmuje miejsce pierścionka. */}
        <div className="wpb__goal" aria-hidden>
          <span className={`wpb__couple${complete ? " wpb__couple--on" : ""}${burst > 0 && complete ? " wpb__icon--pop" : ""}`}>
            <img src="/media/postep/para-mloda.png" alt="" height={48} draggable={false} />
          </span>
          {celebrating && (
            <span className="wpb__burst" key={burst}>
              {BITS.map((b, i) => (
                <i
                  key={i}
                  className={`wpb__bit wpb__bit--${b.kind}`}
                  style={{ "--dx": `${b.dx}px`, "--dy": `${b.dy}px`, animationDelay: `${b.delay}ms` } as React.CSSProperties}
                />
              ))}
            </span>
          )}
        </div>
      </div>
      <p className="wpb__finale" aria-live="polite">
        {complete ? FINALE_TEXT : ""}
      </p>
    </div>
  );
}
