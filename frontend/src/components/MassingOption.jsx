import { useEffect, useState } from "react";
import {
  createMassingOption,
  deleteMassingOption,
  FEASIBLE,
  generateMassingOption,
  updateMassingOption,
} from "../api.js";
import {
  addChildButton,
  colors,
  deleteButton,
  editNameButton,
  input,
  generateButton,
  label,
  saveButton,
  settingsSection,
} from "../styles.js";
import Spinner from "./Spinner.jsx";
import ConfirmDialog from "./ConfirmDialog.jsx";
import { useToast } from "./toastContext.js";

// Deepest the massing options tree may nest: roots are depth 1, so the last addable level is 4.
export const MAX_DEPTH = 5;

// Editable per-option constraints — each maps to a key in the `constraints` jsonb column.
const CONSTRAINT_FIELDS = [
  { key: "setback_m", label: "setback m", step: "any" },
  { key: "floor_to_floor_m", label: "floor-to-floor m", step: "any" },
  { key: "max_height_m", label: "max height m", step: "any" },
  { key: "max_floors", label: "max floors", step: "1" },
  { key: "site_coverage_ratio", label: "site coverage", step: "any" },
  { key: "target_gfa", label: "target GFA", step: "any" },
];

// Read-only metrics — counted during generation, never edited here.
const METRIC_FIELDS = [
  { key: "floor_count", label: "floors" },
  { key: "footprint_area", label: "footprint area" },
  { key: "gfa", label: "GFA" },
];

const inlineFieldLabel = {
  fontSize: "0.78rem",
  color: colors.muted,
  display: "flex",
  alignItems: "center",
  gap: "0.3rem",
};

// Each detail section (constraints, metrics) sits in its own tinted panel so the
// two read as distinct groups rather than one long list.
const sectionPanel = {
  marginTop: "0.6rem",
  padding: "0.5rem 0.6rem",
  borderRadius: 6,
  border: `1px solid ${colors.border}`,
  background: colors.bg,
};

function StatusBadge({ status }) {
  if (!status) return null;
  const ok = status === FEASIBLE;
  return (
    <span style={{ fontSize: "0.75rem", fontWeight: 600, color: ok ? colors.feasible : colors.infeasible }}>
      {status}
    </span>
  );
}

// One massing option in the tree: a collapsed header, plus settings/actions/sub-options when expanded.
export default function MassingOption({
  node,
  polygonId,
  onChanged,
  onOptionDirtyChange,
  activeOptionId,
  onActivate,
  depth = 1,
}) {
  const notify = useToast();
  const [name, setName] = useState(node.name ?? "");
  // String-valued inputs for each constraint, seeded from the saved row.
  const [constraintInputs, setConstraintInputs] = useState(() =>
    Object.fromEntries(CONSTRAINT_FIELDS.map(({ key }) => [key, node.constraints?.[key] ?? ""])),
  );
  const setConstraint = (key, value) => setConstraintInputs((prev) => ({ ...prev, [key]: value }));
  const [status, setStatus] = useState(node.verification_result ?? null);
  // The last Generate preview (footprint + metrics + reasons); null until generated.
  // Not persisted — it's a what-if over the current, possibly-unsaved constraints.
  const [result, setResult] = useState(null);
  // Which action is in flight, so its button can show a spinner; null when idle.
  const [pending, setPending] = useState(null);
  const busy = pending !== null;
  // One toggle reveals the massing option's detail — settings, actions, and any sub-options.
  const [expanded, setExpanded] = useState(false);
  // Whether the name is being edited; otherwise it reads as plain text.
  const [editingName, setEditingName] = useState(false);
  // Whether the delete-confirmation dialog is showing.
  const [confirmOpen, setConfirmOpen] = useState(false);

  const hasChildren = node.children.length > 0;
  // This option's footprint is the one currently drawn on the canvas.
  const isActive = node.id === activeOptionId;
  // At the deepest level, adding another sub-option would exceed MAX_DEPTH.
  const atMaxDepth = depth >= MAX_DEPTH;
  // Unsaved edits to this option's own fields (name / constraints) block adding children.
  const dirty =
    (name.trim() || null) !== (node.name ?? null) ||
    CONSTRAINT_FIELDS.some(({ key }) => String(constraintInputs[key]) !== String(node.constraints?.[key] ?? ""));

  // Report unsaved edits up so the parent can guard navigation; clear on unmount.
  useEffect(() => {
    onOptionDirtyChange?.(node.id, dirty);
    return () => onOptionDirtyChange?.(node.id, false);
  }, [dirty, node.id, onOptionDirtyChange]);

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

  // Collect the editor's numeric constraints (skipping blanks) for save/generate.
  const collectConstraints = () => {
    const constraints = {};
    for (const { key } of CONSTRAINT_FIELDS) {
      const raw = constraintInputs[key];
      if (raw !== "") constraints[key] = Number(raw);
    }
    return constraints;
  };

  const save = () =>
    run("save", async () => {
      const payload = { name: name.trim() || null, constraints: collectConstraints() };
      // Persist the last preview's metrics too, so they survive reloads and a
      // branched child can inherit them from the saved row.
      if (result) {
        payload.floor_count = result.floor_count;
        payload.footprint_area = result.footprint_area;
        payload.gfa = result.gfa;
        payload.verification_result = result.verification_result;
      }
      await updateMassingOption(node.id, payload);
      await onChanged();
    });

  // The 3D mass: the footprint + its building height (floors × floor-to-floor).
  const massingOf = (r) => {
    if (!r?.footprint) return { footprint: null, height: null };
    const floorHeight = Number(constraintInputs.floor_to_floor_m) || 0;
    const height = r.floor_count && floorHeight ? r.floor_count * floorHeight : null;
    return { footprint: r.footprint, height };
  };

  // Generate is a preview: it masses with the *current* (possibly unsaved) constraints
  // and shows the result here + on the canvas, without persisting anything.
  const generate = () =>
    run("generate", async () => {
      const res = await generateMassingOption(node.id, collectConstraints());
      setResult(res);
      setStatus(res.verification_result);
      onActivate?.(node.id, massingOf(res));
    });

  // Show this option on the canvas with its latest previewed footprint (if any).
  const activate = () => onActivate?.(node.id, massingOf(result));
  const addChild = () =>
    run("add", async () => {
      // Pre-fill the child with this option's current state so it branches as a
      // copy; metrics come from the latest preview if there is one, else the saved row.
      const metrics = result ?? node;
      await createMassingOption({
        polygon_id: polygonId,
        parent_id: node.id,
        constraints: collectConstraints(),
        floor_count: metrics.floor_count ?? null,
        footprint_area: metrics.footprint_area ?? null,
        gfa: metrics.gfa ?? null,
        verification_result: metrics.verification_result ?? null,
      });
      setExpanded(true);
      await onChanged();
    });
  const confirmDelete = () =>
    run("delete", async () => {
      await deleteMassingOption(node.id);
      setConfirmOpen(false);
      await onChanged(); // refresh the massing options list now that this node is gone
    });

  return (
    <li style={{ listStyle: "none" }}>
      <div
        style={{
          padding: "0.4rem 0.5rem",
          marginTop: "0.4rem",
          border: `1px solid ${isActive ? colors.selectedBorder : colors.border}`,
          borderRadius: 6,
          background: isActive ? colors.selected : "#fff",
        }}
      >
        {/* Block 1 — title, child count, add-child. Always visible; click to open and show on canvas. */}
        <div
          onClick={() => {
            setExpanded((v) => !v);
            activate();
          }}
          role="button"
          tabIndex={0}
          aria-expanded={expanded}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              setExpanded((v) => !v);
              activate();
            }
          }}
          style={{ display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap", cursor: "pointer" }}
        >
          {/* expand/collapse caret — reveals this massing option's settings, actions, and sub-options */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              setExpanded((v) => !v);
            }}
            aria-label={expanded ? "collapse" : "expand"}
            style={{
              width: "1.1rem",
              height: "1.1rem",
              lineHeight: 1,
              padding: 0,
              border: "none",
              background: "none",
              cursor: "pointer",
              color: colors.muted,
              fontSize: "0.7rem",
            }}
          >
            {expanded ? "▾" : "▸"}
          </button>
          {/* Name reads as plain text; the pencil switches it to an input. */}
          {editingName ? (
            <input
              style={{ ...input, width: "7rem" }}
              type="text"
              placeholder="name…"
              value={name}
              autoFocus
              onClick={(e) => e.stopPropagation()}
              onChange={(e) => setName(e.target.value)}
              onBlur={() => setEditingName(false)}
              onKeyDown={(e) => {
                e.stopPropagation();
                if (e.key === "Enter") setEditingName(false);
              }}
              aria-label={`massing option ${node.id} name`}
            />
          ) : (
            <>
              <span style={{ fontSize: "0.9rem", color: name.trim() ? "#222" : "#aaa" }}>
                {name.trim() || "Untitled"}
              </span>
              <button
                style={editNameButton}
                onClick={(e) => {
                  e.stopPropagation();
                  setEditingName(true);
                }}
                title="Edit name"
                aria-label={`edit massing option ${node.id} name`}
              >
                ✎
              </button>
            </>
          )}
          <span style={{ flex: 1 }} />
          {hasChildren && (
            <span style={{ fontSize: "0.72rem", color: "#999" }}>
              {node.children.length} child{node.children.length > 1 ? "ren" : ""}
            </span>
          )}
          {/* Blue circular "＋" in the corner — add a sub-option (capped at MAX_DEPTH). */}
          <button
            style={{
              ...addChildButton,
              ...(busy || atMaxDepth || dirty || !node.id ? { opacity: 0.4, cursor: "not-allowed" } : {}),
            }}
            disabled={busy || atMaxDepth || dirty || !node.id}
            onClick={(e) => {
              e.stopPropagation();
              void addChild();
            }}
            title={
              atMaxDepth
                ? `Maximum nesting depth of ${MAX_DEPTH} reached`
                : dirty
                  ? "Save changes before adding a sub-option"
                  : "Add a sub-option under this one"
            }
            aria-label={`add a sub-option under massing option ${node.id}`}
          >
            +
          </button>
        </div>

        {expanded && (
          <>
            {/* Block 2 — constraints; one numeric input per building constraint. */}
            <div style={sectionPanel}>
              <span style={label}>Constraints</span>
              <div style={{ ...settingsSection, marginTop: 0 }}>
                {CONSTRAINT_FIELDS.map(({ key, label: fieldLabel, step }) => (
                  <label key={key} style={inlineFieldLabel}>
                    {fieldLabel}
                    <input
                      style={{ ...input, width: "4.5rem" }}
                      type="number"
                      step={step}
                      value={constraintInputs[key]}
                      onChange={(e) => setConstraint(key, e.target.value)}
                    />
                  </label>
                ))}
              </div>
            </div>

            {/* Block 3 — metrics; from the last preview if any, else the saved/inherited row. */}
            <div style={sectionPanel}>
              <span style={label}>Metrics{result ? " (preview)" : ""}</span>
              <div style={{ ...settingsSection, marginTop: 0 }}>
                {METRIC_FIELDS.map(({ key, label: fieldLabel }) => {
                  const value = (result ?? node)[key] ?? null;
                  return (
                    <span key={key} style={inlineFieldLabel}>
                      {fieldLabel}
                      <strong style={{ color: value == null ? "#aaa" : "#222", fontWeight: 600 }}>
                        {value ?? "—"}
                      </strong>
                    </span>
                  );
                })}
              </div>
              {result?.reasons?.length > 0 && (
                <ul style={{ margin: "0.4rem 0 0", paddingLeft: "1rem" }}>
                  {result.reasons.map((r) => (
                    <li key={r.name} style={{ fontSize: "0.75rem", color: colors.muted }}>
                      {r.message}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Block 4 — actions. */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.4rem",
                marginTop: "0.6rem",
                paddingTop: "0.5rem",
                borderTop: `1px solid ${colors.border}`,
              }}
            >
              <StatusBadge status={status} />
              <span style={{ flex: 1 }} />
              <button style={generateButton} disabled={busy} onClick={generate}>
                {pending === "generate" ? <Spinner /> : "Generate"}
              </button>
              <button style={saveButton} disabled={busy} onClick={save}>
                {pending === "save" ? <Spinner /> : "Save"}
              </button>
              <button style={deleteButton} disabled={busy || !node.id} onClick={() => setConfirmOpen(true)}>
                {pending === "delete" ? <Spinner /> : "Delete"}
              </button>
            </div>
          </>
        )}
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Delete massing option"
        message={`Delete "${name.trim() || "Untitled"}" and its sub-options? This cannot be undone.`}
        busy={pending === "delete"}
        onConfirm={confirmDelete}
        onCancel={() => setConfirmOpen(false)}
      />

      {hasChildren && expanded && (
        // Children indented under a vertical "spine" so the hierarchy reads as a tree.
        <ul
          style={{
            padding: 0,
            margin: 0,
            marginLeft: "0.55rem",
            paddingLeft: "0.7rem",
            borderLeft: `2px solid ${colors.border}`,
          }}
        >
          {node.children.map((child) => (
            <MassingOption
              key={child.id}
              node={child}
              polygonId={polygonId}
              onChanged={onChanged}
              onOptionDirtyChange={onOptionDirtyChange}
              activeOptionId={activeOptionId}
              onActivate={onActivate}
              depth={depth + 1}
            />
          ))}
        </ul>
      )}
    </li>
  );
}
