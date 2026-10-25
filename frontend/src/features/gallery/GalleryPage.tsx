import { useState } from "react";

import { Button } from "../../components/Button";
import { DateField } from "../../components/DateField";
import { AmountField, Checkbox, PasswordField, TextField } from "../../components/Field";
import { ConfirmDialog, Sheet } from "../../components/Overlay";
import { Segmented } from "../../components/Segmented";
import { Card, EmptyState, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatMoney, plural } from "../../lib/format";
import { setTheme, THEME_OPTIONS, usePreferences, type ThemeMode } from "../../lib/preferences";
import "./gallery.css";

/** Katalog komponentów (tylko w trybie deweloperskim). Dane fikcyjne. */
export function GalleryPage() {
  const prefs = usePreferences();
  const toast = useToast();
  const [dialog, setDialog] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [note, setNote] = useState("");
  const [amount, setAmount] = useState<string | null>("5000.00");
  const [done, setDone] = useState(false);

  return (
    <main className="page gallery">
      <div>
        <p className="overline">Dane fikcyjne · tryb deweloperski</p>
        <h1>Komponenty</h1>
      </div>
      <Segmented<ThemeMode>
        label="Motyw"
        value={prefs.theme}
        options={THEME_OPTIONS}
        onChange={setTheme}
      />

      <section className="gallery__section" aria-labelledby="g-buttons">
        <h2 id="g-buttons">Przyciski</h2>
        <div className="gallery__row">
          <Button>Zapisz</Button>
          <Button variant="secondary">Anuluj</Button>
          <Button variant="danger">Usuń</Button>
          <Button variant="text">Cały plan</Button>
          <Button pending>Zapisywanie</Button>
          <Button isDisabled>Niedostępne</Button>
        </div>
      </section>

      <section className="gallery__section" aria-labelledby="g-fields">
        <h2 id="g-fields">Pola</h2>
        <TextField label="Nazwa usługodawcy" description="Tak, jak na umowie." />
        <TextField label="E-mail kontaktowy" type="email" error="Wpisz adres e-mail, np. sala@example.com." value="sala@" />
        <PasswordField label="Hasło" />
        <AmountField label="Zadatek" description="Wpisz z przecinkiem lub kropką." value={amount} onChange={setAmount} />
        <p className="text-secondary num">Wartość dla API: {amount ?? "brak (brak wyceny)"}</p>
        <DateField label="Termin płatności" />
        <Checkbox isSelected={done} onChange={setDone}>
          Potwierdź liczbę gości
        </Checkbox>
      </section>

      <section className="gallery__section" aria-labelledby="g-status">
        <h2 id="g-status">Statusy i komunikaty</h2>
        <div className="gallery__row">
          <StatusChip tone="success">Potwierdzone</StatusChip>
          <StatusChip tone="warning">Oczekuje</StatusChip>
          <StatusChip tone="error">Po terminie</StatusChip>
          <StatusChip tone="info">Współorganizator</StatusChip>
          <StatusChip tone="neutral">Brak wyceny</StatusChip>
        </div>
        <Notice tone="warning" title="Termin płatności">
          Wymaga uzupełnienia.
        </Notice>
        <Notice tone="error" title="Nie zapisano">
          Brak połączenia — spróbuj ponownie.
        </Notice>
        <Notice tone="info">Dane zapiszą się po Twoim potwierdzeniu.</Notice>
      </section>

      <section className="gallery__section" aria-labelledby="g-format">
        <h2 id="g-format">Formatowanie</h2>
        <Card>
          <ul className="gallery__list num">
            <li>{formatMoney({ amount: "5000.00", currency: "PLN" })}</li>
            <li>{formatMoney({ amount: "1250000.50", currency: "PLN" })}</li>
            <li>{formatMoney(null)}</li>
            {[1, 3, 5, 22].map((n) => (
              <li key={n}>{plural(n, { one: "Zostało # zadanie", few: "Zostały # zadania", many: "Zostało # zadań", other: "Zostało # zadania" })}</li>
            ))}
          </ul>
        </Card>
      </section>

      <section className="gallery__section" aria-labelledby="g-overlays">
        <h2 id="g-overlays">Dialog, panel, powiadomienie</h2>
        <div className="gallery__row">
          <Button variant="secondary" onPress={() => setDialog(true)}>
            Dialog potwierdzenia
          </Button>
          <Button variant="secondary" onPress={() => setSheet(true)}>
            Dolny panel
          </Button>
          <Button variant="secondary" onPress={() => toast("Oznaczono jako zrobione", () => setDone(false))}>
            Powiadomienie z „Cofnij”
          </Button>
        </div>
      </section>

      <section className="gallery__section" aria-labelledby="g-empty">
        <h2 id="g-empty">Stan pusty i wczytywanie</h2>
        <Card>
          <EmptyState title="Nie ma jeszcze ofert" action={<Button>Dodaj pierwszą ofertę</Button>}>
            Wgraj PDF albo zdjęcie oferty, a pomożemy ją porównać.
          </EmptyState>
        </Card>
        <Skeleton lines={3} delay={0} />
      </section>

      <ConfirmDialog title="Usunąć punkt programu?" isOpen={dialog} onOpenChange={setDialog}>
        <p>„Pierwszy taniec” zniknie z harmonogramu. Tej operacji nie można cofnąć.</p>
        <div className="gallery__row">
          <Button variant="secondary" onPress={() => setDialog(false)}>
            Anuluj
          </Button>
          <Button variant="danger" onPress={() => setDialog(false)}>
            Usuń punkt
          </Button>
        </div>
      </ConfirmDialog>
      <Sheet title="Notatka" isOpen={sheet} onOpenChange={setSheet} isDirty={note !== ""}>
        <TextField label="Treść notatki" value={note} onChange={setNote} />
        <Button block onPress={() => { setNote(""); setSheet(false); }}>
          Zapisz
        </Button>
      </Sheet>
    </main>
  );
}
