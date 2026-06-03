import { useCallback, useState } from "react";
import { colors } from "../styles.js";
import { ToastContext } from "./toastContext.js";

// Non-blocking notifications — a drop-in replacement for window.alert.
// Toasts stack at the bottom-right, auto-dismiss after a few seconds, and
// can be clicked to dismiss early.
const KIND_COLOR = {
  error: colors.danger,
  success: colors.feasible,
  info: colors.selectedBorder,
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => setToasts((list) => list.filter((t) => t.id !== id)), []);

  const notify = useCallback(
    (message, kind = "error") => {
      const id = `${Date.now()}-${Math.random()}`;
      setToasts((list) => [...list, { id, message, kind }]);
      setTimeout(() => dismiss(id), 5000);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={notify}>
      {children}
      <div
        style={{
          position: "fixed",
          bottom: "1rem",
          right: "1rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.5rem",
          zIndex: 2000,
          maxWidth: "min(90vw, 360px)",
        }}
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role="alert"
            onClick={() => dismiss(t.id)}
            title="Dismiss"
            style={{
              padding: "0.6rem 0.75rem",
              background: "#fff",
              borderRadius: 6,
              borderLeft: `4px solid ${KIND_COLOR[t.kind] ?? colors.danger}`,
              boxShadow: "0 6px 20px rgba(0, 0, 0, 0.18)",
              fontSize: "0.85rem",
              color: "#222",
              cursor: "pointer",
            }}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
