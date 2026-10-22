import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, Upload } from "lucide-react";
import { useState } from "react";
import { FileTrigger } from "react-aria-components";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { Sheet } from "../../components/Overlay";
import { Notice } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { plural } from "../../lib/format";
import { keys } from "./data";

type ImportOut = components["schemas"]["ImportOut"];

/** Znacznik kolejności bajtów (BOM) — zapisany kodem, żeby nie był niewidocznym znakiem w źródle. */
const BOM = String.fromCharCode(0xfeff);

/** Polskie (i angielskie) nagłówki kolumn → nazwy oczekiwane przez API. */
const HEADER_ALIASES: Record<string, string> = {
  household: "household",
  zaproszenie: "household",
  rodzina: "household",
  gospodarstwo: "household",
  first_name: "first_name",
  imie: "first_name",
  last_name: "last_name",
  nazwisko: "last_name",
  side: "side",
  strona: "side",
  age_group: "age_group",
  wiek: "age_group",
  dietary: "dietary",
  dieta: "dietary",
  accommodation: "accommodation",
  nocleg: "accommodation",
  transport: "transport",
  dojazd: "transport",
  email: "email",
  "e-mail": "email",
  mail: "email",
  phone: "phone",
  telefon: "phone",
  language: "language",
  jezyk: "language",
};

const strip = (s: string) =>
  s
    .trim()
    .replace(/^"|"$/g, "")
    .toLocaleLowerCase("pl-PL")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/ł/g, "l");

/** Zamienia nazwy kolumn w pierwszym wierszu; nieznane kolumny zostają (API je pomija). */
export function normalizeHeaders(csv: string): string {
  const text = csv.startsWith(BOM) ? csv.slice(1) : csv;
  const end = text.search(/\r?\n/);
  const first = end === -1 ? text : text.slice(0, end);
  const rest = end === -1 ? "" : text.slice(end);
  const sep = first.split(";").length >= first.split(",").length ? ";" : ",";
  const mapped = first
    .split(sep)
    .map((h) => HEADER_ALIASES[strip(h)] ?? h.trim())
    .join(sep);
  return mapped + rest;
}

/** Excel w Polsce zapisuje CSV często jako Windows-1250; UTF-8 próbujemy najpierw (bez strat). */
export function decodeCsv(bytes: ArrayBuffer): string {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return new TextDecoder("windows-1250").decode(bytes);
  }
}

const TEMPLATE =
  "Zaproszenie;Imię;Nazwisko;Strona;Wiek;Dieta;Nocleg;Transport;E-mail;Telefon\r\n" +
  "Państwo Kowalscy;Anna;Kowalska;Panna młoda;dorosły;;tak;nie;anna@example.com;600100200\r\n" +
  "Państwo Kowalscy;Piotr;Kowalski;Panna młoda;dorosły;wegetariańska;tak;nie;;\r\n" +
  "Państwo Kowalscy;Zosia;Kowalska;Panna młoda;dziecko;;tak;nie;;\r\n";

function downloadTemplate() {
  // BOM: Excel rozpozna UTF-8 i polskie znaki.
  const url = URL.createObjectURL(new Blob([BOM, TEMPLATE], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "goscie-wzor.csv";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export function GuestImportSheet({ weddingId, isOpen, onClose }: { weddingId: string; isOpen: boolean; onClose: () => void }) {
  return (
    <Sheet title="Import gości z pliku" isOpen={isOpen} onOpenChange={(o) => !o && onClose()}>
      {isOpen && <ImportFlow weddingId={weddingId} onClose={onClose} />}
    </Sheet>
  );
}

function ImportFlow({ weddingId, onClose }: { weddingId: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [csv, setCsv] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [preview, setPreview] = useState<ImportOut | null>(null);

  const run = useMutation({
    mutationFn: ({ text, dryRun }: { text: string; dryRun: boolean }) =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/guests/import", {
          params: { path: { wedding_id: weddingId } },
          body: { csv: text, dry_run: dryRun },
        }),
      ),
    onSuccess: async (r) => {
      if (r.dry_run) {
        setPreview(r);
        return;
      }
      await Promise.all(
        [keys.households(weddingId), keys.guestStats(weddingId), keys.summary(weddingId)].map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      );
      onClose();
      toast(plural(r.guests_created, { one: "Zaimportowano # osobę", few: "Zaimportowano # osoby", many: "Zaimportowano # osób", other: "Zaimportowano # osoby" }));
    },
  });

  const ok = preview && preview.errors.length === 0 && preview.guests_created > 0;

  return (
    <div className="form-stack">
      <p className="text-secondary">
        Plik CSV z Excela lub Arkuszy Google, jeden wiersz = jedna osoba. Wymagane kolumny: <strong>Zaproszenie</strong> i{" "}
        <strong>Imię</strong>. Osoby z tą samą nazwą zaproszenia trafią do jednej rodziny.
      </p>
      <Button variant="text" icon={<Download aria-hidden size={18} />} onPress={downloadTemplate}>
        Pobierz wzór pliku
      </Button>
      <FileTrigger
        acceptedFileTypes={[".csv", ".txt", "text/csv"]}
        onSelect={async (list) => {
          const f = list?.[0];
          if (!f) return;
          run.reset();
          setPreview(null);
          if (f.size > 1_000_000) {
            setFileName(null);
            setCsv(null);
            toast("Plik jest za duży (do 1 MB, ok. 2000 osób).");
            return;
          }
          const text = normalizeHeaders(decodeCsv(await f.arrayBuffer()));
          setFileName(f.name);
          setCsv(text);
          run.mutate({ text, dryRun: true });
        }}
      >
        <Button variant="secondary" icon={<Upload aria-hidden size={20} />}>
          {fileName ? "Wybierz inny plik" : "Wybierz plik CSV"}
        </Button>
      </FileTrigger>
      {fileName && <p className="text-secondary">{fileName}</p>}

      {run.isError && (
        <Notice tone="error" live>
          {userMessage(run.error)}
        </Notice>
      )}
      {preview && preview.errors.length > 0 && (
        <Notice tone="error" title="Popraw plik i wybierz go ponownie" live>
          <ul className="conflict-list">
            {preview.errors.slice(0, 10).map((e) => (
              <li key={e.row}>
                Wiersz {e.row}: {e.message}
              </li>
            ))}
          </ul>
          {preview.errors.length > 10 && <p>…i {preview.errors.length - 10} kolejnych.</p>}
        </Notice>
      )}
      {ok && (
        <Notice tone="info" title="Podgląd" live>
          {plural(preview.guests_created, { one: "# osoba", few: "# osoby", many: "# osób", other: "# osoby" })} w{" "}
          {plural(preview.households_created + preview.households_reused, {
            one: "# zaproszeniu",
            few: "# zaproszeniach",
            many: "# zaproszeniach",
            other: "# zaproszeniach",
          })}
          {preview.households_reused > 0 && ` (w tym ${preview.households_reused} już istniejących — osoby zostaną do nich dopisane)`}.
        </Notice>
      )}
      {ok && (
        <Button block pending={run.isPending && run.variables?.dryRun === false} onPress={() => run.mutate({ text: csv!, dryRun: false })}>
          Importuj
        </Button>
      )}
    </div>
  );
}
