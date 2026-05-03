const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const PREFIX = "/api/v1";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${PREFIX}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok || json.success === false) {
    const msg = json?.error?.message || `Request failed: ${res.status}`;
    throw new Error(msg);
  }
  return json.data;
}

export const api = {
  query: (query, sessionId, opts = {}) => {
    const body = {
      query,
      session_id: sessionId,
    };
    if (opts.similarity_hit_threshold != null) {
      body.similarity_hit_threshold = opts.similarity_hit_threshold;
    }
    if (opts.similarity_gray_zone_low != null) {
      body.similarity_gray_zone_low = opts.similarity_gray_zone_low;
    }
    return request("/query", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
  getDecisionThresholds: () => request("/config/decision-thresholds"),
  updateDecisionThresholds: (similarity_hit_threshold, similarity_gray_zone_low) =>
    request("/config/decision-thresholds", {
      method: "PUT",
      body: JSON.stringify({
        similarity_hit_threshold,
        similarity_gray_zone_low,
      }),
    }),
  clearAllCache: () =>
    request("/cache/clear", {
      method: "POST",
    }),
  feedback: (cacheId, rating) =>
    request(`/feedback/${cacheId}`, {
      method: "POST",
      body: JSON.stringify({ rating }),
    }),
  listCache: (page = 1, pageSize = 50) =>
    request(`/cache/entries?page=${page}&page_size=${pageSize}`),
  deleteCache: (id) => request(`/cache/${id}`, { method: "DELETE" }),
  evict: () => request("/cache/evict", { method: "POST" }),
  summary: () => request("/analytics/summary"),
  history: (limit = 20) => request(`/analytics/history?limit=${limit}`),
  health: () => request("/health"),
};
