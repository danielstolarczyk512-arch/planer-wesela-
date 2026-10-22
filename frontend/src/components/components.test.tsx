import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { AmountField, TextField } from "./Field";
import { Sheet } from "./Overlay";
import { ToastProvider, useToast } from "./Toast";

describe("TextField", () => {
  it("błąd jest tekstem powiązanym z polem (nie tylko kolorem)", () => {
    render(<TextField label="E-mail" error="Wpisz adres e-mail." />);
    const input = screen.getByLabelText("E-mail");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription(/Wpisz adres e-mail/);
  });
});

describe("AmountField", () => {
  it("akceptuje przecinek, zwraca napis dla API i formatuje po wyjściu z pola", async () => {
    const onChange = vi.fn();
    render(<AmountField label="Zadatek" value={null} onChange={onChange} />);
    const input = screen.getByLabelText("Zadatek");
    await userEvent.type(input, "1500,5");
    await userEvent.tab();
    expect(onChange).toHaveBeenCalledWith("1500.50");
    expect((input as HTMLInputElement).value).toMatch(/^1\s500,50\szł$/);
  });

  it("nieprawidłowa kwota: komunikat przy polu, bez zmiany wartości", async () => {
    const onChange = vi.fn();
    render(<AmountField label="Zadatek" value={null} onChange={onChange} />);
    await userEvent.type(screen.getByLabelText("Zadatek"), "abc");
    await userEvent.tab();
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByText(/Wpisz kwotę/)).toBeInTheDocument();
  });
});

function DirtySheet() {
  const [open, setOpen] = useState(true);
  const [text, setText] = useState("");
  return (
    <>
      <p>{open ? "otwarty" : "zamknięty"}</p>
      <Sheet title="Notatka" isOpen={open} onOpenChange={setOpen} isDirty={text !== ""}>
        <TextField label="Treść" value={text} onChange={setText} />
      </Sheet>
    </>
  );
}

describe("Sheet", () => {
  it("Escape przy niezapisanych zmianach pyta zamiast zamykać", async () => {
    render(<DirtySheet />);
    await userEvent.type(screen.getByLabelText("Treść"), "ważne");
    await userEvent.keyboard("{Escape}");
    expect(screen.getByText("otwarty")).toBeInTheDocument();
    expect(screen.getByText(/Zapisać szkic czy odrzucić zmiany/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Odrzuć zmiany" }));
    expect(screen.getByText("zamknięty")).toBeInTheDocument();
  });

  it("bez zmian Escape zamyka od razu", async () => {
    render(<DirtySheet />);
    await userEvent.keyboard("{Escape}");
    expect(screen.getByText("zamknięty")).toBeInTheDocument();
  });
});

function ToastTrigger({ onUndo }: { onUndo: () => void }) {
  const toast = useToast();
  return <button onClick={() => toast("Zrobione", onUndo)}>pokaż</button>;
}

describe("Toast", () => {
  it("„Cofnij” wywołuje akcję, a komunikat jest w regionie na żywo", async () => {
    const onUndo = vi.fn();
    render(
      <ToastProvider>
        <ToastTrigger onUndo={onUndo} />
      </ToastProvider>,
    );
    await userEvent.click(screen.getByText("pokaż"));
    expect(screen.getByText("Zrobione").closest("[aria-live]")).toHaveAttribute("aria-live", "polite");
    await userEvent.click(screen.getByRole("button", { name: "Cofnij" }));
    expect(onUndo).toHaveBeenCalledOnce();
  });
});
