import { beforeEach, describe, expect, it, vi } from "vitest";

describe("preferencje wyglądu", () => {
  beforeEach(() => { localStorage.clear(); vi.resetModules(); });
  it("przywraca motyw biało-złoty po odświeżeniu", async () => {
    localStorage.setItem("wp.theme", "gold");
    await import("./preferences");
    expect(document.documentElement.dataset.theme).toBe("gold");
  });
  it("bez zapisanego wyboru: motyw Romantyczny", async () => {
    await import("./preferences");
    expect(document.documentElement.dataset.theme).toBe("romantic");
  });
  it("zmienia motyw bez usuwania wpisanych danych", async () => {
    const { setTheme } = await import("./preferences");
    const input = document.createElement("input");
    input.value = "Niezapisany formularz";
    document.body.append(input);
    setTheme("gold");
    expect(localStorage.getItem("wp.theme")).toBe("gold");
    expect(document.documentElement.dataset.theme).toBe("gold");
    expect(input.value).toBe("Niezapisany formularz");
    input.remove();
    setTheme("system");
    expect(localStorage.getItem("wp.theme")).toBe("system");
    setTheme("romantic");
    expect(localStorage.getItem("wp.theme")).toBeNull();
  });
});
