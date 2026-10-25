import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AppearanceTools } from "./AppearanceTools";

describe("panel wyglądu", () => {
  it("Escape zamyka panel i oddaje fokus do przycisku otwierającego", async () => {
    const user = userEvent.setup();
    render(<AppearanceTools />);
    const trigger = screen.getByRole("button", { name: "Wygląd aplikacji" });
    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "Zamknij wygląd" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).toHaveFocus();
  });
  it("kliknięcie poza panelem zamyka go bez usuwania formularza", async () => {
    const user = userEvent.setup();
    render(<><input aria-label="Notatka" defaultValue="Nasze ustalenia" /><AppearanceTools /></>);
    await user.click(screen.getByRole("button", { name: "Wygląd aplikacji" }));
    await user.click(screen.getByRole("textbox", { name: "Notatka" }));
    expect(screen.queryByRole("region", { name: "Wygląd aplikacji" })).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Notatka" })).toHaveValue("Nasze ustalenia");
  });
});
