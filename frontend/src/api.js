const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const V1 = `${API_BASE}/api/v1`;

// Feasibility statuses returned by the massing-option /generate endpoint.
export const FEASIBLE = "feasible"; // generation passed
export const INFEASIBLE = "infeasible"; // generation failed

async function request(path, options = {}) {
  const res = await fetch(`${V1}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (res.status === 204) return null;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail ?? res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body;
}

// --- Polygons ---
export const listPolygons = () => request("/polygons");
export const createPolygon = (payload) => request("/polygons", { method: "POST", body: JSON.stringify(payload) });
export const updatePolygon = (id, payload) =>
  request(`/polygons/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
export const deletePolygon = (id) => request(`/polygons/${id}`, { method: "DELETE" });
// Massing options are listed under their polygon, even though they have their own write routes.
export const listPolygonMassingOptions = (polygonId) => request(`/polygons/${polygonId}/massing-options`);

// --- Massing options ---
export const createMassingOption = (payload) =>
  request("/massing-options", { method: "POST", body: JSON.stringify(payload) });
export const updateMassingOption = (id, payload) =>
  request(`/massing-options/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
export const deleteMassingOption = (id) => request(`/massing-options/${id}`, { method: "DELETE" });
export const generateMassingOption = (id) => request(`/massing-options/${id}/generate`, { method: "POST" });
