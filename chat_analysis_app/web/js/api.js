export async function fetchHealth() {
  const res = await fetch("/api/health");
  if (!res.ok) throw new Error(`Health ${res.status}`);
  return res.json();
}

export async function analyzeText(text) {
  const body = new FormData();
  body.append("text", text);
  const res = await fetch("/api/analyze", { method: "POST", body });
  return parseAnalyze(res);
}

export async function analyzeAudio(blob) {
  const body = new FormData();
  body.append("audio", blob, "utterance.wav");
  const res = await fetch("/api/analyze", { method: "POST", body });
  return parseAnalyze(res);
}

async function parseAnalyze(res) {
  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    const detail = data?.detail || `Request failed (${res.status})`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}
