import {
  DateField as AriaDateField,
  DateInput,
  DateSegment,
  FieldError,
  Label,
  Text,
  TimeField as AriaTimeField,
  type DateFieldProps,
  type DateValue,
  type TimeFieldProps as AriaTimeFieldProps,
  type TimeValue,
} from "react-aria-components";

import type { CommonProps } from "./Field";
import "./Field.css";

// Osobny moduł: @internationalized/date nie trafia do pakietu strony logowania.
export interface DateFieldPropsWp<T extends DateValue> extends Omit<DateFieldProps<T>, "className" | "children">, CommonProps {}

/** Data z segmentami (dzień, miesiąc, rok) w kolejności polskiej; bez wymuszania kalendarza. */
export function DateField<T extends DateValue>({ label, description, error, ...rest }: DateFieldPropsWp<T>) {
  return (
    <AriaDateField {...rest} isInvalid={!!error || rest.isInvalid} className="wp-field">
      <Label className="wp-field__label">{label}</Label>
      <DateInput className="wp-field__input wp-field__date">
        {(segment) => <DateSegment segment={segment} className="wp-field__segment" />}
      </DateInput>
      {description && (
        <Text slot="description" className="wp-field__description">
          {description}
        </Text>
      )}
      <FieldError className="wp-field__error">{error}</FieldError>
    </AriaDateField>
  );
}

export interface TimeFieldPropsWp<T extends TimeValue> extends Omit<AriaTimeFieldProps<T>, "className" | "children">, CommonProps {}

/** Godzina (24 h, segmenty godzina:minuta). */
export function TimeField<T extends TimeValue>({ label, description, error, ...rest }: TimeFieldPropsWp<T>) {
  return (
    <AriaTimeField {...rest} hourCycle={24} isInvalid={!!error || rest.isInvalid} className="wp-field">
      <Label className="wp-field__label">{label}</Label>
      <DateInput className="wp-field__input wp-field__date">
        {(segment) => <DateSegment segment={segment} className="wp-field__segment" />}
      </DateInput>
      {description && (
        <Text slot="description" className="wp-field__description">
          {description}
        </Text>
      )}
      <FieldError className="wp-field__error">{error}</FieldError>
    </AriaTimeField>
  );
}
