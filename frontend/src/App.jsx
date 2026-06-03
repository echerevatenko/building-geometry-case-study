import { useCallback, useEffect, useState } from "react";
import { createPolygon, listPolygons } from "./api.js";
import { card, colors } from "./styles.js";
import PolygonsList from "./components/PolygonsList.jsx";
import Polygon from "./components/Polygon.jsx";
import ConfirmDialog from "./components/ConfirmDialog.jsx";
import { useToast } from "./components/toastContext.js";

export default function App() {
  const notify = useToast();
  const [polygons, setPolygons] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  // Whether the selected polygon's editor has unsaved edits (reported by <Polygon>).
  const [dirty, setDirty] = useState(false);
  // A navigation action awaiting confirmation because of unsaved edits; null when idle.
  const [pendingNav, setPendingNav] = useState(null);
  // Width of the side panel in px; dragged via the divider between canvas and panel.
  const [asideWidth, setAsideWidth] = useState(400);

  const startResize = (e) => {
    e.preventDefault();
    const onMove = (ev) => setAsideWidth(Math.min(720, Math.max(280, window.innerWidth - ev.clientX)));
    const stop = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", stop);
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
    };
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", stop);
  };

  const loadPolygons = useCallback(async () => {
    const rows = await listPolygons();
    setPolygons(rows);
    return rows;
  }, []);

  useEffect(() => {
    loadPolygons().catch((err) => notify(err.message));
  }, [loadPolygons, notify]);

  const addPolygon = async () => {
    try {
      const created = await createPolygon({ title: "Untitled polygon" });
      await loadPolygons();
      setSelectedId(created.id);
    } catch (err) {
      notify(err.message);
    }
  };

  // Run a navigation now; the freshly mounted editor will re-report its own dirty state.
  const runNav = (action) => {
    setDirty(false);
    action();
  };
  // Navigate, but if the current editor has unsaved edits, confirm the discard first.
  const guardedNav = (action) => (dirty ? setPendingNav(() => action) : runNav(action));

  // After a save, keep the selection but refresh the list (titles, polygons).
  const onPolygonSaved = () => loadPolygons();
  const onPolygonDeleted = async () => {
    await loadPolygons();
    setDirty(false);
    setSelectedId(null);
  };

  const selected = polygons.find((p) => p.id === selectedId) ?? null;

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", height: "100vh", display: "flex", overflow: "hidden" }}>
      {/* Main screen: canvas / visualization (left empty for now). */}
      <section style={{ flex: 1, display: "flex", flexDirection: "column", padding: "1.5rem", minWidth: 0 }}>
        <h1 style={{ margin: "0 0 1rem", fontSize: "1.4rem" }}>Building Geometry Case Study</h1>
        <div
          style={{
            flex: 1,
            border: `2px dashed ${colors.borderStrong}`,
            borderRadius: 8,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#888",
          }}
        >
          {/* TODO(candidate): polygon visualization renders here. */}
          Canvas — visualization goes here.
        </div>
      </section>

      {/* Draggable divider — resizes the side panel. */}
      <div
        onMouseDown={startResize}
        role="separator"
        aria-orientation="vertical"
        title="Drag to resize"
        style={{ width: 6, flex: "0 0 auto", cursor: "col-resize", background: colors.border }}
      />

      {/* Side panel: polygons + per-polygon massing options. */}
      <aside
        style={{
          width: asideWidth,
          flex: "0 0 auto",
          background: colors.bg,
          padding: "1.5rem",
          overflowY: "auto",
        }}
      >
        <PolygonsList
          polygons={polygons}
          selectedId={selectedId}
          onSelect={(id) => id !== selectedId && guardedNav(() => setSelectedId(id))}
          onAdd={() => guardedNav(addPolygon)}
        />

        {selected ? (
          <div style={card}>
            <Polygon
              key={selected.id}
              polygon={selected}
              onSaved={onPolygonSaved}
              onDeleted={onPolygonDeleted}
              onDirtyChange={setDirty}
            />
          </div>
        ) : (
          <p style={{ fontSize: "0.85rem", color: "#888" }}>
            Select a polygon to edit it and manage its massing options.
          </p>
        )}
      </aside>

      <ConfirmDialog
        open={pendingNav !== null}
        title="Unsaved changes"
        message="You have unsaved changes to this polygon. Discard them and continue?"
        confirmLabel="Discard changes"
        onConfirm={() => {
          const action = pendingNav;
          setPendingNav(null);
          runNav(action);
        }}
        onCancel={() => setPendingNav(null)}
      />
    </main>
  );
}
