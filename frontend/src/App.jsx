import { useCallback, useEffect, useState } from "react";
import { listPolygons } from "./api.js";
import { card, colors } from "./styles.js";
import PolygonsList from "./components/PolygonsList.jsx";
import Polygon from "./components/Polygon.jsx";
import Scene from "./components/Scene.jsx";
import ConfirmDialog from "./components/ConfirmDialog.jsx";
import { useToast } from "./components/toastContext.js";

// A new polygon is an unsaved client-side draft until the user hits Save; it
// carries this sentinel id and is never sent to the backend until then.
const DRAFT_ID = "draft";
// A draft starts with no coordinates — the user enters the site polygon themselves.
const EMPTY_SITE = { coordinates: [] };

export default function App() {
  const notify = useToast();
  const [polygons, setPolygons] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  // Whether the selected polygon's editor has unsaved edits (reported by <Polygon>).
  const [dirty, setDirty] = useState(false);
  // A navigation action awaiting confirmation because of unsaved edits; null when idle.
  const [pendingNav, setPendingNav] = useState(null);
  // The massing option whose footprint is shown on the canvas: { id, footprint }.
  // The footprint comes from the last Generate preview (it isn't persisted).
  const [active, setActive] = useState(null);
  // The unsaved new polygon, if any (id === DRAFT_ID). Persisted only on Save.
  const [draft, setDraft] = useState(null);
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

  // Adding a polygon creates only a local draft — nothing is sent to the backend
  // until the user saves it. It starts blank; the user enters the coordinates.
  const addPolygon = () => {
    setDraft({
      id: DRAFT_ID,
      title: "Untitled polygon",
      site_polygon: EMPTY_SITE,
      buildable_base: null,
      geometry_status: null,
      geometry_reason: null,
      is_deleted: false,
      created_at: null,
      updated_at: null,
    });
    setSelectedId(DRAFT_ID);
  };

  // Run a navigation now; the freshly mounted editor will re-report its own dirty state.
  const runNav = (action) => {
    setDirty(false);
    action();
  };
  // Navigate, but if the current editor has unsaved edits, confirm the discard first.
  const guardedNav = (action) => (dirty ? setPendingNav(() => action) : runNav(action));

  // After a save, refresh the list. If a draft was just created, select the real
  // row (which clears the draft via the effect below).
  const onPolygonSaved = async (saved) => {
    await loadPolygons();
    if (selectedId === DRAFT_ID) setSelectedId(saved?.id ?? null);
  };
  const onPolygonDeleted = async () => {
    setDraft(null);
    await loadPolygons();
    setDirty(false);
    setSelectedId(null);
  };

  // The draft (if any) shows at the top of the list alongside saved polygons.
  const listed = draft ? [draft, ...polygons] : polygons;
  const selected = listed.find((p) => p.id === selectedId) ?? null;
  // The shown footprint belongs to the selected polygon; drop it when navigating away.
  useEffect(() => {
    setActive(null);
  }, [selectedId]);
  // Leaving the draft (saved, deleted, or navigated away) discards it.
  useEffect(() => {
    if (selectedId !== DRAFT_ID) setDraft(null);
  }, [selectedId]);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", height: "100vh", display: "flex", overflow: "hidden" }}>
      {/* Main screen: canvas / visualization (left empty for now). */}
      <section style={{ flex: 1, display: "flex", flexDirection: "column", padding: "1.5rem", minWidth: 0 }}>
        <h1 style={{ margin: "0 0 1rem", fontSize: "1.4rem" }}>Building Geometry Case Study</h1>
        <div
          style={{
            flex: 1,
            border: `1px solid ${colors.border}`,
            borderRadius: 8,
            overflow: "hidden",
            minHeight: 0,
          }}
        >
          <Scene
            site={selected?.site_polygon ?? null}
            base={selected?.buildable_base ?? null}
            footprint={active?.footprint ?? null}
            height={active?.height ?? null}
          />
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
          polygons={listed}
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
              activeOptionId={active?.id ?? null}
              onActivate={(id, massing) => setActive(id == null ? null : { id, ...massing })}
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
