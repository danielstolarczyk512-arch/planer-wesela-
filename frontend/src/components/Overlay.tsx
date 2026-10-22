import { X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Button as AriaButton, Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";

import { Button } from "./Button";
import "./Overlay.css";

interface OverlayProps {
  title: string;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  children: ReactNode;
}

/**
 * Dialog potwierdzenia: fokus w środku, Escape zamyka, fokus wraca do wywołującej kontrolki
 * (React Aria). Jednoznaczne przyciski przekazuje wywołujący.
 */
export function ConfirmDialog({ title, isOpen, onOpenChange, children }: OverlayProps) {
  return (
    <ModalOverlay isOpen={isOpen} onOpenChange={onOpenChange} isDismissable className="wp-overlay">
      <Modal className="wp-dialog">
        <Dialog className="wp-dialog__body">
          <Heading slot="title">{title}</Heading>
          {children}
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

interface SheetProps extends OverlayProps {
  /** Formularz ma niezapisane zmiany: zamknięcie pyta „Zapisać szkic czy odrzucić?”. */
  isDirty?: boolean;
  onSaveDraft?: () => void;
}

/**
 * Dolny panel (na telefonie od dołu, na szerokim ekranie wyśrodkowany). Uchwyt jest dekoracją:
 * zamykanie przyciskiem, Escape albo dotknięciem tła; gest nie jest jedyną metodą.
 */
export function Sheet({ title, isOpen, onOpenChange, isDirty, onSaveDraft, children }: SheetProps) {
  const [asking, setAsking] = useState(false);
  const requestClose = (open: boolean) => {
    if (open) return onOpenChange(true);
    if (isDirty) return setAsking(true);
    setAsking(false);
    onOpenChange(false);
  };
  return (
    <ModalOverlay isOpen={isOpen} onOpenChange={requestClose} isDismissable className="wp-overlay wp-overlay--sheet">
      <Modal className="wp-sheet">
        <Dialog className="wp-sheet__body">
          <span className="wp-sheet__handle" aria-hidden="true" />
          <div className="wp-sheet__header">
            <Heading slot="title">{title}</Heading>
            <AriaButton className="wp-icon-button" aria-label="Zamknij" onPress={() => requestClose(false)}>
              <X aria-hidden size={22} strokeWidth={1.75} />
            </AriaButton>
          </div>
          {asking ? (
            <div className="wp-sheet__ask" role="alertdialog" aria-label="Niezapisane zmiany">
              <p className="wp-notice__title">Masz niezapisane zmiany.</p>
              <p className="text-secondary">Zapisać szkic czy odrzucić zmiany?</p>
              <div className="wp-sheet__actions">
                <Button
                  variant="secondary"
                  onPress={() => {
                    setAsking(false);
                    onOpenChange(false);
                  }}
                >
                  Odrzuć zmiany
                </Button>
                {onSaveDraft ? (
                  <Button
                    onPress={() => {
                      onSaveDraft();
                      setAsking(false);
                      onOpenChange(false);
                    }}
                  >
                    Zapisz szkic
                  </Button>
                ) : (
                  <Button autoFocus onPress={() => setAsking(false)}>
                    Wróć do formularza
                  </Button>
                )}
              </div>
            </div>
          ) : (
            children
          )}
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}
