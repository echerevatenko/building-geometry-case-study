import MassingOption from "./MassingOption.jsx";

// Build a parent/child tree from the flat, pre-ordered massing option list.
function buildTree(massingOptions) {
  const byId = new Map(massingOptions.map((o) => [o.id, { ...o, children: [] }]));
  const roots = [];
  for (const node of byId.values()) {
    const parent = node.parent_id != null ? byId.get(node.parent_id) : null;
    if (parent) parent.children.push(node);
    else roots.push(node);
  }
  return roots;
}

export default function MassingOptionsTree({ massingOptions, polygonId, onChanged, onOptionDirtyChange }) {
  const roots = buildTree(massingOptions);
  if (roots.length === 0) {
    return <p style={{ fontSize: "0.8rem", color: "#888", margin: "0.5rem 0" }}>No massing options yet.</p>;
  }
  return (
    <ul style={{ padding: 0, margin: 0 }}>
      {roots.map((node) => (
        <MassingOption
          key={node.id}
          node={node}
          polygonId={polygonId}
          onChanged={onChanged}
          onOptionDirtyChange={onOptionDirtyChange}
        />
      ))}
    </ul>
  );
}
