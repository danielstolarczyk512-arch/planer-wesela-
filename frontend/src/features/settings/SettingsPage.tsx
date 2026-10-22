import { Checkbox } from "../../components/Field";
import { AccountSection } from "./AccountSection";
import { Segmented } from "../../components/Segmented";
import { Card } from "../../components/Surface";
import { setReduceMotion, setTheme, usePreferences, type ThemeMode } from "../../lib/preferences";

const THEMES: { value: ThemeMode; label: string }[] = [
  { value: "system", label: "Systemowy" },
  { value: "light", label: "Jasny" },
  { value: "dark", label: "Ciemny" },
];

export function SettingsPage() {
  const prefs = usePreferences();
  return (
    <main className="page enter-detail" aria-labelledby="settings-h">
      <h1 id="settings-h">Ustawienia</h1>
      <AccountSection />
      <h2>Wygląd</h2>
      <Card>
        <div style={{ display: "grid", gap: "var(--wp-space-4)" }}>
          <Segmented label="Motyw" value={prefs.theme} options={THEMES} onChange={setTheme} />
          <p className="text-secondary">
            Systemowy: jasny w dzień, ciemny wieczorem, zgodnie z ustawieniem telefonu.
          </p>
          <Checkbox isSelected={prefs.reduceMotion} onChange={setReduceMotion}>
            Ogranicz animacje
          </Checkbox>
          <p className="text-secondary">
            Bez przesuwania i powiększania elementów. Działa też ustawienie systemowe telefonu.
          </p>
        </div>
      </Card>
    </main>
  );
}
