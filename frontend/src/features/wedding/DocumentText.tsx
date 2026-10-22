import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { Button as AriaButton, Disclosure, DisclosurePanel, Heading } from "react-aria-components";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { Notice, Skeleton } from "../../components/Surface";

/**
 * Tekst odczytany z dokumentu (strona po stronie), pobierany dopiero po rozwinięciu.
 * Służy do sprawdzenia cytatów, z których AI wzięła kwoty.
 */
export function DocumentText({ weddingId, documentId, versionId, title = "Odczytany tekst" }: { weddingId: string; documentId: string; versionId: string; title?: string }) {
  const [open, setOpen] = useState(false);
  const text = useQuery({
    queryKey: ["wedding", weddingId, "documents", documentId, versionId, "text"],
    enabled: open,
    staleTime: Infinity,
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/weddings/{wedding_id}/documents/{document_id}/versions/{version_id}/text", {
          params: { path: { wedding_id: weddingId, document_id: documentId, version_id: versionId } },
          signal,
        }),
      ),
  });
  return (
    <Disclosure className="doc-text" isExpanded={open} onExpandedChange={setOpen}>
      <Heading level={3} className="household__heading">
        <AriaButton slot="trigger" className="household__trigger">
          <span className="row__body">{title}</span>
          <ChevronDown aria-hidden size={20} className="household__chevron" />
        </AriaButton>
      </Heading>
      <DisclosurePanel className="doc-text__panel">
        {text.isPending && <Skeleton lines={4} />}
        {text.isError && (
          <Notice tone="error" live>
            {userMessage(text.error)}
          </Notice>
        )}
        {text.data && (
          <>
            <p className="text-secondary">{text.data.note}</p>
            {text.data.pages.length === 0 && <p className="text-secondary">Brak tekstu.</p>}
            {text.data.pages.map((p) => (
              <section key={p.page} aria-label={`Strona ${p.page}`} className="doc-text__page">
                <h4 className="text-secondary">Strona {p.page}</h4>
                <p className="prewrap">{p.text}</p>
              </section>
            ))}
          </>
        )}
      </DisclosurePanel>
    </Disclosure>
  );
}
