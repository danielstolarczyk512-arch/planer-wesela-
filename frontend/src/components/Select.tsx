import { ChevronDown } from "lucide-react";
import {
  Button as AriaButton,
  FieldError,
  Label,
  ListBox,
  ListBoxItem,
  Popover,
  Select as AriaSelect,
  SelectValue,
  Text,
  type Key,
} from "react-aria-components";

import "./Field.css";
import "./Select.css";

interface SelectProps {
  label: string;
  description?: string;
  error?: string | null;
  options: { id: string; label: string }[];
  value: string | null;
  onChange: (value: string) => void;
  placeholder?: string;
  isRequired?: boolean;
}

/** Lista wyboru (dostępna z klawiatury i czytnika ekranu, lista w wyskakującym panelu). */
export function Select({ label, description, error, options, value, onChange, placeholder, isRequired }: SelectProps) {
  return (
    <AriaSelect
      className="wp-field"
      selectedKey={value}
      onSelectionChange={(k: Key | null) => k !== null && onChange(String(k))}
      isRequired={isRequired}
      isInvalid={!!error}
      placeholder={placeholder ?? "Wybierz"}
    >
      <Label className="wp-field__label">{label}</Label>
      <AriaButton className="wp-field__input wp-select__button">
        <SelectValue className="wp-select__value" />
        <ChevronDown aria-hidden size={20} strokeWidth={1.75} />
      </AriaButton>
      {description && (
        <Text slot="description" className="wp-field__description">
          {description}
        </Text>
      )}
      <FieldError className="wp-field__error">{error}</FieldError>
      <Popover className="wp-select__popover">
        <ListBox className="wp-select__list">
          {options.map((o) => (
            <ListBoxItem key={o.id} id={o.id} className="wp-select__option">
              {o.label}
            </ListBoxItem>
          ))}
        </ListBox>
      </Popover>
    </AriaSelect>
  );
}
