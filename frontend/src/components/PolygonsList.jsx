import { button, colors } from "../styles.js";

// The sidebar list of polygons: header, add button, and a selectable row per polygon.
export default function PolygonsList({ polygons, selectedId, onSelect, onAdd }) {
  return (
    <>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.6rem" }}>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Polygons</h2>
        <button style={button} onClick={onAdd}>
          + Add polygon
        </button>
      </div>

      {polygons.length === 0 ? (
        <p style={{ fontSize: "0.85rem", color: "#888" }}>No polygons yet.</p>
      ) : (
        <ul
          style={{
            listStyle: "none",
            padding: 0,
            margin: "0 0 1rem",
            display: "flex",
            flexDirection: "column",
            gap: "0.3rem",
          }}
        >
          {polygons.map((p) => {
            const active = p.id === selectedId;
            return (
              <li key={p.id}>
                <button
                  onClick={() => onSelect(p.id)}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    font: "inherit",
                    fontSize: "0.88rem",
                    padding: "0.45rem 0.6rem",
                    borderRadius: 6,
                    cursor: "pointer",
                    border: `1px solid ${active ? colors.selectedBorder : colors.border}`,
                    background: active ? colors.selected : "#fff",
                  }}
                >
                  {p.title}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
