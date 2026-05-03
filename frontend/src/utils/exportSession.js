/** Build a Markdown transcript for download (professor / demo artifact). */
export function buildSessionMarkdown(sessionId, messages) {
  const when = new Date().toISOString();
  const lines = [
    "# SemCacheLM session export",
    "",
    `- **Exported:** ${when}`,
    `- **Session ID:** \`${sessionId}\``,
    "",
    "---",
    "",
  ];

  for (const m of messages) {
    if (m.role === "user") {
      lines.push("## User", "", m.content.trim(), "", "---", "");
      continue;
    }
    const p = m.payload;
    if (!p) {
      lines.push("## Assistant", "", (m.content || "").trim(), "", "---", "");
      continue;
    }
    const meta = m.requestMeta;
    lines.push(
      "## Assistant",
      "",
      m.content.trim(),
      "",
      "### Routing metadata",
      "",
      "| Field | Value |",
      "| --- | --- |",
      `| source | \`${p.source}\` |`,
      `| agent_action | \`${p.agent_action}\` |`,
      `| similarity_score | ${(p.similarity_score * 100).toFixed(1)}% |`,
      `| latency_ms | ${p.latency_ms} |`,
      `| cache_id | ${p.cache_id ?? "—"} |`,
      `| decision_reason | ${p.decision_reason?.replace(/\|/g, "\\|") ?? "—"} |`
    );
    if (p.matched_query) {
      lines.push(`| matched_query | ${String(p.matched_query).replace(/\|/g, "\\|")} |`);
    }
    if (p.validation_confidence != null) {
      lines.push(`| validation_confidence | ${p.validation_confidence} |`);
    }
    if (meta) {
      lines.push(
        "",
        "_Thresholds used for this request:_",
        `- hit: ${meta.hitThreshold}, gray floor: ${meta.grayLow}`
      );
    }
    lines.push("", "---", "");
  }

  return lines.join("\n");
}

export function downloadMarkdown(filename, text) {
  const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
