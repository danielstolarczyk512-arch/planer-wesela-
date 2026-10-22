import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Globe, Mail, Phone, Plus, Upload } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { ConfirmDialog } from "../../components/Overlay";
import { Card, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate } from "../../lib/format";
import { useCanWrite, useMembers, useTasks, useWedding, useWeddingId, type Task } from "./data";
import { EditTaskSheet } from "./EditTaskSheet";
import { TaskRow, useToggleTask } from "./tasks";
import { DocumentList, DocumentSheet, UploadSheet, useDocuments } from "./Documents";
import { OfferEditorSheet } from "./OfferEditor";
import { VendorSheet } from "./VendorsView";
import { DayLinkSection } from "./DayLinkSection";
import { VendorMessages } from "./VendorMessages";
import { VendorBriefSection } from "./VendorBriefSection";
import { VendorChecklist } from "./VendorChecklist";
import { OFFER_STATUS, useOffers, useVendor, vendorKeys, VENDOR_STATUS } from "./vendors";

export function VendorView() {
  const id = useWeddingId();
  const { vendorId = "" } = useParams();
  const vendor = useVendor(id, vendorId);
  const wedding = useWedding(id);
  const offers = useOffers(id);
  const canWrite = useCanWrite(id);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [addingOffer, setAddingOffer] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const own = (offers.data ?? []).filter((o) => o.vendor_id === vendorId);
  const docs = useDocuments(id);
  const ownDocs = (docs.data ?? []).filter((d) => d.vendor_id === vendorId);
  const [uploading, setUploading] = useState(false);
  const [openDoc, setOpenDoc] = useState<string | null>(null);
  const tasks = useTasks(id);
  const members = useMembers(id);
  const ownTasks = (tasks.data ?? []).filter((t) => t.vendor_id === vendorId);
  const { toggle, error: taskError } = useToggleTask(id);
  const [editingTask, setEditingTask] = useState<Task | null>(null);

  const remove = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE("/api/v1/weddings/{wedding_id}/vendors/{vendor_id}", {
          params: { path: { wedding_id: id, vendor_id: vendorId } },
        }),
      ),
    onSuccess: async () => {
      setConfirmDelete(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: vendorKeys.all(id) }),
        queryClient.invalidateQueries({ queryKey: vendorKeys.offers(id) }),
      ]);
      toast(`Usunięto „${vendor.data?.name}”`);
      navigate(`/w/${id}/uslugodawcy`, { replace: true });
    },
  });

  if (vendor.isPending) {
    return (
      <main className="page">
        <Skeleton lines={6} />
      </main>
    );
  }
  if (vendor.isError) {
    return (
      <main className="page">
        <Notice tone="error" title="Nie udało się wczytać usługodawcy." live>
          {userMessage(vendor.error)}
        </Notice>
      </main>
    );
  }
  const v = vendor.data;
  const st = VENDOR_STATUS[v.status];

  return (
    <main className="page enter-detail" aria-labelledby="vendor-h">
      <div className="view-head">
        <div>
          <Link to={`/w/${id}/uslugodawcy`} viewTransition className="wp-button wp-button--text back-link">
            ← Usługodawcy
          </Link>
          <p className="overline">{v.category_label}</p>
          <h1 id="vendor-h">{v.name}</h1>
          <p className="chips">
            <StatusChip tone={st.tone}>{st.label}</StatusChip>
            {v.city && <span className="text-secondary">{v.city}</span>}
          </p>
        </div>
        {canWrite && (
          <Button variant="secondary" onPress={() => setEditing(true)}>
            Edytuj
          </Button>
        )}
      </div>

      {(v.phone || v.email || v.website_url) && (
        <Card>
          <ul className="row-list">
            {v.phone && (
              <li>
                <a className="row link-card" href={`tel:${v.phone.replace(/[^\d+]/g, "")}`}>
                  <Phone aria-hidden size={20} />
                  <span className="row__body">{v.phone}</span>
                </a>
              </li>
            )}
            {v.email && (
              <li>
                <a className="row link-card" href={`mailto:${v.email}`}>
                  <Mail aria-hidden size={20} />
                  <span className="row__body">{v.email}</span>
                </a>
              </li>
            )}
            {v.website_url && (
              <li>
                <a className="row link-card" href={v.website_url} target="_blank" rel="noopener noreferrer">
                  <Globe aria-hidden size={20} />
                  <span className="row__body">{v.website_url.replace(/^https?:\/\//, "").replace(/\/$/, "")}</span>
                </a>
              </li>
            )}
          </ul>
        </Card>
      )}
      {v.notes && <p className="text-secondary prewrap">{v.notes}</p>}
      {(v.crew_meals ?? 0) > 0 && (
        <p className="text-secondary num">
          Posiłki dla obsługi na sali: {v.crew_meals} — doliczane do oferty sali w porównaniu.
        </p>
      )}

      <section aria-labelledby="offers-h" className="form-stack">
        <div className="section-head">
          <h2 id="offers-h">Oferty</h2>
          {canWrite && (
            <Button variant="text" icon={<Plus aria-hidden size={18} />} onPress={() => setAddingOffer(true)}>
              Dodaj ofertę
            </Button>
          )}
        </div>
        {offers.isPending && <Skeleton lines={2} />}
        {offers.data && own.length === 0 && (
          <Card>
            <p className="text-secondary">
              Brak ofert. Przepiszcie ceny z maila lub PDF-u — porównamy je z innymi przy tej samej liczbie gości.
            </p>
          </Card>
        )}
        {own.length > 0 && (
          <Card>
            <ul className="row-list">
              {own.map((o) => (
                <li key={o.id}>
                  <Link to={`/w/${id}/oferty/${o.id}`} viewTransition className="row link-card">
                    <span className="row__body">
                      <span className="row__title">{o.title}</span>
                      <span className="text-secondary">
                        {[o.valid_until && `ważna do ${formatDate(o.valid_until)}`, o.unverified_fields > 0 && `pól do sprawdzenia: ${o.unverified_fields}`]
                          .filter(Boolean)
                          .join(" · ") || `${o.components.length} pozycji`}
                      </span>
                    </span>
                    <StatusChip tone={OFFER_STATUS[o.status].tone}>{OFFER_STATUS[o.status].label}</StatusChip>
                    <ChevronRight aria-hidden size={20} />
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </section>

      <DayLinkSection weddingId={id} vendorId={vendorId} vendorCategory={v.category} canWrite={canWrite} />
      <VendorBriefSection weddingId={id} vendorId={vendorId} vendorCategory={v.category} canWrite={canWrite} />
      {wedding.data && canWrite && <VendorMessages wedding={wedding.data} vendor={v} />}
      <VendorChecklist weddingId={id} vendorId={vendorId} kind="question" canWrite={canWrite} />
      <VendorChecklist weddingId={id} vendorId={vendorId} kind="contract" canWrite={canWrite} />

      <section aria-labelledby="vdocs-h" className="form-stack">
        <div className="section-head">
          <h2 id="vdocs-h">Dokumenty</h2>
          {canWrite && (
            <Button variant="text" icon={<Upload aria-hidden size={18} />} onPress={() => setUploading(true)}>
              Wgraj ofertę lub umowę
            </Button>
          )}
        </div>
        <Card>
          {ownDocs.length === 0 ? (
            <p className="text-secondary">Wgrajcie ofertę w PDF — odczytamy z niej ceny i warunki do sprawdzenia.</p>
          ) : (
            <DocumentList docs={ownDocs} onOpen={setOpenDoc} />
          )}
        </Card>
      </section>

      {ownTasks.length > 0 && (
        <section aria-labelledby="vtasks-h" className="form-stack">
          <h2 id="vtasks-h">Zadania</h2>
          {taskError && (
            <Notice tone="error" live>
              {taskError}
            </Notice>
          )}
          <Card>
            <ul className="row-list">
              {ownTasks.map((t) => (
                <li key={t.id}>
                  <TaskRow task={t} members={members.data} canWrite={canWrite} onToggle={toggle} onEdit={setEditingTask} />
                </li>
              ))}
            </ul>
          </Card>
        </section>
      )}

      {canWrite && (
        <Button variant="text" onPress={() => setConfirmDelete(true)}>
          Usuń usługodawcę
        </Button>
      )}

      <VendorSheet weddingId={id} vendor={v} isOpen={editing} onClose={() => setEditing(false)} />
      <EditTaskSheet weddingId={id} task={editingTask} onClose={() => setEditingTask(null)} />
      <UploadSheet weddingId={id} vendorId={vendorId} isOpen={uploading} onClose={() => setUploading(false)} />
      <DocumentSheet weddingId={id} doc={ownDocs.find((d) => d.id === openDoc) ?? null} onClose={() => setOpenDoc(null)} />
      <OfferEditorSheet
        weddingId={id}
        vendorId={vendorId}
        vendorCategory={v.category}
        offer={null}
        isOpen={addingOffer}
        onClose={() => setAddingOffer(false)}
      />
      <ConfirmDialog title="Usunąć usługodawcę?" isOpen={confirmDelete} onOpenChange={setConfirmDelete}>
        <p>
          „{v.name}” zniknie razem z {own.length > 0 ? `ofertami (${own.length})` : "danymi kontaktowymi"}. Pozycje w budżecie i
          płatności zostaną.
        </p>
        {remove.isError && (
          <Notice tone="error" live>
            {userMessage(remove.error)}
          </Notice>
        )}
        <div className="wp-sheet__actions">
          <Button variant="secondary" onPress={() => setConfirmDelete(false)}>
            Anuluj
          </Button>
          <Button variant="danger" pending={remove.isPending} onPress={() => remove.mutate()}>
            Usuń
          </Button>
        </div>
      </ConfirmDialog>
    </main>
  );
}
