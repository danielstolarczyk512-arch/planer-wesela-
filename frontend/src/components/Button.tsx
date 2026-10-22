import type { ReactNode } from "react";
import { Button as AriaButton, type ButtonProps as AriaButtonProps } from "react-aria-components";

import "./Button.css";

export interface ButtonProps extends Omit<AriaButtonProps, "children" | "className"> {
  variant?: "primary" | "secondary" | "danger" | "text";
  /** Pełna szerokość kontenera (główne działanie ekranu). */
  block?: boolean;
  /** Trwa zapis: przycisk blokuje tylko ponowne wysłanie, nie całe GUI. */
  pending?: boolean;
  icon?: ReactNode;
  children: ReactNode;
}

export function Button({
  variant = "primary",
  block,
  pending,
  icon,
  children,
  isDisabled,
  ...rest
}: ButtonProps) {
  return (
    <AriaButton
      {...rest}
      isDisabled={isDisabled}
      isPending={pending}
      className={`wp-button wp-button--${variant}${block ? " wp-button--block" : ""}`}
    >
      {pending ? <span className="wp-button__spinner" aria-hidden="true" /> : icon}
      <span>{children}</span>
    </AriaButton>
  );
}
