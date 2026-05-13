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

/**
 * POST /query may return 202 + job_id (async pipeline). Poll until completed.
 */
async function submitQueryAndWait(body) {
  const res = await fetch(`${BASE_URL}${PREFIX}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok || json.success === false) {
    const msg = json?.error?.message || `Request failed: ${res.status}`;
    throw new Error(msg);
  }

  if (res.status === 202) {
    const jobId = json.data?.job_id;
    if (!jobId) throw new Error("Async query accepted but missing job_id");

    const deadline = Date.now() + 120_000;
    let delay = 80;
    while (Date.now() < deadline) {
      const pollRes = await fetch(`${BASE_URL}${PREFIX}/query/${jobId}`, {
        headers: { "Content-Type": "application/json" },
      });
      const pollJson = await pollRes.json().catch(() => ({}));
      if (!pollRes.ok || pollJson.success === false) {
        const msg = pollJson?.error?.message || `Poll failed: ${pollRes.status}`;
        throw new Error(msg);
      }
      const st = pollJson.data;
      if (st.status === "completed" && st.result) return st.result;
      if (st.status === "failed" || st.status === "degraded") {
        throw new Error(st.error || `Query ended as ${st.status}`);
      }
      await new Promise((r) => setTimeout(r, delay));
      delay = Math.min(Math.round(delay * 1.45), 2000);
    }
    throw new Error("Query timed out waiting for result");
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
    return submitQueryAndWait(body);
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
  invalidateCache: (body) =>
    request("/cache/invalidate", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  summary: () => request("/analytics/summary"),
  history: (limit = 20) => request(`/analytics/history?limit=${limit}`),
  health: () => request("/health"),
};
