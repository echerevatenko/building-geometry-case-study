import { useEffect } from "react";
import { button, deleteButton } from "../styles.js";
import Spinner from "./Spinner.jsx";

// Modal confirmation, replacing window.confirm. Renders nothing until `open`.
// Backdrop click and Escape cancel; the confirm button shows a spinner while `busy`.
export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Delete",
  busy = false,
  onConfirm,
  onCancel,
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape" && !busy) onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, onCancel]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={() => !busy && onCancel()}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0, 0, 0, 0.35)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "#fff",
          borderRadius: 8,
          padding: "1.25rem",
          width: "min(90vw, 360px)",
          boxShadow: "0 10px 30px rgba(0, 0, 0, 0.2)",
        }}
      >
        {title && <h3 style={{ margin: "0 0 0.5rem", fontSize: "1rem" }}>{title}</h3>}
        <p style={{ margin: "0 0 1rem", fontSize: "0.88rem", color: "#444" }}>{message}</p>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
          <button style={button} onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button style={deleteButton} onClick={onConfirm} disabled={busy}>
            {busy ? <Spinner /> : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
