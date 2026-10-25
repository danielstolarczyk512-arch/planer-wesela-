import { useEffect, useRef, useState } from "react";
import { ArrowUp, Palette, X } from "lucide-react";
import { Segmented } from "./Segmented";
import { Checkbox } from "./Field";
import { setTheme, setReduceMotion, usePreferences, motionReduced, THEME_OPTIONS } from "../lib/preferences";

/** Podgląd motywów bez opuszczania ekranu i utraty wpisanych danych. */
export function AppearanceTools() {
  const prefs = usePreferences();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const scroll = () => setScrolled(window.scrollY > 500);
    scroll();
    window.addEventListener("scroll", scroll, { passive: true });
    return () => window.removeEventListener("scroll", scroll);
  }, []);
  useEffect(() => {
    if (!open) return;
    container.current?.querySelector<HTMLButtonElement>("#appearance-panel button")?.focus();
    const outside = (e: PointerEvent) => {
      if (!container.current?.contains(e.target as Node)) setOpen(false);
    };
    const escape = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setOpen(false); trigger.current?.focus(); }
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);
  return <div className="appearance-tools" ref={container}>
    {open && <section id="appearance-panel" className="appearance-panel" aria-label="Wygląd aplikacji">
      <div className="appearance-panel__head"><h2>Wasz styl, Wasz dzień</h2>
        <button type="button" className="appearance-icon" aria-label="Zamknij wygląd" onClick={() => { setOpen(false); trigger.current?.focus(); }}><X size={20} aria-hidden="true" /></button>
      </div>
      <p className="text-secondary">Przymierz każdy styl. Wybór zapamiętamy na tym urządzeniu.</p>
      <Segmented label="Styl aplikacji" value={prefs.theme} options={THEME_OPTIONS} onChange={setTheme} />
      <Checkbox isSelected={prefs.reduceMotion} onChange={setReduceMotion}>Ogranicz animacje</Checkbox>
    </section>}
    <div className="appearance-tools__buttons">
      {scrolled && <button type="button" className="appearance-icon" aria-label="Wróć na górę" onClick={() => {
        window.scrollTo({ top: 0, behavior: motionReduced() ? "instant" : "smooth" });
        const heading = document.querySelector<HTMLElement>("main h1, main h2");
        if (heading) { heading.setAttribute("tabindex", "-1"); heading.focus({ preventScroll: true }); }
      }}><ArrowUp size={20} aria-hidden="true" /></button>}
      <button type="button" className="appearance-icon" ref={trigger} aria-label="Wygląd aplikacji" aria-expanded={open} aria-controls={open ? "appearance-panel" : undefined} onClick={() => setOpen(!open)}><Palette size={20} aria-hidden="true" /></button>
    </div>
  </div>;
}
