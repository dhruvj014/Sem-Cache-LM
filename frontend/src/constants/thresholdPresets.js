/** One-click policy presets for similarity bands (upper = auto hit, lower = gray floor). */
export const THRESHOLD_PRESETS = [
  {
    id: "conservative",
    label: "Conservative",
    hint: "Narrow gray zone, high bar for auto-cache — fewer risky reuses.",
    similarity_hit_threshold: 0.94,
    similarity_gray_zone_low: 0.82,
  },
  {
    id: "balanced",
    label: "Balanced",
    hint: "Default-friendly tradeoff for demos and general use.",
    similarity_hit_threshold: 0.92,
    similarity_gray_zone_low: 0.7,
  },
  {
    id: "aggressive",
    label: "Aggressive",
    hint: "More cache hits; wider gray zone — validate more often.",
    similarity_hit_threshold: 0.86,
    similarity_gray_zone_low: 0.58,
  },
];
