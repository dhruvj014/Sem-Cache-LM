import { useState } from "react";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import { api } from "../api/client.js";

export default function FeedbackButtons({ cacheId }) {
  const [submitted, setSubmitted] = useState(null);
  const [error, setError] = useState(null);

  if (!cacheId) return null;

  const submit = async (rating) => {
    try {
      const res = await api.feedback(cacheId, rating);
      setSubmitted({ rating, score: res.new_quality_score });
    } catch (e) {
      setError(e.message);
    }
  };

  if (submitted) {
    return (
      <div className="text-xs text-slate-400">
        Recorded {submitted.rating === "up" ? "👍 upvote" : "👎 downvote"} · new quality{" "}
        <span className="code">{submitted.score.toFixed(3)}</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => submit("up")}
        className="flex items-center gap-1 px-3 py-1.5 rounded-md bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/20 text-sm"
      >
        <ThumbsUp size={14} /> Upvote
      </button>
      <button
        onClick={() => submit("down")}
        className="flex items-center gap-1 px-3 py-1.5 rounded-md bg-rose-500/10 text-rose-300 border border-rose-500/30 hover:bg-rose-500/20 text-sm"
      >
        <ThumbsDown size={14} /> Downvote
      </button>
      {error && <span className="text-xs text-rose-400">{error}</span>}
    </div>
  );
}
