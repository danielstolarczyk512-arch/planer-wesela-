/**
 * Kalkulator alkoholu i napojów. Wartości to orientacyjne założenia (każdą można zmienić) —
 * pijemy różnie, więc wynik to punkt wyjścia do rozmowy z salą, nie wyrocznia.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { Button as AriaButton, Disclosure, DisclosurePanel, Heading } from "react-aria-components";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { AmountField, TextField } from "../../components/Field";
import { Card, Notice } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatMoney } from "../../lib/format";
import { keys, useBudgetCategories, useGuestStats } from "./data";

export interface DrinksInput {
  adults: number;
  allGuests: number;
  drinkingShare: number; // 0–100 %
  vodkaPerDrinker: number; // litry
  winePerDrinker: number; // butelki 0,75 l
  softPerGuest: number; // litry
}

/** Liczba butelek/litrów (zaokrąglone w górę) — czysta funkcja do testów. */
export function drinksNeeded(i: DrinksInput): { vodka: number; wine: number; soft: number } {
  const drinkers = Math.ceil((i.adults * i.drinkingShare) / 100);
  return {
    vodka: Math.ceil((drinkers * i.vodkaPerDrinker) / 0.5),
    wine: Math.ceil(drinkers * i.winePerDrinker),
    soft: Math.ceil(i.allGuests * i.softPerGuest),
  };
}

const num = (v: string, fallback: number) => {
  const n = Number(v.replace(",", "."));
  return Number.isFinite(n) && n >= 0 ? n : fallback;
};

export function DrinksCalculator({ weddingId, canWrite }: { weddingId: string; canWrite: boolean }) {
  const stats = useGuestStats(weddingId);
  const categories = useBudgetCategories(weddingId);
  const queryClient = useQueryClient();
  const toast = useToast();
  const [adults, setAdults] = useState<string>("");
  const [share, setShare] = useState("80");
  const [vodka, setVodka] = useState("0,5");
  const [wine, setWine] = useState("0,33");
  const [soft, setSoft] = useState("1,5");
  const [vodkaPrice, setVodkaPrice] = useState<string | null>(null);
  const [winePrice, setWinePrice] = useState<string | null>(null);

  const adultsN = adults.trim() ? num(adults, 0) : (stats.data?.adults ?? 0);
  const all = Math.max(adultsN, (stats.data?.adults ?? 0) + (stats.data?.children ?? 0));
  const need = drinksNeeded({
    adults: adultsN,
    allGuests: all,
    drinkingShare: Math.min(num(share, 80), 100),
    vodkaPerDrinker: num(vodka, 0.5),
    winePerDrinker: num(wine, 0.33),
    softPerGuest: num(soft, 1.5),
  });
  const cost = (vodkaPrice ? Number(vodkaPrice) * need.vodka : 0) + (winePrice ? Number(winePrice) * need.wine : 0);

  const add = useMutation({
    mutationFn: () => {
      const category = categories.data?.find((c) => c.name.startsWith("Sala")) ?? categories.data?.[0];
      if (!category) throw new Error("Brak kategorii budżetu.");
      return unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/budget/items", {
          params: { path: { wedding_id: weddingId } },
          body: {
            category_id: category.id,
            name: `Alkohol (${need.vodka} × wódka 0,5 l, ${need.wine} × wino)`,
            cost_mode: "fixed",
            planned: { amount: cost.toFixed(2), currency: "PLN" },
            status: "planned",
            indexation: "none",
          },
        }),
      );
    },
    onSuccess: async () => {
      await Promise.all([keys.items(weddingId), keys.budget(weddingId), keys.summary(weddingId)].map((queryKey) => queryClient.invalidateQueries({ queryKey })));
      toast("Dodano wydatek „Alkohol” do budżetu");
    },
  });

  return (
    <Card className="form-stack">
      <Disclosure className="quote__details">
        <Heading level={2} className="household__heading">
          <AriaButton slot="trigger" className="household__trigger">
            <span className="row__body">
              <span>Kalkulator alkoholu i napojów</span>
              <span className="text-secondary">Ile butelek kupić, jeśli alkohol nie jest w pakiecie sali.</span>
            </span>
            <ChevronDown aria-hidden size={20} className="household__chevron" />
          </AriaButton>
        </Heading>
        <DisclosurePanel>
          <div className="form-stack">
            <div className="stat-grid">
              <TextField label="Dorośli goście" inputMode="numeric" value={adults} onChange={setAdults} description={`Z listy: ${stats.data?.adults ?? 0}`} />
              <TextField label="Pijących alkohol (%)" inputMode="numeric" value={share} onChange={setShare} />
            </div>
            <div className="stat-grid">
              <TextField label="Wódka na pijącą osobę (l)" inputMode="decimal" value={vodka} onChange={setVodka} />
              <TextField label="Wino na pijącą osobę (butelki)" inputMode="decimal" value={wine} onChange={setWine} />
            </div>
            <TextField label="Napoje na gościa (l)" inputMode="decimal" value={soft} onChange={setSoft} />
            <ul className="row-list" aria-live="polite">
              <li className="row">
                <span className="row__body">Wódka 0,5 l</span>
                <strong className="num">{need.vodka} szt.</strong>
              </li>
              <li className="row">
                <span className="row__body">Wino 0,75 l</span>
                <strong className="num">{need.wine} szt.</strong>
              </li>
              <li className="row">
                <span className="row__body">Napoje (soki, woda, napoje gazowane)</span>
                <strong className="num">{need.soft} l</strong>
              </li>
            </ul>
            <p className="text-secondary">
              Założenia są orientacyjne — zmieńcie je pod swoich gości. Zapytajcie salę o zwrot nieotwartych butelek i o korkowe.
            </p>
            {canWrite && (
              <>
                <div className="stat-grid">
                  <AmountField label="Cena wódki 0,5 l (opcjonalnie)" value={vodkaPrice} onChange={setVodkaPrice} />
                  <AmountField label="Cena wina (opcjonalnie)" value={winePrice} onChange={setWinePrice} />
                </div>
                {add.isError && (
                  <Notice tone="error" live>
                    {userMessage(add.error)}
                  </Notice>
                )}
                <Button variant="secondary" isDisabled={cost <= 0} pending={add.isPending} onPress={() => add.mutate()}>
                  {cost > 0 ? `Dodaj do budżetu: ${formatMoney({ amount: cost.toFixed(2), currency: "PLN" })}` : "Wpiszcie ceny, aby dodać do budżetu"}
                </Button>
              </>
            )}
          </div>
        </DisclosurePanel>
      </Disclosure>
    </Card>
  );
}
