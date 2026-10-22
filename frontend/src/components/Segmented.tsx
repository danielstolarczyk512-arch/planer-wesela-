import type { ReactNode } from "react";
import { Label, Radio, RadioGroup } from "react-aria-components";

import "./Segmented.css";

interface SegmentedProps<T extends string> {
  label: string;
  value: T;
  options: { value: T; label: ReactNode }[];
  onChange: (value: T) => void;
  /** „chips”: filtry o szerokości tekstu, zawijane w wiersze (np. statusy gości). */
  variant?: "segments" | "chips";
}

/** Wybór jednej z kilku opcji (np. motyw). Semantyka grupy radiowej, wygląd przełącznika. */
export function Segmented<T extends string>({ label, value, options, onChange, variant = "segments" }: SegmentedProps<T>) {
  return (
    <RadioGroup
      className={`wp-segmented${variant === "chips" ? " wp-segmented--chips" : ""}`}
      value={value}
      onChange={(v) => onChange(v as T)}
      orientation="horizontal"
    >
      <Label className="wp-field__label">{label}</Label>
      <div className="wp-segmented__track">
        {options.map((o) => (
          <Radio key={o.value} value={o.value} className="wp-segmented__option">
            {o.label}
          </Radio>
        ))}
      </div>
    </RadioGroup>
  );
}
