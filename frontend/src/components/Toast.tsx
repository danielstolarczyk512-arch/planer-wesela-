import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";

import "./Toast.css";

interface ToastItem {
  id: number;
  message: string;
  undo?: () => void;
}

const ToastContext = createContext<(message: string, undo?: () => void) => void>(() => {});

/** Czas widoczności: min. 6 s (spec), wstrzymywany przy fokusie i najechaniu. */
export const TOAST_MS = 6000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastItem | null>(null);
  const show = useCallback((message: string, undo?: () => void) => {
    setToast({ id: Date.now(), message, undo });
  }, []);
  return (
    <ToastContext.Provider value={show}>
      {children}
      {/* Region na żywo istnieje zawsze: czytnik ekranu ogłasza nowe komunikaty. */}
      <div className="wp-toast-region" aria-live="polite" aria-atomic="true">
        {toast && <Toast key={toast.id} item={toast} onDone={() => setToast(null)} />}
      </div>
    </ToastContext.Provider>
  );
}

function Toast({ item, onDone }: { item: ToastItem; onDone: () => void }) {
  const timer = useRef<number | undefined>(undefined);
  const start = useCallback(() => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(onDone, TOAST_MS);
  }, [onDone]);
  const pause = () => window.clearTimeout(timer.current);
  useEffect(() => {
    start();
    return pause;
  }, [start]);
  return (
    <div className="wp-toast" onMouseEnter={pause} onMouseLeave={start} onFocus={pause} onBlur={start}>
      <span>{item.message}</span>
      {item.undo && (
        <button
          type="button"
          className="wp-toast__undo"
          onClick={() => {
            item.undo?.();
            onDone();
          }}
        >
          Cofnij
        </button>
      )}
    </div>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
