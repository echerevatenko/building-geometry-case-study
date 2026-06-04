import { useCallback, useEffect, useState } from "react";
import { createMassingOption, createPolygon, deletePolygon, listPolygonMassingOptions, updatePolygon } from "../api.js";
import { button, card, colors, deleteButton, editNameButton, input, label, saveButton } from "../styles.js";
import CoordinateEditor from "./CoordinateEditor.jsx";
import MassingOptionsTree from "./MassingOptionsTree.jsx";
import Spinner from "./Spinner.jsx";
import ConfirmDialog from "./ConfirmDialog.jsx";
import { useToast } from "./toastContext.js";

const coordsOf = (polygon) => polygon.site_polygon?.coordinates ?? [];

export default function Polygon({ polygon, onSaved, onDeleted, onDirtyChange, activeOptionId, onActivate }) {
  const notify = useToast();
  // A draft polygon (not yet persisted) has a non-numeric sentinel id.
  const isNew = typeof polygon.id !== "number";
  const [title, setTitle] = useState(polygon.title);
  // Title reads as plain text; the pencil switches it to an input — same as massing option names.
  const [editingTitle, setEditingTitle] = useState(false);
  const [coords, setCoords] = useState(coordsOf(polygon));
  const [massingOptions, setMassingOptions] = useState([]);
  // Ids of massing options with unsaved edits, reported up from the tree.
  const [dirtyOptionIds, setDirtyOptionIds] = useState(() => new Set());
  // Which action is in flight, so its button can show a spinner; null when idle.
  const [pending, setPending] = useState(null);
  const busy = pending !== null;
  // Whether the delete-confirmation dialog is showing.
  const [confirmOpen, setConfirmOpen] = useState(false);

  // Reset the drafts whenever a different polygon is selected.
  useEffect(() => {
    setTitle(polygon.title);
    setEditingTitle(false);
    setCoords(coordsOf(polygon));
  }, [polygon.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadMassingOptions = useCallback(async () => {
    // A draft has no backend row yet, so it has no options to load.
    if (typeof polygon.id !== "number") {
      setMassingOptions([]);
      return;
    }
    setMassingOptions(await listPolygonMassingOptions(polygon.id));
  }, [polygon.id]);

  useEffect(() => {
    loadMassingOptions().catch((err) => notify(err.message));
  }, [loadMassingOptions, notify]);

  // A massing option reports whether it currently has unsaved edits.
  const handleOptionDirty = useCallback((id, isDirty) => {
    setDirtyOptionIds((prev) => {
      if (isDirty === prev.has(id)) return prev;
      const next = new Set(prev);
      if (isDirty) next.add(id);
      else next.delete(id);
      return next;
    });
  }, []);

  const run = async (key, fn) => {
    setPending(key);
    try {
      await fn();
    } catch (err) {
      notify(err.message);
    } finally {
      setPending(null);
    }
  };

  const save = () =>
    run("save", async () => {
      const payload = { title: title.trim(), site_polygon: { coordinates: coords } };
      // A draft is created on first save; an existing polygon is patched.
      const saved = isNew ? await createPolygon(payload) : await updatePolygon(polygon.id, payload);
      await onSaved(saved);
    });

  const confirmDelete = () =>
    run("delete", async () => {
      if (!isNew) await deletePolygon(polygon.id); // a draft only needs discarding
      setConfirmOpen(false);
      await onDeleted();
    });

  const addMassingOption = () =>
    run("add", async () => {
      await createMassingOption({ polygon_id: polygon.id });
      await loadMassingOptions();
    });

  // Options can only be added once the polygon has a saved site polygon and no pending edits
  // to the polygon's own fields (a mid-edit massing option doesn't block adding a sibling).
  const savedCoords = coordsOf(polygon);
  const ownDirty = title.trim() !== polygon.title || JSON.stringify(coords) !== JSON.stringify(savedCoords);
  const addDisabledReason = isNew
    ? "Save the polygon before adding massing options"
    : ownDirty
      ? "Save changes before adding massing options"
      : savedCoords.length === 0
        ? "Add a site polygon before adding massing options"
        : null;

  // Unsaved edits anywhere in this editor — the polygon itself or any massing option —
  // so the parent can guard against discarding them when navigating away. A brand-new
  // draft is always "dirty" until it has been saved at least once.
  const dirty = isNew || ownDirty || dirtyOptionIds.size > 0;
  // A polygon needs at least 3 points before it can be saved.
  const cannotSave = busy || coords.length < 3;
  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div>
        {editingTitle ? (
          <input
            style={{ ...input, width: "100%" }}
            value={title}
            autoFocus
            onChange={(e) => setTitle(e.target.value)}
            onBlur={() => setEditingTitle(false)}
            onKeyDown={(e) => {
              if (e.key === "Enter") setEditingTitle(false);
            }}
          />
        ) : (
          <div style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
            <span style={{ fontSize: "1.05rem", fontWeight: 600, color: title.trim() ? "#222" : "#aaa" }}>
              {title.trim() || "Untitled"}
            </span>
            <button
              style={editNameButton}
              onClick={() => setEditingTitle(true)}
              title="Edit title"
              aria-label="edit polygon title"
            >
              ✎
            </button>
          </div>
        )}
      </div>

      <CoordinateEditor title="Footprint (site polygon)" coords={coords} onChange={setCoords} />

      <div style={{ display: "flex", gap: "0.4rem", alignItems: "center", flexWrap: "wrap" }}>
        <button
          style={{ ...saveButton, ...(cannotSave ? { opacity: 0.45, cursor: "not-allowed" } : {}) }}
          disabled={cannotSave}
          onClick={save}
          title={coords.length < 3 ? "Add at least 3 points to the site polygon first" : undefined}
        >
          {pending === "save" ? <Spinner /> : "Save"}
        </button>
        <button style={deleteButton} disabled={busy} onClick={() => (isNew ? confirmDelete() : setConfirmOpen(true))}>
          {pending === "delete" ? <Spinner /> : isNew ? "Discard" : "Delete"}
        </button>
      </div>

      {/* Massing options live in their own card, separate from the polygon's own fields. */}
      <div style={{ ...card, background: colors.bg }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.3rem" }}>
          <span style={label}>Massing options</span>
          <button
            style={button}
            disabled={busy || addDisabledReason !== null}
            onClick={addMassingOption}
            title={addDisabledReason ?? undefined}
          >
            + Add massing option
          </button>
        </div>
        <MassingOptionsTree
          massingOptions={massingOptions}
          polygonId={polygon.id}
          onChanged={loadMassingOptions}
          onOptionDirtyChange={handleOptionDirty}
          activeOptionId={activeOptionId}
          onActivate={onActivate}
        />
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Delete polygon"
        message={`Delete polygon "${polygon.title}" and all its massing options? This cannot be undone.`}
        busy={pending === "delete"}
        onConfirm={confirmDelete}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}
