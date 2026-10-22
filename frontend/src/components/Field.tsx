import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import {
  Button as AriaButton,
  Checkbox as AriaCheckbox,
  FieldError,
  Group,
  Input,
  Label,
  Text,
  TextArea,
  TextField as AriaTextField,
  type CheckboxProps,
  type TextFieldProps as AriaTextFieldProps,
} from "react-aria-components";

import { formatMoney, parseAmountInput } from "../lib/format";
import "./Field.css";

export interface CommonProps {
  label: string;
  description?: string;
  /** Błąd z serwera albo walidacji formularza: tekst przy polu (nie sam kolor obrysu). */
  error?: string | null;
}

export interface TextFieldProps extends Omit<AriaTextFieldProps, "className" | "children">, CommonProps {
  placeholder?: string;
}

export function TextField({ label, description, error, placeholder, ...rest }: TextFieldProps) {
  return (
    <AriaTextField {...rest} isInvalid={!!error || rest.isInvalid} className="wp-field">
      <Label className="wp-field__label">{label}</Label>
      <Input className="wp-field__input" placeholder={placeholder} />
      {description && (
        <Text slot="description" className="wp-field__description">
          {description}
        </Text>
      )}
      <FieldError className="wp-field__error">{error}</FieldError>
    </AriaTextField>
  );
}

/** Pole wielowierszowe (np. lista „jedna pozycja w wierszu”). */
export function TextAreaField({ label, description, error, placeholder, rows = 4, ...rest }: TextFieldProps & { rows?: number }) {
  return (
    <AriaTextField {...rest} isInvalid={!!error || rest.isInvalid} className="wp-field">
      <Label className="wp-field__label">{label}</Label>
      <TextArea className="wp-field__input wp-field__textarea" placeholder={placeholder} rows={rows} />
      {description && (
        <Text slot="description" className="wp-field__description">
          {description}
        </Text>
      )}
      <FieldError className="wp-field__error">{error}</FieldError>
    </AriaTextField>
  );
}

export function PasswordField({ label, description, error, ...rest }: TextFieldProps) {
  const [visible, setVisible] = useState(false);
  return (
    <AriaTextField
      {...rest}
      type={visible ? "text" : "password"}
      isInvalid={!!error || rest.isInvalid}
      className="wp-field"
    >
      <Label className="wp-field__label">{label}</Label>
      <Group className="wp-field__group">
        <Input className="wp-field__input wp-field__input--grouped" />
        <AriaButton
          className="wp-field__adornment"
          onPress={() => setVisible((v) => !v)}
          aria-label={visible ? "Ukryj hasło" : "Pokaż hasło"}
          aria-pressed={visible}
        >
          {visible ? <EyeOff aria-hidden size={20} strokeWidth={1.75} /> : <Eye aria-hidden size={20} strokeWidth={1.75} />}
        </AriaButton>
      </Group>
      {description && (
        <Text slot="description" className="wp-field__description">
          {description}
        </Text>
      )}
      <FieldError className="wp-field__error">{error}</FieldError>
    </AriaTextField>
  );
}

export interface AmountFieldProps extends CommonProps {
  /** Wartość dla API ("1234.50") albo null (brak wyceny). */
  value: string | null;
  onChange: (value: string | null) => void;
  isRequired?: boolean;
  name?: string;
}

/**
 * Kwota: klawiatura dziesiętna, przecinek lub kropka, formatowanie po zakończeniu edycji.
 * Wartość przechowywana jako napis (bez liczb zmiennoprzecinkowych).
 */
export function AmountField({ label, description, error, value, onChange, isRequired, name }: AmountFieldProps) {
  const [text, setText] = useState(value ? formatMoney({ amount: value, currency: "PLN" }) : "");
  const [localError, setLocalError] = useState<string | null>(null);
  return (
    <AriaTextField
      name={name}
      value={text}
      onChange={setText}
      isRequired={isRequired}
      inputMode="decimal"
      isInvalid={!!(error ?? localError)}
      onFocus={(e) => {
        if (!value) return;
        // Do edycji surowa liczba („1200”, „1200,50”) zaznaczona w całości: wpisanie zastępuje kwotę.
        setText(value.replace(/\.00$/, "").replace(".", ","));
        const input = e.target as HTMLInputElement;
        requestAnimationFrame(() => input.select());
      }}
      onBlur={() => {
        if (!text.trim()) {
          setLocalError(null);
          onChange(null);
          return;
        }
        const parsed = parseAmountInput(text);
        if (parsed === null) {
          setLocalError("Wpisz kwotę, np. 1500 albo 1500,50.");
          return;
        }
        setLocalError(null);
        onChange(parsed);
        setText(formatMoney({ amount: parsed, currency: "PLN" }));
      }}
      className="wp-field"
    >
      <Label className="wp-field__label">{label}</Label>
      <Input className="wp-field__input num" />
      {description && (
        <Text slot="description" className="wp-field__description">
          {description}
        </Text>
      )}
      <FieldError className="wp-field__error">{error ?? localError}</FieldError>
    </AriaTextField>
  );
}

export function Checkbox({ children, ...rest }: Omit<CheckboxProps, "className"> & { children: React.ReactNode }) {
  return (
    <AriaCheckbox {...rest} className="wp-checkbox">
      <span className="wp-checkbox__box" aria-hidden="true">
        <svg viewBox="0 0 18 18">
          <polyline points="4 9.5 7.5 13 14 5.5" />
        </svg>
      </span>
      <span>{children}</span>
    </AriaCheckbox>
  );
}
