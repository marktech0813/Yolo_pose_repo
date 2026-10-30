function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

const STATUS_LABEL = {
  correct: "Correct",
  grammar: "Grammar",
  spelling: "Spelling",
  accent: "Accent",
  filler: "Filler",
  recognition: "Unclear",
};

export function formatDuration(sec) {
  if (sec == null || Number.isNaN(sec)) return null;
  const s = Math.max(0, Math.round(sec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}

export function metricsLine(metrics) {
  if (!metrics) return "";
  const parts = [];
  if (metrics.word_count != null && metrics.correct_count != null) {
    parts.push(`${metrics.correct_count}/${metrics.word_count} correct`);
  }
  if (metrics.grammar_count) parts.push(`${metrics.grammar_count} grammar`);
  if (metrics.spelling_count) parts.push(`${metrics.spelling_count} spelling`);
  if (metrics.unclear_count) parts.push(`${metrics.unclear_count} accent`);
  if (metrics.filler_count) parts.push(`${metrics.filler_count} fillers`);
  if (metrics.pause_count) parts.push(`${metrics.pause_count} pauses`);
  if (metrics.wpm != null) parts.push(`~${Math.round(metrics.wpm)} WPM`);
  if (metrics.duration_sec != null) parts.push(formatDuration(metrics.duration_sec));
  return parts.join(" · ");
}

function renderWordReviews(reviews) {
  if (!reviews || !reviews.length) return "";
  const chips = reviews
    .map((w) => {
      const status = w.status || "correct";
      const title = [
        STATUS_LABEL[status] || status,
        w.message || "",
        w.replacements?.length ? `Try: ${w.replacements.slice(0, 2).join(", ")}` : "",
      ]
        .filter(Boolean)
        .join(" — ");
      const tip = title ? ` title="${escapeHtml(title)}"` : "";
      return `<span class="word word-${status}"${tip}>${escapeHtml(w.text)}</span>`;
    })
    .join(" ");
  return `<div class="heard-block">
    <p class="heard-label">Recognized English</p>
    <p class="heard-sentence">${chips}</p>
    <ul class="legend" aria-label="Mark meanings">
      <li><span class="swatch word-correct"></span> Correct</li>
      <li><span class="swatch word-grammar"></span> Grammar</li>
      <li><span class="swatch word-spelling"></span> Spelling</li>
      <li><span class="swatch word-accent"></span> Accent</li>
      <li><span class="swatch word-filler"></span> Filler</li>
    </ul>
  </div>`;
}

function renderAlertList(alerts) {
  const useful = (alerts || []).filter((a) =>
    ["grammar", "spelling", "accent", "pronunciation", "recognition", "filler", "repeat", "pause", "rate"].includes(
      a.kind
    )
  );
  if (!useful.length) {
    return `<p class="alert-empty">No issues flagged on this sentence.</p>`;
  }
  const items = useful
    .slice(0, 8)
    .map((a) => {
      const kind = a.kind === "pronunciation" ? "accent" : a.kind;
      const label = STATUS_LABEL[kind] || kind;
      const sug =
        a.replacements && a.replacements.length
          ? ` <span class="alert-fix">→ ${escapeHtml(a.replacements.slice(0, 2).join(", "))}</span>`
          : "";
      return `<li class="alert-item alert-${kind}">
        <span class="alert-kind">${escapeHtml(label)}</span>
        <span class="alert-msg">${escapeHtml(a.message || a.text || "")}${sug}</span>
      </li>`;
    })
    .join("");
  return `<ol class="alert-list">${items}</ol>`;
}

export function renderUserMessage(container, { text, durationSec }) {
  const el = document.createElement("article");
  el.className = "msg msg-user";
  const meta = durationSec != null ? `<p class="msg-meta">${escapeHtml(formatDuration(durationSec))}</p>` : "";
  el.innerHTML = `
    <p class="msg-role">You</p>
    <p class="msg-body">${escapeHtml(text)}</p>
    ${meta}
  `;
  container.appendChild(el);
  el.scrollIntoView({ behavior: "smooth", block: "end" });
  return el;
}

export function renderCoachMessage(container, result) {
  const el = document.createElement("article");
  el.className = "msg msg-coach";
  const heard = renderWordReviews(result.word_reviews);
  const fallback =
    !result.word_reviews?.length && result.transcript
      ? `<div class="heard-block">
           <p class="heard-label">Recognized English</p>
           <p class="heard-sentence plain">${escapeHtml(result.transcript)}</p>
         </div>`
      : "";
  const meta = metricsLine(result.metrics);
  el.innerHTML = `
    <p class="msg-role">Northline</p>
    ${heard || fallback}
    <p class="msg-body">${escapeHtml(result.coach_message || "")}</p>
    ${renderAlertList(result.alerts)}
    ${meta ? `<p class="msg-meta">${escapeHtml(meta)}</p>` : ""}
  `;
  container.appendChild(el);
  el.scrollIntoView({ behavior: "smooth", block: "end" });
  return el;
}

export function renderPending(container) {
  const el = document.createElement("article");
  el.className = "msg msg-coach pending-msg";
  el.innerHTML = `
    <p class="msg-role">Northline</p>
    <p class="msg-body pending">Recognizing your English speech…</p>
  `;
  container.appendChild(el);
  el.scrollIntoView({ behavior: "smooth", block: "end" });
  return el;
}

export function renderWelcome(container) {
  const el = document.createElement("article");
  el.className = "msg msg-coach";
  el.innerHTML = `
    <p class="msg-role">Northline</p>
    <p class="msg-body">Speak English into the mic. I’ll show the sentence I heard first, then mark what is correct or wrong for grammar, spelling, native accent, and fluency — all offline on this machine.</p>
  `;
  container.appendChild(el);
}
