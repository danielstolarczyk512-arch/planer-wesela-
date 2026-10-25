import { useSearchParams } from "react-router";

import { Segmented } from "../../components/Segmented";
import { MONEY_SECTIONS, SectionNav } from "../wedding/SectionNav";
import { useWeddingId } from "../wedding/data";
import { CandidatesPanel } from "./CandidatesPanel";
import { CatalogPanel } from "./CatalogPanel";
import { ChatPanel } from "./ChatPanel";
import { InquiriesPanel } from "./InquiriesPanel";
import "./assistant.css";

const TABS = [
  { value: "rozmowa", label: "Rozmowa" },
  { value: "katalog", label: "Katalog" },
  { value: "kandydaci", label: "Kandydaci" },
  { value: "zapytania", label: "Zapytania" },
] as const;
type Tab = (typeof TABS)[number]["value"];

/** Dobór usługodawców: rozmowa z asystentem, katalog z filtrami, lista kandydatów i zapytania do firm. */
export function AssistantView() {
  const id = useWeddingId();
  const [params, setParams] = useSearchParams();
  const raw = params.get("zakladka");
  const tab: Tab = TABS.some((t) => t.value === raw) ? (raw as Tab) : "rozmowa";
  return (
    <main className="page enter-tab" aria-labelledby="assistant-h">
      <SectionNav label="Budżet" sections={MONEY_SECTIONS} />
      <div className="view-head">
        <div>
          <h1 id="assistant-h">Dobór firm</h1>
          <p className="text-secondary">Katalog firm ze źródłami cen, asystent, lista kandydatów i prywatne zapytania.</p>
        </div>
      </div>
      <Segmented
        label="Widok"
        variant="chips"
        value={tab}
        options={TABS.map((t) => ({ value: t.value, label: t.label }))}
        onChange={(v) => setParams({ zakladka: v }, { replace: true })}
      />
      {tab === "rozmowa" && <ChatPanel id={id} />}
      {tab === "katalog" && <CatalogPanel id={id} />}
      {tab === "kandydaci" && <CandidatesPanel id={id} />}
      {tab === "zapytania" && <InquiriesPanel id={id} />}
    </main>
  );
}
