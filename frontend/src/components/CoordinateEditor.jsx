import { useEffect, useState } from "react";
import { button, colors, deleteButton, input, label } from "../styles.js";

// Parse pasted text into an ordered array of [x, y] points, or throw a helpful error.
// Accepts JSON like [[0,0],[10,0],[10,5],[0,5]].
function parsePoints(text) {
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("Not valid JSON — expected e.g. [[0,0],[10,0],[10,5],[0,5]]");
  }
  if (!Array.isArray(data)) throw new Error("Expected an array of points, e.g. [[0,0],[10,0],[10,5]]");
  return data.map((pt, i) => {
    if (!Array.isArray(pt) || pt.length !== 2) throw new Error(`Point ${i} must be an [x, y] pair`);
    const [x, y] = pt;
    if (![x, y].every((n) => typeof n === "number" && Number.isFinite(n)))
      throw new Error(`Point ${i} must be two finite numbers`);
    return [x, y];
  });
}

// Edits a polygon as an ordered array of [x, y] points (metres).
export default function CoordinateEditor({ title, coords, onChange }) {
  const [raw, setRaw] = useState("");
  const [error, setError] = useState(null);
  // True while the user is typing in the JSON box, so we don't overwrite it.
  const [editingRaw, setEditingRaw] = useState(false);

  // Keep the JSON box in sync with the points whenever they change elsewhere
  // (per-point inputs, paste, the parent) — but never while it's being typed in.
  useEffect(() => {
    if (!editingRaw) {
      setRaw(coords.length ? JSON.stringify(coords) : "");
      setError(null);
    }
  }, [coords, editingRaw]);

  const setPoint = (i, axis, value) => {
    const next = coords.map((p) => [...p]);
    next[i][axis] = value === "" ? "" : Number(value);
    onChange(next);
  };

  const addPoint = () => onChange([...coords, [0, 0]]);
  const removePoint = (i) => onChange(coords.filter((_, idx) => idx !== i));

  // Apply pasted coordinates live: valid JSON replaces the points immediately, so
  // there's nothing to "apply" before saving. Invalid text just shows an error and
  // leaves the current points untouched; clearing the box leaves them alone too.
  const onPaste = (text) => {
    setRaw(text);
    if (!text.trim()) {
      setError(null);
      return;
    }
    try {
      onChange(parsePoints(text));
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div>
      <span style={label}>{title}</span>

      {/* Paste an entire polygon at once — validated before it replaces the points. */}
      <div style={{ marginBottom: "0.6rem" }}>
        <textarea
          style={{
            ...input,
            width: "100%",
            minHeight: "3.5rem",
            fontFamily: "ui-monospace, monospace",
            resize: "vertical",
          }}
          placeholder="Paste points, e.g. [[0,0],[10,0],[10,5],[0,5]] — applied as you paste"
          value={raw}
          onChange={(e) => onPaste(e.target.value)}
          onFocus={() => setEditingRaw(true)}
          onBlur={() => setEditingRaw(false)}
          aria-label={`${title} paste coordinates`}
        />
        {error && <div style={{ marginTop: "0.3rem", fontSize: "0.75rem", color: colors.danger }}>{error}</div>}
      </div>

      {coords.length === 0 && <p style={{ margin: "0 0 0.4rem", fontSize: "0.8rem", color: "#888" }}>No points yet.</p>}
      {coords.map((p, i) => (
        <div key={i} style={{ display: "flex", gap: "0.35rem", alignItems: "center", marginBottom: "0.3rem" }}>
          <span style={{ width: "1.4rem", fontSize: "0.75rem", color: "#888" }}>{i}</span>
          <input
            style={{ ...input, width: "5rem" }}
            type="number"
            step="any"
            value={p[0]}
            onChange={(e) => setPoint(i, 0, e.target.value)}
            aria-label={`point ${i} x`}
          />
          <input
            style={{ ...input, width: "5rem" }}
            type="number"
            step="any"
            value={p[1]}
            onChange={(e) => setPoint(i, 1, e.target.value)}
            aria-label={`point ${i} y`}
          />
          <button style={deleteButton} onClick={() => removePoint(i)} title="Remove point">
            ×
          </button>
        </div>
      ))}
      <button style={button} onClick={addPoint}>
        + Add point
      </button>
    </div>
  );
}
