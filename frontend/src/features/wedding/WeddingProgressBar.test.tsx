import { render, screen } from "@testing-library/react";
import { StrictMode } from "react";
import { describe, expect, it } from "vitest";

import { exactShare, FINALE_TEXT, percentLabel, WeddingProgressBar } from "./WeddingProgressBar";

const bar = () => screen.getByRole("progressbar", { name: "Postęp przygotowań" });
const ring = (c: HTMLElement) => c.querySelector(".wpb__icon img");
const coupleOn = (c: HTMLElement) => c.querySelector(".wpb__couple--on");

describe("liczenie postępu", () => {
  it("0/0 to 0%, 13/26 to dokładnie 50%, 25/26 nie pokazuje 100%", () => {
    expect(percentLabel(0, 0, false)).toBe(0);
    expect(exactShare(13, 26)).toBe(50);
    expect(percentLabel(13, 26, false)).toBe(50);
    expect(percentLabel(1, 26, false)).toBe(4);
    expect(percentLabel(999, 1000, false)).toBe(99);
    expect(percentLabel(26, 26, true)).toBe(100);
  });
});

describe("WeddingProgressBar", () => {
  it("0 z 0 i 0 z 26: pierścionek przy lewym końcu, bez finału", () => {
    for (const total of [0, 26]) {
      const { container, unmount } = render(<WeddingProgressBar completed={0} total={total} />);
      expect(bar()).toHaveAttribute("aria-valuenow", "0");
      expect(ring(container)).not.toBeNull();
      expect(coupleOn(container)).toBeNull();
      expect(container.querySelector<HTMLElement>(".wpb__marker")!.style.left).toBe("0%");
      expect(screen.queryByText(FINALE_TEXT)).not.toBeInTheDocument();
      unmount();
    }
  });

  it("13 z 26: środek paska i etykieta 50%", () => {
    const { container } = render(<WeddingProgressBar completed={13} total={26} />);
    expect(bar()).toHaveAttribute("aria-valuenow", "50");
    expect(bar()).toHaveAttribute("aria-valuetext", "13 z 26 zadań");
    expect(container.querySelector<HTMLElement>(".wpb__fill")!.style.width).toBe("50%");
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("25 z 26: nadal pierścionek, bez finału i bez 100%", () => {
    const { container } = render(<WeddingProgressBar completed={25} total={26} />);
    expect(ring(container)).not.toBeNull();
      expect(coupleOn(container)).toBeNull();
    expect(bar()).toHaveAttribute("aria-valuenow", "96");
    expect(screen.queryByText(FINALE_TEXT)).not.toBeInTheDocument();
  });

  it("26 z 26: para młoda i komunikat; przy pierwszym renderze bez konfetti", () => {
    const { container } = render(
      <StrictMode>
        <WeddingProgressBar completed={26} total={26} />
      </StrictMode>,
    );
    expect(ring(container)).toBeNull();
    expect(coupleOn(container)).not.toBeNull();
    expect(screen.getByText(FINALE_TEXT)).toBeInTheDocument();
    expect(container.querySelector(".wpb__burst")).toBeNull();
    expect(bar()).toHaveAttribute("aria-valuenow", "100");
  });

  it("przejście 25 → 26 uruchamia konfetti raz; cofnięcie je usuwa i przywraca pierścionek", () => {
    const { container, rerender } = render(
      <StrictMode>
        <WeddingProgressBar completed={25} total={26} />
      </StrictMode>,
    );
    rerender(
      <StrictMode>
        <WeddingProgressBar completed={26} total={26} />
      </StrictMode>,
    );
    expect(container.querySelectorAll(".wpb__burst")).toHaveLength(1);
    expect(container.querySelectorAll(".wpb__bit").length).toBeGreaterThan(8);
    // odświeżenie z tymi samymi danymi nie powtarza efektu
    rerender(
      <StrictMode>
        <WeddingProgressBar completed={26} total={26} />
      </StrictMode>,
    );
    expect(container.querySelectorAll(".wpb__burst")).toHaveLength(1);
    rerender(
      <StrictMode>
        <WeddingProgressBar completed={25} total={26} />
      </StrictMode>,
    );
    expect(container.querySelector(".wpb__burst")).toBeNull();
    expect(ring(container)).not.toBeNull();
      expect(coupleOn(container)).toBeNull();
    expect(screen.queryByText(FINALE_TEXT)).not.toBeInTheDocument();
    rerender(
      <StrictMode>
        <WeddingProgressBar completed={26} total={26} />
      </StrictMode>,
    );
    expect(container.querySelector(".wpb__burst")).not.toBeNull();
  });

  it("zapis niepotwierdzony: brak finału, po potwierdzeniu finał z konfetti", () => {
    const { container, rerender } = render(<WeddingProgressBar completed={25} total={26} />);
    rerender(<WeddingProgressBar completed={26} total={26} settled={false} />);
    expect(screen.queryByText(FINALE_TEXT)).not.toBeInTheDocument();
    expect(bar()).toHaveAttribute("aria-valuenow", "99");
    rerender(<WeddingProgressBar completed={26} total={26} settled />);
    expect(screen.getByText(FINALE_TEXT)).toBeInTheDocument();
    expect(container.querySelector(".wpb__burst")).not.toBeNull();
  });

  it("ograniczenie ruchu: finał bez konfetti", () => {
    document.documentElement.classList.add("reduce-motion");
    try {
      const { container, rerender } = render(<WeddingProgressBar completed={25} total={26} />);
      rerender(<WeddingProgressBar completed={26} total={26} />);
      expect(screen.getByText(FINALE_TEXT)).toBeInTheDocument();
      expect(container.querySelector(".wpb__burst")).toBeNull();
    } finally {
      document.documentElement.classList.remove("reduce-motion");
    }
  });
});
