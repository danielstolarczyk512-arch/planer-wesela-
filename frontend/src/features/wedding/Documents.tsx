import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Plus, Sparkles, Upload } from "lucide-react";
import { useEffect, useState } from "react";
import { Button as AriaButton, FileTrigger, Form, Input, Label, SearchField, Text } from "react-aria-components";
import { Link, useNavigate } from "react-router";

import { api, authFetch, unwrap } from "../../api/client";
import { downloadAuthorized } from "../../api/download";
import { ApiError, toApiError, userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { TextField } from "../../components/Field";
import { ConfirmDialog, Sheet } from "../../components/Overlay";
import { Select } from "../../components/Select";
import { Card, EmptyState, Notice, Skeleton, StatusChip, type Tone } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { useCanWrite, useWeddingId } from "./data";
import { DocumentText } from "./DocumentText";
import { useVendors, vendorKeys } from "./vendors";

export type Doc = components["schemas"]["DocumentOut"];
type DocKind = Doc["kind"];
type AiRun = components["schemas"]["AiRunOut"];

export const docKeys = {
  all: (id: string) => ["wedding", id, "documents"] as const,
  run: (id: string, runId: string) => ["wedding", id, "ai-runs", runId] as const,
};

const KINDS: { id: DocKind; label: string }[] = [
  { id: "offer", label: "Oferta" },
  { id: "contract", label: "Umowa" },
  { id: "invoice", label: "Faktura / rachunek" },
  { id: "payment_proof", label: "Potwierdzenie wpłaty" },
  { id: "other", label: "Inny" },
];
// Typy MIME obok rozszerzeń: przy nich Safari na iPhonie zamienia zdjęcie HEIC z galerii na JPEG.
const ACCEPT = [
  ".pdf",
  "application/pdf",
  ".docx",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ".jpg",
  ".jpeg",
  "image/jpeg",
  ".png",
  "image/png",
];
export const HEIC_MESSAGE =
  "Zdjęcie jest w formacie HEIC (domyślnym w iPhonie). Wybierz je z galerii telefonu przyciskiem „Wybierz plik” — iPhone sam zapisze je jako JPG — albo wyślij jako JPG lub PDF.";
export const isHeicName = (name: string) => /\.(heic|heif)$/i.test(name);
const MAX_BYTES = 20 * 1024 * 1024;

const TEXT_STATUS: Record<string, { label: string; tone: Tone }> = {
  pending: { label: "Czeka na odczyt", tone: "neutral" },
  processing: { label: "Odczytujemy tekst", tone: "info" },
  done: { label: "Tekst gotowy", tone: "success" },
  failed: { label: "Nie odczytano", tone: "warning" },
};

/** Skan antywirusowy ma pierwszeństwo: plik niesprawdzony lub zablokowany nie jest odczytywany. */
const SCAN_STATUS: Record<string, { label: string; tone: Tone } | undefined> = {
  pending: { label: "Sprawdzanie pliku…", tone: "info" },
  infected: { label: "Zablokowany", tone: "error" },
};

export function useDocuments(id: string) {
  return useQuery({
    queryKey: docKeys.all(id),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/documents", { params: { path: { wedding_id: id } }, signal })),
    // Tekst wyodrębniany w tle: odświeżamy, dopóki coś czeka.
    refetchInterval: (q) =>
      q.state.data?.some((d) => d.versions.some((v) => v.scan_status === "pending" || v.text_status === "pending" || v.text_status === "processing"))
        ? 3000
        : false,
  });
}

/** „1,2 MB” */
export function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toLocaleString("pl-PL", { maximumFractionDigits: 1 })} MB`;
}

export function DocumentsView() {
  const id = useWeddingId();
  const docs = useDocuments(id);
  const vendors = useVendors(id);
  const canWrite = useCanWrite(id);
  const [uploading, setUploading] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const vendorName = (vendorId: string | null) => vendors.data?.find((v) => v.id === vendorId)?.name;

  return (
    <main className="page enter-detail" aria-labelledby="docs-h">
      <div className="view-head">
        <div>
          <Link to={`/w/${id}/wiecej`} viewTransition className="wp-button wp-button--text back-link">
            ← Więcej
          </Link>
          <h1 id="docs-h">Dokumenty</h1>
          <p className="text-secondary">Oferty, umowy i rachunki w jednym miejscu.</p>
        </div>
        {canWrite && (docs.data?.length ?? 0) > 0 && (
          <Button variant="secondary" icon={<Plus aria-hidden size={20} />} onPress={() => setUploading(true)}>
            Dodaj dokument
          </Button>
        )}
      </div>
      {docs.isPending && <Skeleton lines={5} />}
      {docs.isError && (
        <Notice tone="error" live>
          {userMessage(docs.error)}
        </Notice>
      )}
      {docs.data?.length === 0 && (
        <EmptyState
          title="Brak dokumentów"
          action={canWrite ? <Button onPress={() => setUploading(true)}>Dodaj pierwszy</Button> : undefined}
        >
          Wgrajcie ofertę w PDF — odczytamy ceny i warunki do sprawdzenia, a potem porównacie ją z innymi.
        </EmptyState>
      )}
      {(docs.data?.length ?? 0) > 0 && <DocumentSearch weddingId={id} vendorName={vendorName} onOpen={setOpen} />}
      {(docs.data?.length ?? 0) > 0 && (
        <Card>
          <DocumentList docs={docs.data!} vendorName={vendorName} onOpen={setOpen} />
        </Card>
      )}
      <UploadSheet weddingId={id} vendorId={null} isOpen={uploading} onClose={() => setUploading(false)} />
      <DocumentSheet weddingId={id} doc={docs.data?.find((d) => d.id === open) ?? null} onClose={() => setOpen(null)} />
    </main>
  );
}

/** Szukaj w tytułach, nazwach plików i odczytanym tekście (bez polskich znaków, z odmianą, z fragmentem). */
function DocumentSearch({
  weddingId,
  vendorName,
  onOpen,
}: {
  weddingId: string;
  vendorName: (vendorId: string | null) => string | undefined;
  onOpen: (id: string) => void;
}) {
  const [text, setText] = useState("");
  const [query, setQuery] = useState("");
  // Zapytanie po krótkiej przerwie w pisaniu (bez żądania na każdą literę).
  useEffect(() => {
    const t = window.setTimeout(() => setQuery(text.trim()), 300);
    return () => window.clearTimeout(t);
  }, [text]);
  const hits = useQuery({
    queryKey: ["wedding", weddingId, "documents", "search", query],
    queryFn: ({ signal }) =>
      unwrap(api.GET("/api/v1/weddings/{wedding_id}/documents/search", { params: { path: { wedding_id: weddingId }, query: { q: query } }, signal })),
    enabled: query.length >= 2,
  });
  return (
    <section className="form-stack" aria-label="Wyszukiwanie dokumentów">
      <SearchField className="wp-field" value={text} onChange={setText}>
        <Label className="wp-field__label">Szukaj w dokumentach</Label>
        <Input className="wp-field__input" placeholder="np. zadatek, nadgodziny, korkowe" />
        <Text slot="description" className="wp-field__description">
          Szukamy w tytułach, nazwach plików i w odczytanej treści (także skanów).
        </Text>
      </SearchField>
      {query.length >= 2 && hits.data && (
        <Card>
          {hits.data.length === 0 ? (
            <p className="text-secondary">Nic nie znaleźliśmy dla „{query}”.</p>
          ) : (
            <ul className="row-list" aria-live="polite">
              {hits.data.map((h) => (
                <li key={h.document_id} className="row">
                  <FileText aria-hidden size={22} strokeWidth={1.75} />
                  <AriaButton className="row-edit" onPress={() => onOpen(h.document_id)}>
                    <span className="row__title">{h.title}</span>
                    <span className="text-secondary">
                      {[vendorName(h.vendor_id), h.page ? `strona ${h.page}` : null].filter(Boolean).join(" · ")}
                    </span>
                    {h.snippet && <span className="search-snippet">{h.snippet}</span>}
                  </AriaButton>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </section>
  );
}

export function DocumentList({
  docs,
  vendorName,
  onOpen,
}: {
  docs: Doc[];
  vendorName?: (vendorId: string | null) => string | undefined;
  onOpen: (id: string) => void;
}) {
  return (
    <ul className="row-list">
      {docs.map((d) => {
        const v = d.versions.find((x) => x.id === d.current_version_id) ?? d.versions[0];
        const st = v ? (SCAN_STATUS[v.scan_status] ?? TEXT_STATUS[v.text_status]) : null;
        return (
          <li key={d.id} className="row">
            <FileText aria-hidden size={22} strokeWidth={1.75} />
            <AriaButton className="row-edit" onPress={() => onOpen(d.id)}>
              <span className="row__title">{d.title}</span>
              <span className="text-secondary">
                {[KINDS.find((k) => k.id === d.kind)?.label, vendorName?.(d.vendor_id), v && formatSize(v.size_bytes)].filter(Boolean).join(" · ")}
              </span>
            </AriaButton>
            {st && <StatusChip tone={st.tone}>{st.label}</StatusChip>}
          </li>
        );
      })}
    </ul>
  );
}

/* --------------------------------------------------------------------------- wgrywanie */

export function UploadSheet({
  weddingId,
  vendorId,
  isOpen,
  onClose,
}: {
  weddingId: string;
  vendorId: string | null;
  isOpen: boolean;
  onClose: () => void;
}) {
  return (
    <Sheet title="Nowy dokument" isOpen={isOpen} onOpenChange={(o) => !o && onClose()}>
      {isOpen && <UploadForm weddingId={weddingId} vendorId={vendorId} onClose={onClose} />}
    </Sheet>
  );
}

function UploadForm({ weddingId, vendorId, onClose }: { weddingId: string; vendorId: string | null; onClose: () => void }) {
  const vendors = useVendors(weddingId);
  const queryClient = useQueryClient();
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [kind, setKind] = useState<string>(vendorId ? "offer" : "other");
  const [vendor, setVendor] = useState<string>(vendorId ?? "__none__");
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: async () => {
      const form = new FormData();
      form.append("file", file!);
      form.append("kind", kind);
      if (title.trim()) form.append("title", title.trim());
      if (vendor !== "__none__") form.append("vendor_id", vendor);
      const response = await authFetch(
        new Request(`${location.origin}/api/v1/weddings/${weddingId}/documents`, { method: "POST", body: form }),
      );
      if (!response.ok) throw await toApiError(response);
      return (await response.json()) as Doc;
    },
    onSuccess: async (d) => {
      await queryClient.invalidateQueries({ queryKey: docKeys.all(weddingId) });
      onClose();
      toast(`Wgrano „${d.title}” — odczytujemy tekst`);
    },
    onError: (e) => setError(e instanceof ApiError && e.status === 413 ? "Plik jest za duży (do 20 MB)." : `Nie wgrano. ${userMessage(e)}`),
  });

  return (
    <Form
      className="form-stack"
      onSubmit={(e) => {
        e.preventDefault();
        if (!file) {
          setError("Wybierz plik.");
          return;
        }
        upload.mutate();
      }}
    >
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      <div className="form-stack">
        <FileTrigger
          acceptedFileTypes={ACCEPT}
          onSelect={(list) => {
            const f = list?.[0] ?? null;
            setError(null);
            if (f && f.size > MAX_BYTES) {
              setError("Plik jest za duży (do 20 MB).");
              return;
            }
            if (f && isHeicName(f.name)) {
              setError(HEIC_MESSAGE);
              return;
            }
            setFile(f);
            if (f && !title.trim()) setTitle(f.name.replace(/\.[^.]+$/, ""));
          }}
        >
          <Button variant="secondary" icon={<Upload aria-hidden size={20} />}>
            {file ? "Zmień plik" : "Wybierz plik"}
          </Button>
        </FileTrigger>
        <p className="text-secondary" aria-live="polite">
          {file ? `${file.name} · ${formatSize(file.size)}` : "PDF, DOCX, JPG lub PNG, do 20 MB."}
        </p>
      </div>
      <TextField label="Tytuł" value={title} onChange={setTitle} />
      <Select label="Rodzaj" options={KINDS} value={kind} onChange={setKind} />
      <Select
        label="Usługodawca"
        options={[{ id: "__none__", label: "Bez przypisania" }, ...(vendors.data ?? []).map((v) => ({ id: v.id, label: v.name }))]}
        value={vendor}
        onChange={setVendor}
      />
      <Button type="submit" block pending={upload.isPending}>
        Wgraj
      </Button>
    </Form>
  );
}

/* ----------------------------------------------------------------------- szczegóły */

export function DocumentSheet({ weddingId, doc, onClose }: { weddingId: string; doc: Doc | null; onClose: () => void }) {
  return (
    <Sheet title={doc?.title ?? "Dokument"} isOpen={!!doc} onOpenChange={(o) => !o && onClose()}>
      {doc && <DocumentDetails key={doc.id} weddingId={weddingId} doc={doc} onClose={onClose} />}
    </Sheet>
  );
}

function DocumentDetails({ weddingId, doc, onClose }: { weddingId: string; doc: Doc; onClose: () => void }) {
  const canWrite = useCanWrite(weddingId);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const v = doc.versions.find((x) => x.id === doc.current_version_id) ?? doc.versions[0];

  const download = useMutation({
    mutationFn: () =>
      downloadAuthorized(`/api/v1/weddings/${weddingId}/documents/${doc.id}/versions/${v!.id}/file`, v!.original_filename),
    onError: (e) => setError(`Nie pobrano. ${userMessage(e)}`),
  });

  const retry = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/documents/{document_id}/versions/{version_id}/retry", {
          params: { path: { wedding_id: weddingId, document_id: doc.id, version_id: v!.id } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: docKeys.all(weddingId) }),
    onError: (e) => setError(userMessage(e)),
  });

  const analyze = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/documents/{document_id}/versions/{version_id}/analyze", {
          params: { path: { wedding_id: weddingId, document_id: doc.id, version_id: v!.id } },
          body: { vendor_id: doc.vendor_id! },
        }),
      ),
    onSuccess: (run) => {
      setError(null);
      setRunId(run.id);
    },
    onError: (e) => setError(userMessage(e)),
  });

  const run = useQuery({
    queryKey: docKeys.run(weddingId, runId ?? ""),
    enabled: !!runId,
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/weddings/{wedding_id}/ai-runs/{run_id}", {
          params: { path: { wedding_id: weddingId, run_id: runId! } },
          signal,
        }),
      ),
    refetchInterval: (q) => (q.state.data && !["queued", "running"].includes(q.state.data.status) ? false : 3000),
  });

  // Szkic oferty gotowy: lista ofert usługodawcy ma go pokazać.
  const succeeded = run.data?.status === "succeeded";
  useEffect(() => {
    if (succeeded) void queryClient.invalidateQueries({ queryKey: vendorKeys.offers(weddingId) });
  }, [succeeded, queryClient, weddingId]);

  const remove = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE("/api/v1/weddings/{wedding_id}/documents/{document_id}", {
          params: { path: { wedding_id: weddingId, document_id: doc.id } },
        }),
      ),
    onSuccess: async () => {
      setConfirmDelete(false);
      await queryClient.invalidateQueries({ queryKey: docKeys.all(weddingId) });
      onClose();
      toast(`Usunięto „${doc.title}”`);
    },
    onError: (e) => {
      setConfirmDelete(false);
      setError(`Nie usunięto. ${userMessage(e)}`);
    },
  });

  const canAnalyze = canWrite && v?.text_status === "done" && (doc.kind === "offer" || doc.kind === "contract");

  return (
    <div className="form-stack">
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      {v && (
        <p className="text-secondary">
          {v.original_filename} · {formatSize(v.size_bytes)}
          {v.page_count ? ` · stron: ${v.page_count}` : ""}
          {v.ocr_used ? " · skan (OCR)" : ""}
        </p>
      )}
      {v?.scan_status === "pending" && (
        <Notice tone="info" title="Sprawdzanie pliku…">
          Każdy wgrany plik sprawdzamy programem antywirusowym. Pobieranie i odczyt tekstu będą dostępne za chwilę.
        </Notice>
      )}
      {v?.scan_status === "infected" && (
        <Notice tone="error" title="Plik zablokowany">
          Skaner antywirusowy wykrył w tym pliku zagrożenie, więc go usunęliśmy — nie da się go pobrać ani odczytać. Usuńcie dokument
          i poproście usługodawcę o nową kopię.
        </Notice>
      )}
      {v?.text_status === "failed" && v.scan_status !== "infected" && (
        <Notice tone="warning" title="Nie odczytaliśmy tekstu">
          {v.text_error ?? "Spróbujcie ponownie albo wpiszcie ofertę ręcznie."}
          {canWrite && (
            <Button variant="text" pending={retry.isPending} onPress={() => retry.mutate()}>
              Spróbuj ponownie
            </Button>
          )}
        </Notice>
      )}
      {(v?.scan_status === "clean" || v?.scan_status === "not_scanned") && (
        <Button variant="secondary" pending={download.isPending} onPress={() => download.mutate()}>
          Pobierz plik
        </Button>
      )}

      {v?.text_status === "done" && <DocumentText weddingId={weddingId} documentId={doc.id} versionId={v.id} />}

      {canAnalyze && (
        <section className="form-stack ai-box" aria-labelledby={`ai-${doc.id}`}>
          <h3 id={`ai-${doc.id}`}>Odczytaj ofertę automatycznie</h3>
          <p className="text-secondary">
            Model językowy działający na naszym serwerze odczyta ceny i warunki, z cytatem z dokumentu przy każdej kwocie. Wynik to
            szkic — sprawdzicie go przed porównaniem. Dokument nie trafia do zewnętrznych firm bez Waszej zgody.
          </p>
          {!doc.vendor_id && <Notice tone="info">Najpierw przypiszcie dokument do usługodawcy (wgrajcie go z jego karty).</Notice>}
          {!runId && (
            <Button
              icon={<Sparkles aria-hidden size={20} />}
              isDisabled={!doc.vendor_id}
              pending={analyze.isPending}
              onPress={() => analyze.mutate()}
            >
              Odczytaj ofertę
            </Button>
          )}
          {runId && <RunStatus run={run.data} onOpen={(offerId) => navigate(`/w/${weddingId}/oferty/${offerId}`, { viewTransition: true })} />}
        </section>
      )}

      {canWrite && (
        <Button variant="text" onPress={() => setConfirmDelete(true)}>
          Usuń dokument
        </Button>
      )}
      <ConfirmDialog title="Usunąć dokument?" isOpen={confirmDelete} onOpenChange={setConfirmDelete}>
        <p>„{doc.title}” zniknie razem ze wszystkimi wersjami pliku. Oferty odczytane z dokumentu zostaną.</p>
        <div className="wp-sheet__actions">
          <Button variant="secondary" onPress={() => setConfirmDelete(false)}>
            Anuluj
          </Button>
          <Button variant="danger" pending={remove.isPending} onPress={() => remove.mutate()}>
            Usuń
          </Button>
        </div>
      </ConfirmDialog>
    </div>
  );
}

function RunStatus({ run, onOpen }: { run: AiRun | undefined; onOpen: (offerId: string) => void }) {
  if (!run || run.status === "queued" || run.status === "running") {
    return (
      <Notice tone="info" live>
        Czytamy dokument… To może potrwać kilka minut. Możecie zamknąć to okno — szkic pojawi się przy usługodawcy.
      </Notice>
    );
  }
  if (run.status === "succeeded" && run.offer_id) {
    return (
      <Notice tone="success" title="Gotowe" live>
        Odczytaliśmy ofertę. Sprawdźcie kwoty z cytatami i zatwierdźcie.
        <Button variant="text" onPress={() => onOpen(run.offer_id!)}>
          Otwórz szkic oferty
        </Button>
      </Notice>
    );
  }
  return (
    <Notice tone="warning" title={run.status === "blocked" ? "Wstrzymane" : "Nie udało się"} live>
      {run.error ?? "Nie odczytaliśmy oferty. Wpiszcie ją ręcznie — to zajmie kilka minut."}
    </Notice>
  );
}
