export const colors = {
  border: "#d0d0d7",
  borderStrong: "#bbb",
  muted: "#666",
  bg: "#f7f7f9",
  selected: "#e8f0fe",
  selectedBorder: "#4a90d9",
  feasible: "#1a7f37",
  infeasible: "#cf222e",
  danger: "#cf222e",
};

export const button = {
  font: "inherit",
  fontSize: "0.8rem",
  padding: "0.25rem 0.6rem",
  border: `1px solid ${colors.border}`,
  borderRadius: 6,
  background: "#fff",
  cursor: "pointer",
};

export const saveButton = {
  ...button,
  background: colors.selectedBorder,
  borderColor: colors.selectedBorder,
  color: "#fff",
};

export const generateButton = {
  ...button,
  background: colors.feasible,
  borderColor: colors.feasible,
  color: "#fff",
};

export const deleteButton = {
  ...button,
  borderColor: colors.danger,
  color: colors.danger,
};

// Round "＋" affordance — a blue plus in a circle, e.g. add a sub-option.
export const addChildButton = {
  width: "1.5rem",
  height: "1.5rem",
  flex: "0 0 auto",
  padding: 0,
  borderRadius: "50%",
  border: `1px solid ${colors.selectedBorder}`,
  background: colors.selectedBorder,
  color: "#fff",
  cursor: "pointer",
  fontSize: "1.05rem",
  lineHeight: 1,
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
};

// Pencil affordance next to a name shown as text — click to switch to editing.
export const editNameButton = {
  flex: "0 0 auto",
  padding: "0 0.2rem",
  border: "none",
  background: "none",
  cursor: "pointer",
  color: colors.muted,
  fontSize: "0.8rem",
  lineHeight: 1,
};

// Borderless block holding a massing option's constraints (setback, and more to come).
export const settingsSection = {
  display: "flex",
  flexWrap: "wrap",
  alignItems: "center",
  gap: "0.8rem",
  marginTop: "0.5rem",
};

export const input = {
  font: "inherit",
  fontSize: "0.85rem",
  padding: "0.3rem 0.45rem",
  border: `1px solid ${colors.border}`,
  borderRadius: 6,
  boxSizing: "border-box",
};

export const label = {
  display: "block",
  fontSize: "0.72rem",
  textTransform: "uppercase",
  letterSpacing: "0.04em",
  color: colors.muted,
  marginBottom: "0.25rem",
};

export const card = {
  border: `1px solid ${colors.border}`,
  borderRadius: 8,
  padding: "0.75rem",
  background: "#fff",
};
